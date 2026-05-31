from __future__ import annotations

import json
import shutil

import numpy as np

from .config import AppConfig
from .documents import Document
from .embeddings import BgeM3Embeddings


LOCAL_INDEX_DIR = "local_vectors"
LOCAL_VECTORS_FILE = "vectors.npy"
LOCAL_DOCS_FILE = "documents.jsonl"
_STORE_CACHE = {}


class LocalVectorStore:
    def __init__(self, config: AppConfig):
        self.config = config
        self.index_dir = config.data_dir / "indexes" / LOCAL_INDEX_DIR
        self.embeddings = BgeM3Embeddings(config)
        self.vectors = np.load(self.index_dir / LOCAL_VECTORS_FILE, mmap_mode="r")
        self.documents = []
        with (self.index_dir / LOCAL_DOCS_FILE).open("r", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                self.documents.append(Document(page_content=row["page_content"], metadata=row["metadata"]))

    def similarity_search(self, query: str, k: int = 5) -> list[Document]:
        query_vector = np.asarray(self.embeddings.embed_query(query), dtype=np.float32)
        query_norm = np.linalg.norm(query_vector)
        if query_norm:
            query_vector = query_vector / query_norm
        scores = self.vectors @ query_vector
        top_indices = np.argsort(scores)[::-1][:k]
        return [self.documents[int(idx)] for idx in top_indices]


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
    local_index = config.data_dir / "indexes" / LOCAL_INDEX_DIR / LOCAL_VECTORS_FILE
    return local_index.exists() or (config.chroma_dir.exists() and any(config.chroma_dir.iterdir()))


def reset_index(config: AppConfig) -> None:
    local_index_dir = config.data_dir / "indexes" / LOCAL_INDEX_DIR
    if local_index_dir.exists():
        shutil.rmtree(local_index_dir)
    if config.chroma_dir.exists():
        shutil.rmtree(config.chroma_dir)
    config.chroma_dir.mkdir(parents=True, exist_ok=True)


def build_vector_store(config: AppConfig, documents: list[Document]):
    reset_index(config)
    embeddings = BgeM3Embeddings(config)
    texts = [doc.page_content for doc in documents]
    vectors = np.asarray(embeddings.embed_documents(texts), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = vectors / np.maximum(norms, 1e-12)

    local_index_dir = config.data_dir / "indexes" / LOCAL_INDEX_DIR
    local_index_dir.mkdir(parents=True, exist_ok=True)
    np.save(local_index_dir / LOCAL_VECTORS_FILE, vectors)
    with (local_index_dir / LOCAL_DOCS_FILE).open("w", encoding="utf-8") as f:
        for doc in documents:
            row = {"page_content": doc.page_content, "metadata": dict(doc.metadata)}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    if config.build_chroma:
        Chroma = _chroma_class()
        try:
            return Chroma.from_documents(
                documents=documents,
                embedding=embeddings,
                persist_directory=str(config.chroma_dir),
                collection_name="tarot_knowledge",
            )
        except Exception:
            return LocalVectorStore(config)
    return LocalVectorStore(config)


def load_vector_store(config: AppConfig):
    local_index = config.data_dir / "indexes" / LOCAL_INDEX_DIR / LOCAL_VECTORS_FILE
    if local_index.exists():
        docs_file = config.data_dir / "indexes" / LOCAL_INDEX_DIR / LOCAL_DOCS_FILE
        cache_key = (
            str(local_index),
            local_index.stat().st_mtime_ns,
            docs_file.stat().st_mtime_ns if docs_file.exists() else 0,
            config.embedding_model,
            config.embedding_device,
        )
        if cache_key not in _STORE_CACHE:
            _STORE_CACHE.clear()
            _STORE_CACHE[cache_key] = LocalVectorStore(config)
        return _STORE_CACHE[cache_key]
    embeddings = BgeM3Embeddings(config)
    Chroma = _chroma_class()
    return Chroma(
        persist_directory=str(config.chroma_dir),
        embedding_function=embeddings,
        collection_name="tarot_knowledge",
    )
