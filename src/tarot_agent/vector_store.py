from __future__ import annotations

import shutil

from .config import AppConfig
from .documents import Document
from .embeddings import BgeM3Embeddings


def _chroma_class():
    try:
        from langchain_chroma import Chroma

        return Chroma
    except ImportError:
        try:
            from langchain_community.vectorstores import Chroma

            return Chroma
        except ImportError as exc:
            raise RuntimeError("缺少 Chroma/LangChain 依赖，请先安装 requirements.txt。") from exc


def index_exists(config: AppConfig) -> bool:
    return config.chroma_dir.exists() and any(config.chroma_dir.iterdir())


def reset_index(config: AppConfig) -> None:
    if config.chroma_dir.exists():
        shutil.rmtree(config.chroma_dir)
    config.chroma_dir.mkdir(parents=True, exist_ok=True)


def build_vector_store(config: AppConfig, documents: list[Document]):
    reset_index(config)
    embeddings = BgeM3Embeddings(config)
    Chroma = _chroma_class()
    return Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=str(config.chroma_dir),
        collection_name="tarot_knowledge",
    )


def load_vector_store(config: AppConfig):
    embeddings = BgeM3Embeddings(config)
    Chroma = _chroma_class()
    return Chroma(
        persist_directory=str(config.chroma_dir),
        embedding_function=embeddings,
        collection_name="tarot_knowledge",
    )
