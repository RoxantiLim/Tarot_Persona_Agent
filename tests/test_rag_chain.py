from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.tarot_agent.documents import Document
from src.tarot_agent.rag_chain import rerank_documents, retrieve_context


def make_doc(
    chunk_id: str,
    score: float,
    status: str = "keep",
    weight: float = 1.0,
    page: int = 1,
) -> Document:
    return Document(
        page_content=f"{chunk_id} 塔罗解释",
        metadata={
            "chunk_id": chunk_id,
            "source_file": "book.pdf",
            "page": page,
            "quality_status": status,
            "retrieval_weight": weight,
            "retrieval_score": score,
        },
    )


class FakeStore:
    def __init__(self, docs: list[Document]):
        self.docs = docs
        self.requested_k = 0

    def similarity_search(self, query: str, k: int = 5) -> list[Document]:
        self.requested_k = k
        return self.docs[:k]


class RagRerankTests(unittest.TestCase):
    def test_knowledge_profile_applies_downrank_weight(self) -> None:
        docs = [
            make_doc("downranked", 0.95, "downrank", 0.45),
            make_doc("kept", 0.60),
        ]
        ranked = rerank_documents(docs, top_k=2)
        self.assertEqual(["kept", "downranked"], [doc.metadata["chunk_id"] for doc in ranked])

    def test_agent_profile_prefers_keep_before_downrank(self) -> None:
        docs = [
            make_doc("downranked", 0.99, "downrank", 0.45),
            make_doc("kept-a", 0.20, page=2),
            make_doc("kept-b", 0.10, page=3),
        ]
        ranked = rerank_documents(docs, top_k=2, profile="agent")
        self.assertEqual(["kept-a", "kept-b"], [doc.metadata["chunk_id"] for doc in ranked])

    def test_agent_profile_supplements_downrank_when_needed(self) -> None:
        docs = [
            make_doc("downranked", 0.99, "downrank", 0.45),
            make_doc("kept", 0.20, page=2),
        ]
        ranked = rerank_documents(docs, top_k=2, profile="agent")
        self.assertEqual(["kept", "downranked"], [doc.metadata["chunk_id"] for doc in ranked])

    def test_limits_chunks_from_same_page(self) -> None:
        docs = [
            make_doc("same-a", 0.9),
            make_doc("same-b", 0.8),
            make_doc("same-c", 0.7),
            make_doc("other", 0.6, page=2),
        ]
        ranked = rerank_documents(docs, top_k=3)
        self.assertEqual(["same-a", "same-b", "other"], [doc.metadata["chunk_id"] for doc in ranked])

    def test_vector_and_keyword_paths_share_reranking(self) -> None:
        rows = [
            make_doc("downranked", 0.0, "downrank", 0.10),
            make_doc("kept", 0.0, "keep", 1.0, page=2),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_file = Path(temp_dir) / "indexes" / "local_vectors" / "documents.jsonl"
            docs_file.parent.mkdir(parents=True)
            with docs_file.open("w", encoding="utf-8") as f:
                for doc in rows:
                    f.write(json.dumps({"page_content": doc.page_content, "metadata": doc.metadata}) + "\n")

            keyword_config = SimpleNamespace(retrieval_mode="keyword", data_dir=Path(temp_dir))
            with patch("src.tarot_agent.rag_chain.index_exists", return_value=True):
                keyword_docs = retrieve_context(keyword_config, "塔罗", top_k=2)

            vector_docs = [
                make_doc("downranked", 10.0, "downrank", 0.10),
                make_doc("kept", 2.0, "keep", 1.0, page=2),
            ]
            store = FakeStore(vector_docs)
            vector_config = SimpleNamespace(retrieval_mode="vector")
            with (
                patch("src.tarot_agent.rag_chain.index_exists", return_value=True),
                patch("src.tarot_agent.rag_chain.load_vector_store", return_value=store),
            ):
                selected_vector_docs = retrieve_context(vector_config, "塔罗", top_k=2)

        self.assertEqual("kept", keyword_docs[0].metadata["chunk_id"])
        self.assertEqual("kept", selected_vector_docs[0].metadata["chunk_id"])
        self.assertEqual(8, store.requested_k)


if __name__ == "__main__":
    unittest.main()
