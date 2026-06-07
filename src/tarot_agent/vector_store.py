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
CHROMA_COLLECTION = "tarot_knowledge"
_STORE_CACHE = {}


class LocalVectorStore:
    """Small NumPy fallback store for local development and recovery."""

    backend_name = "numpy"

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
        return [
            document_with_score(self.documents[int(idx)], scores[int(idx)])
            for idx in top_indices
        ]


class ChromaVectorStore:
    """ChromaDB-backed vector store using precomputed bge-m3 embeddings."""

    backend_name = "chroma"

    def __init__(self, config: AppConfig):
        self.config = config
        self.embeddings = BgeM3Embeddings(config)
        self.client = _chroma_client(config)
        self.collection = self.client.get_collection(CHROMA_COLLECTION)

    def similarity_search(self, query: str, k: int = 5) -> list[Document]:
        results = self.collection.query(
            query_embeddings=[self.embeddings.embed_query(query)],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        return [
            document_with_score(
                Document(page_content=text, metadata=metadata or {}),
                1.0 - float(distance),
            )
            for text, metadata, distance in zip(documents, metadatas, distances)
        ]


def _chroma_client(config: AppConfig):
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("Missing chromadb dependency. Install requirements.txt first.") from exc
    return chromadb.PersistentClient(path=str(config.chroma_dir))


def document_with_score(document: Document, score: float) -> Document:
    metadata = dict(document.metadata)
    metadata["retrieval_score"] = float(score)
    return Document(page_content=document.page_content, metadata=metadata)


def chroma_index_exists(config: AppConfig) -> bool:
    return (config.chroma_dir / "chroma.sqlite3").exists()


def index_exists(config: AppConfig) -> bool:
    local_index = config.data_dir / "indexes" / LOCAL_INDEX_DIR / LOCAL_VECTORS_FILE
    return local_index.exists() or chroma_index_exists(config)


def reset_index(config: AppConfig) -> None:
    _STORE_CACHE.clear()
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
    print(f"[index] embedding {len(texts)} chunks with {config.embedding_model}", flush=True)
    vectors = np.asarray(embeddings.embed_documents(texts), dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    vectors = vectors / np.maximum(norms, 1e-12)

    _write_numpy_store(config, documents, vectors)
    print("[index] NumPy fallback index written", flush=True)
    if config.build_chroma:
        _write_chroma_store(config, documents, vectors)
        print("[index] ChromaDB index written", flush=True)
        if config.vector_store_backend == "chroma":
            return ChromaVectorStore(config)
    return LocalVectorStore(config)


def _write_numpy_store(config: AppConfig, documents: list[Document], vectors: np.ndarray) -> None:
    local_index_dir = config.data_dir / "indexes" / LOCAL_INDEX_DIR
    local_index_dir.mkdir(parents=True, exist_ok=True)
    np.save(local_index_dir / LOCAL_VECTORS_FILE, vectors)
    with (local_index_dir / LOCAL_DOCS_FILE).open("w", encoding="utf-8") as f:
        for doc in documents:
            row = {"page_content": doc.page_content, "metadata": dict(doc.metadata)}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_chroma_store(config: AppConfig, documents: list[Document], vectors: np.ndarray) -> None:
    client = _chroma_client(config)
    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    batch_size = 128
    for start in range(0, len(documents), batch_size):
        batch = documents[start : start + batch_size]
        collection.add(
            ids=[str(doc.metadata["chunk_id"]) for doc in batch],
            documents=[doc.page_content for doc in batch],
            metadatas=[dict(doc.metadata) for doc in batch],
            embeddings=vectors[start : start + batch_size].tolist(),
        )


def load_vector_store(config: AppConfig):
    local_index = config.data_dir / "indexes" / LOCAL_INDEX_DIR / LOCAL_VECTORS_FILE
    if config.vector_store_backend == "chroma" and chroma_index_exists(config):
        chroma_file = config.chroma_dir / "chroma.sqlite3"
        cache_key = (
            "chroma",
            str(config.chroma_dir),
            chroma_file.stat().st_mtime_ns,
            config.embedding_model,
            config.embedding_device,
        )
        if cache_key not in _STORE_CACHE:
            _STORE_CACHE.clear()
            try:
                _STORE_CACHE[cache_key] = ChromaVectorStore(config)
            except Exception:
                _STORE_CACHE[cache_key] = LocalVectorStore(config)
        return _STORE_CACHE[cache_key]

    if local_index.exists():
        docs_file = config.data_dir / "indexes" / LOCAL_INDEX_DIR / LOCAL_DOCS_FILE
        cache_key = (
            "numpy",
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

    raise RuntimeError("No knowledge index found. Run scripts\\ingest_documents.py first.")
