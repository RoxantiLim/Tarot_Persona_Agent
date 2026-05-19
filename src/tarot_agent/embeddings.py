from __future__ import annotations

import os

from .config import AppConfig


class BgeM3Embeddings:
    """Small LangChain-compatible wrapper around sentence-transformers."""

    def __init__(self, config: AppConfig):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("缺少 sentence-transformers，请先安装 requirements.txt。") from exc

        os.environ.setdefault("HF_HOME", str(config.model_cache_dir))
        os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(config.model_cache_dir))

        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            device = "cpu"

        self.model = SentenceTransformer(
            config.embedding_model,
            cache_folder=str(config.model_cache_dir),
            device=device,
        )

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
