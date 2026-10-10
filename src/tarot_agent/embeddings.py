from __future__ import annotations

import os
from urllib.parse import urlsplit

from .config import AppConfig

_MODEL_CACHE = {}


def create_embeddings(config: AppConfig):
    if config.embedding_provider == "api":
        return ApiEmbeddings(config)
    return BgeM3Embeddings(config)


class ApiEmbeddings:
    """OpenAI-compatible embedding API; never imports local model packages."""

    def __init__(self, config: AppConfig):
        if not config.embedding_api_key.strip():
            raise RuntimeError("Embedding API key 未配置，请填写 EMBEDDING_API_KEY。")
        if config.embedding_batch_size < 1 or config.embedding_timeout_seconds <= 0:
            raise ValueError("Embedding batch size and timeout must be positive")
        url = urlsplit(config.embedding_base_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("EMBEDDING_BASE_URL must be an HTTPS base URL without credentials or query parameters")
        from openai import OpenAI

        self.config = config
        self.client = OpenAI(
            api_key=config.embedding_api_key,
            base_url=config.embedding_base_url,
            timeout=config.embedding_timeout_seconds,
            max_retries=1,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        import numpy as np

        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.config.embedding_batch_size):
            batch = texts[start : start + self.config.embedding_batch_size]
            if any(not text.strip() for text in batch):
                raise ValueError("Embedding inputs must not be empty")
            # Avoid forwarding upstream error messages that may contain request headers.
            try:
                response = self.client.embeddings.create(
                    model=self.config.embedding_model, input=batch, encoding_format="float",
                )
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                label = f"HTTP {status}" if status else type(exc).__name__
                raise RuntimeError(f"Embedding API 请求失败（{label}），请检查密钥、额度和网络后重试。") from None
            rows = sorted(response.data, key=lambda item: item.index)
            if [row.index for row in rows] != list(range(len(batch))):
                raise ValueError("Embedding API returned missing or duplicate vector indices")
            matrix = np.asarray([row.embedding for row in rows], dtype=np.float32)
            if matrix.ndim != 2 or matrix.shape[1] == 0 or not np.isfinite(matrix).all():
                raise ValueError("Embedding API returned invalid vectors")
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            if np.any(norms == 0):
                raise ValueError("Embedding API returned zero vectors")
            if vectors and len(vectors[0]) != matrix.shape[1]:
                raise ValueError("Embedding API returned inconsistent vector dimensions")
            vectors.extend((matrix / norms).tolist())
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class BgeM3Embeddings:
    """Small LangChain-compatible wrapper around sentence-transformers."""

    def __init__(self, config: AppConfig):
        os.environ.setdefault("HF_HOME", str(config.model_cache_dir))
        os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(config.model_cache_dir))
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("缺少 sentence-transformers，请先安装 requirements.txt。") from exc

        device = _preferred_device(config)
        cache_key = (config.embedding_model, str(config.model_cache_dir), device)
        if cache_key in _MODEL_CACHE:
            self.model = _MODEL_CACHE[cache_key]
            return

        try:
            self.model = _load_model(SentenceTransformer, config, device)
        except Exception as exc:
            if device == "cuda" and _looks_like_cuda_oom(exc):
                _clear_cuda_cache()
                device = "cpu"
                cache_key = (config.embedding_model, str(config.model_cache_dir), device)
                if cache_key not in _MODEL_CACHE:
                    _MODEL_CACHE[cache_key] = _load_model_with_fallback(SentenceTransformer, config, device)
                self.model = _MODEL_CACHE[cache_key]
                return
            self.model = _load_transformer_text_embedder(config, device)

        _MODEL_CACHE[cache_key] = self.model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts,
            batch_size=8,
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        vector = self.model.encode(text, normalize_embeddings=True)
        return vector.tolist()


def _preferred_device(config: AppConfig | None = None) -> str:
    configured_device = (config.embedding_device if config else "auto").strip().lower()
    if configured_device in {"cpu", "cuda"}:
        return configured_device
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _load_model(SentenceTransformer, config: AppConfig, device: str):
    return SentenceTransformer(
        config.embedding_model,
        cache_folder=str(config.model_cache_dir),
        device=device,
        local_files_only=True,
    )


def _load_model_with_fallback(SentenceTransformer, config: AppConfig, device: str):
    try:
        return _load_model(SentenceTransformer, config, device)
    except Exception:
        return _load_transformer_text_embedder(config, device)


def _load_transformer_text_embedder(config: AppConfig, device: str):
    return TransformerTextEmbedder(
        model_name=config.embedding_model,
        cache_dir=str(config.model_cache_dir),
        device=device,
    )


class TransformerTextEmbedder:
    """Text-only fallback for embedding models when sentence-transformers misdetects processors."""

    def __init__(self, model_name: str, cache_dir: str, device: str):
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            cache_dir=cache_dir,
            local_files_only=True,
            trust_remote_code=True,
        )
        self.model = AutoModel.from_pretrained(
            model_name,
            cache_dir=cache_dir,
            local_files_only=True,
            trust_remote_code=True,
        ).to(device)
        self.model.eval()

    def encode(self, texts, normalize_embeddings: bool = True, show_progress_bar: bool = False):
        single = isinstance(texts, str)
        batch_texts = [texts] if single else list(texts)
        outputs = []
        batch_size = 8
        with self.torch.no_grad():
            for start in range(0, len(batch_texts), batch_size):
                batch = batch_texts[start : start + batch_size]
                encoded = self.tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=8192,
                    return_tensors="pt",
                )
                encoded = {key: value.to(self.device) for key, value in encoded.items()}
                model_output = self.model(**encoded)
                token_embeddings = model_output.last_hidden_state
                attention_mask = encoded["attention_mask"].unsqueeze(-1).expand(token_embeddings.size()).float()
                pooled = (token_embeddings * attention_mask).sum(dim=1) / attention_mask.sum(dim=1).clamp(min=1e-9)
                if normalize_embeddings:
                    pooled = self.torch.nn.functional.normalize(pooled, p=2, dim=1)
                outputs.append(pooled.cpu())
        vectors = self.torch.cat(outputs, dim=0).numpy()
        return vectors[0] if single else vectors


def _looks_like_cuda_oom(exc: Exception) -> bool:
    text = repr(exc).lower()
    return "cuda out of memory" in text or "outofmemoryerror" in text


def _clear_cuda_cache() -> None:
    try:
        import torch

        torch.cuda.empty_cache()
    except Exception:
        pass
