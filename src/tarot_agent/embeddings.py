from __future__ import annotations

import os

from .config import AppConfig

_MODEL_CACHE = {}


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

        device = _preferred_device()
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
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        vector = self.model.encode(text, normalize_embeddings=True)
        return vector.tolist()


def _preferred_device() -> str:
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
