from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path

import numpy as np

from .config import AppConfig
from .documents import Document
from .embeddings import create_embeddings


LOCAL_INDEX_DIR = "local_vectors"
LOCAL_VECTORS_FILE = "vectors.npy"
LOCAL_DOCS_FILE = "documents.jsonl"
CHROMA_COLLECTION = "tarot_knowledge"
_STORE_CACHE = {}


def local_index_path(config: AppConfig) -> Path:
    return getattr(config, "local_index_dir", None) or config.data_dir / "indexes" / LOCAL_INDEX_DIR


def embedding_identity(config: AppConfig) -> dict[str, str]:
    identity = {"provider": config.embedding_provider, "model": config.embedding_model}
    if config.embedding_provider == "api":
        identity["base_url"] = config.embedding_base_url.rstrip("/")
    return identity


def validate_local_index(config: AppConfig) -> dict:
    index_dir = local_index_path(config)
    manifest_file = index_dir / "manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8")) if manifest_file.exists() else {}
    if not isinstance(manifest, dict) or (manifest and manifest.get("version") != 1):
        raise ValueError("Unsupported vector index manifest")
    if manifest:
        if manifest.get("embedding") != embedding_identity(config):
            raise RuntimeError("Embedding index mismatch: 请使用当前 embedding 配置重新构建独立索引。")
    elif config.embedding_provider == "api":
        raise RuntimeError("Embedding index mismatch: API 模式不能使用未经验证的旧本地索引。")
    vectors = np.load(index_dir / LOCAL_VECTORS_FILE, mmap_mode="r", allow_pickle=False)
    try:
        count = 0
        for line in (index_dir / LOCAL_DOCS_FILE).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            document = json.loads(line)
            if not isinstance(document, dict) or not isinstance(document.get("page_content"), str) or not document["page_content"].strip() or not isinstance(document.get("metadata"), dict):
                raise ValueError("Invalid document in vector index")
            count += 1
        if vectors.ndim != 2 or vectors.shape[0] != count or count == 0 or vectors.shape[1] == 0:
            raise ValueError("Invalid vector index shape or document count")
        if not np.isfinite(vectors).all() or np.any(np.linalg.norm(vectors, axis=1) == 0):
            raise ValueError("Invalid vector index values")
        if manifest and (manifest.get("count") != count or manifest.get("dimensions") != vectors.shape[1]):
            raise ValueError("Vector index manifest does not match its files")
        return {**manifest, "count": count, "dimensions": int(vectors.shape[1])}
    finally:
        vectors._mmap.close()


class LocalVectorStore:
    """Small NumPy fallback store for local development and recovery."""

    backend_name = "numpy"

    def __init__(self, config: AppConfig):
        self.config = config
        self.index_dir = local_index_path(config)
        validate_local_index(config)
        self.embeddings = create_embeddings(config)
        self.vectors = np.load(self.index_dir / LOCAL_VECTORS_FILE, mmap_mode="r", allow_pickle=False)
        self.documents = []
        with (self.index_dir / LOCAL_DOCS_FILE).open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                self.documents.append(Document(page_content=row["page_content"], metadata=row["metadata"]))

    def similarity_search(self, query: str, k: int = 5) -> list[Document]:
        query_vector = np.asarray(self.embeddings.embed_query(query), dtype=np.float32)
        query_norm = np.linalg.norm(query_vector)
        if query_norm:
            query_vector = query_vector / query_norm
        if query_vector.shape != (self.vectors.shape[1],) or not np.isfinite(query_vector).all() or not query_norm:
            raise ValueError("Query embedding does not match the index dimensions or contains invalid values")
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
        self.embeddings = create_embeddings(config)
        self.client = _chroma_client(config)
        try:
            self.collection = self.client.get_collection(CHROMA_COLLECTION)
            stored_identity = (self.collection.metadata or {}).get("embedding_identity")
            if stored_identity:
                if json.loads(stored_identity) != embedding_identity(config):
                    raise RuntimeError("Embedding index mismatch: Chroma 索引与当前 embedding 配置不同。")
            elif config.embedding_provider == "api":
                raise RuntimeError("Embedding index mismatch: 请先用 API 重建 Chroma 索引。")
        except Exception:
            if callable(getattr(self.client, "close", None)):
                self.client.close()
            raise

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
    index_dir = local_index_path(config)
    has_numpy = (index_dir / LOCAL_VECTORS_FILE).exists() and (index_dir / LOCAL_DOCS_FILE).exists()
    return has_numpy or (config.vector_store_backend == "chroma" and chroma_index_exists(config))


def reset_index(config: AppConfig) -> None:
    clear_store_cache()
    local_index_dir = local_index_path(config)
    if local_index_dir.exists():
        shutil.rmtree(local_index_dir)
    if config.chroma_dir.exists():
        shutil.rmtree(config.chroma_dir)
    config.chroma_dir.mkdir(parents=True, exist_ok=True)


def build_vector_store(config: AppConfig, documents: list[Document]):
    if not documents:
        raise ValueError("Cannot build an empty vector index")
    embeddings = create_embeddings(config)
    texts = [doc.page_content for doc in documents]
    print(f"[index] embedding {len(texts)} chunks with {config.embedding_model}", flush=True)
    vectors = np.asarray(embeddings.embed_documents(texts), dtype=np.float32)
    if vectors.ndim != 2 or vectors.shape[0] != len(documents) or vectors.shape[1] == 0 or not np.isfinite(vectors).all():
        raise ValueError("Embedding response does not match the documents")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("Embedding response contains zero vectors")
    vectors = vectors / np.maximum(norms, 1e-12)
    index_dir = local_index_path(config)
    index_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".index-build-", dir=index_dir.parent) as temp_dir:
        staging = Path(temp_dir)
        staged_config = replace(config, local_index_dir=staging / "numpy", chroma_dir=staging / "chroma")
        _write_numpy_store(staged_config, documents, vectors)
        validate_local_index(staged_config)
        replacements = [(staged_config.local_index_dir, index_dir)]
        if config.build_chroma:
            _write_chroma_store(staged_config, documents, vectors)
            replacements.append((staged_config.chroma_dir, config.chroma_dir))
        _publish_indexes(replacements)
    print("[index] Validated index published; previous directories retained as backups", flush=True)
    if config.build_chroma and config.vector_store_backend == "chroma":
        return ChromaVectorStore(config)
    return LocalVectorStore(config)


def clear_store_cache() -> None:
    for store in _STORE_CACHE.values():
        vectors = getattr(store, "vectors", None)
        if vectors is not None and getattr(vectors, "_mmap", None) is not None:
            vectors._mmap.close()
        client = getattr(store, "client", None)
        if client is not None and callable(getattr(client, "close", None)):
            client.close()
    _STORE_CACHE.clear()


def _publish_indexes(replacements: list[tuple[Path, Path]]) -> None:
    clear_store_cache()
    previous: list[tuple[Path, Path | None]] = []
    published: list[tuple[Path, Path]] = []
    try:
        for source, target in replacements:
            target.parent.mkdir(parents=True, exist_ok=True)
            backup = target.with_name(f"{target.name}.backup-{uuid.uuid4().hex}") if target.exists() else None
            if backup:
                target.rename(backup)
            previous.append((target, backup))
            source.rename(target)
            published.append((source, target))
    except Exception:
        for source, target in reversed(published):
            target.rename(source)
        for target, backup in reversed(previous):
            if backup:
                backup.rename(target)
        raise


def _write_numpy_store(config: AppConfig, documents: list[Document], vectors: np.ndarray) -> None:
    local_index_dir = local_index_path(config)
    local_index_dir.mkdir(parents=True, exist_ok=True)
    np.save(local_index_dir / LOCAL_VECTORS_FILE, vectors)
    with (local_index_dir / LOCAL_DOCS_FILE).open("w", encoding="utf-8") as f:
        for doc in documents:
            row = {"page_content": doc.page_content, "metadata": dict(doc.metadata)}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = {"version": 1, "embedding": embedding_identity(config), "count": len(documents), "dimensions": int(vectors.shape[1])}
    (local_index_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_chroma_store(config: AppConfig, documents: list[Document], vectors: np.ndarray) -> None:
    client = _chroma_client(config)
    if not callable(getattr(client, "close", None)):
        raise RuntimeError("Transactional Chroma builds require chromadb>=1.5.9; upgrade requirements.txt first.")
    try:
        collection = client.get_or_create_collection(
            name=CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine", "embedding_identity": json.dumps(embedding_identity(config))},
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
    finally:
        client.close()


def load_vector_store(config: AppConfig):
    local_index = local_index_path(config) / LOCAL_VECTORS_FILE
    if config.vector_store_backend == "chroma" and chroma_index_exists(config):
        chroma_file = config.chroma_dir / "chroma.sqlite3"
        cache_key = (
            "chroma",
            str(config.chroma_dir),
            chroma_file.stat().st_mtime_ns,
            config.embedding_model,
            config.embedding_device,
            json.dumps(embedding_identity(config), sort_keys=True),
        )
        if cache_key not in _STORE_CACHE:
            clear_store_cache()
            try:
                _STORE_CACHE[cache_key] = ChromaVectorStore(config)
            except Exception:
                _STORE_CACHE[cache_key] = LocalVectorStore(config)
        return _STORE_CACHE[cache_key]

    if local_index.exists():
        docs_file = local_index_path(config) / LOCAL_DOCS_FILE
        cache_key = (
            "numpy",
            str(local_index),
            local_index.stat().st_mtime_ns,
            docs_file.stat().st_mtime_ns if docs_file.exists() else 0,
            config.embedding_model,
            config.embedding_device,
            json.dumps(embedding_identity(config), sort_keys=True),
        )
        if cache_key not in _STORE_CACHE:
            clear_store_cache()
            _STORE_CACHE[cache_key] = LocalVectorStore(config)
        return _STORE_CACHE[cache_key]

    raise RuntimeError("No knowledge index found. Run scripts\\ingest_documents.py first.")
