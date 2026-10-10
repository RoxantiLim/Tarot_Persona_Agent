from __future__ import annotations

import os
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from src.tarot_agent.config import AppConfig
from src.tarot_agent.documents import Document
from src.tarot_agent.embeddings import ApiEmbeddings
from src.tarot_agent.vector_store import (
    LocalVectorStore, _publish_indexes, build_vector_store, validate_local_index,
)


def config_for(path: Path) -> AppConfig:
    with patch.dict(os.environ, {}, clear=True), patch("src.tarot_agent.config.load_dotenv"):
        config = AppConfig.load()
    return replace(
        config, data_dir=path, local_index_dir=path / "api_vectors", chroma_dir=path / "chroma",
        embedding_provider="api", embedding_api_key="test-only", embedding_batch_size=2,
        vector_store_backend="numpy", build_chroma=False,
    )


def response(*vectors):
    return SimpleNamespace(data=[SimpleNamespace(index=i, embedding=v) for i, v in enumerate(vectors)])


class ApiEmbeddingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = config_for(Path(self.temp.name))

    def test_batches_reorders_and_normalizes_without_loading_local_models(self):
        with patch("openai.OpenAI") as client, patch.dict("sys.modules", {"torch": None, "sentence_transformers": None, "transformers": None}):
            batch = response([3, 4], [0, 2])
            batch.data.reverse()
            client.return_value.embeddings.create.side_effect = [batch, response([2, 0])]
            vectors = ApiEmbeddings(self.config).embed_documents(["a", "b", "c"])
            np.testing.assert_allclose(vectors, [[0.6, 0.8], [0, 1], [1, 0]], atol=1e-6)
            self.assertEqual([['a', 'b'], ['c']], [call.kwargs['input'] for call in client.return_value.embeddings.create.call_args_list])

    def test_missing_key_fails_before_creating_client(self):
        with patch("openai.OpenAI") as client:
            with self.assertRaisesRegex(RuntimeError, "EMBEDDING_API_KEY"):
                ApiEmbeddings(replace(self.config, embedding_api_key=""))
            client.assert_not_called()

    def test_rejects_missing_duplicate_and_nonfinite_vectors(self):
        duplicate = response([1, 0], [0, 1])
        duplicate.data[1].index = 0
        invalid = [response([1, 0]), duplicate, response([float('nan'), 1], [1, 0]), response([0, 0], [1, 0])]
        for value in invalid:
            with self.subTest(value=value), patch("openai.OpenAI") as client:
                client.return_value.embeddings.create.return_value = value
                with self.assertRaises(ValueError):
                    ApiEmbeddings(self.config).embed_documents(["a", "b"])

    def test_api_errors_do_not_expose_upstream_credentials(self):
        with patch("openai.OpenAI") as client:
            client.return_value.embeddings.create.side_effect = RuntimeError("Authorization: Bearer private-value")
            with self.assertRaises(RuntimeError) as error:
                ApiEmbeddings(self.config).embed_query("hello")
            self.assertNotIn("private-value", str(error.exception))


class ApiIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = config_for(self.root)
        self.docs = [Document(page_content="one", metadata={"chunk_id": "one"}), Document(page_content="two", metadata={"chunk_id": "two"})]

    def build(self):
        embeddings = Mock()
        embeddings.embed_documents.return_value = [[1, 0], [0, 1]]
        embeddings.embed_query.return_value = [1, 0]
        with patch("src.tarot_agent.vector_store.create_embeddings", return_value=embeddings):
            store = build_vector_store(self.config, self.docs)
        store.vectors._mmap.close()
        return embeddings

    def test_successful_build_and_query_preserve_original_local_index(self):
        original = self.root / "indexes" / "local_vectors"
        original.mkdir(parents=True)
        marker = original / "vectors.npy"
        marker.write_bytes(b"old-local-index")
        embeddings = self.build()
        self.assertEqual(2, validate_local_index(self.config)['count'])
        with patch("src.tarot_agent.vector_store.create_embeddings", return_value=embeddings):
            store = LocalVectorStore(self.config)
            self.assertEqual("one", store.similarity_search("hello", 1)[0].page_content)
            store.vectors._mmap.close()
        self.assertEqual(b"old-local-index", marker.read_bytes())

    def test_embedding_or_staging_failure_preserves_existing_api_index(self):
        self.build()
        path = self.config.local_index_dir / "vectors.npy"
        original = path.read_bytes()
        failing = Mock()
        failing.embed_documents.side_effect = RuntimeError("API unavailable")
        with patch("src.tarot_agent.vector_store.create_embeddings", return_value=failing):
            with self.assertRaisesRegex(RuntimeError, "API unavailable"):
                build_vector_store(self.config, self.docs)
        self.assertEqual(original, path.read_bytes())
        good = Mock()
        good.embed_documents.return_value = [[0, 1], [1, 0]]
        with patch("src.tarot_agent.vector_store.create_embeddings", return_value=good), patch("src.tarot_agent.vector_store._write_numpy_store", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                build_vector_store(self.config, self.docs)
        self.assertEqual(original, path.read_bytes())

    def test_second_directory_publish_failure_restores_both_originals(self):
        targets = [self.root / "target-a", self.root / "target-b"]
        sources = [self.root / "source-a", self.root / "source-b"]
        for target in targets:
            target.mkdir()
            (target / "marker").write_text("old")
        for source in sources:
            source.mkdir()
            (source / "marker").write_text("new")
        rename = Path.rename
        def fail_second(path, target):
            if path == sources[1]:
                raise OSError("publish failed")
            return rename(path, target)
        with patch.object(Path, "rename", fail_second), self.assertRaises(OSError):
            _publish_indexes(list(zip(sources, targets)))
        self.assertEqual(["old", "old"], [(target / "marker").read_text() for target in targets])

    def test_old_or_different_provider_model_and_endpoint_index_is_rejected(self):
        self.build()
        for changed in [replace(self.config, embedding_model="another-model"), replace(self.config, embedding_provider="local"), replace(self.config, embedding_base_url="https://another.example/v1")]:
            with self.subTest(changed=changed.embedding_model), self.assertRaisesRegex(RuntimeError, "index mismatch"):
                validate_local_index(changed)
        (self.config.local_index_dir / "manifest.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "index mismatch"):
            validate_local_index(self.config)

    def test_rebuild_retains_previous_api_directory_as_backup(self):
        self.build()
        self.build()
        backups = list(self.root.glob("api_vectors.backup-*"))
        self.assertEqual(1, len(backups))
        self.assertTrue((backups[0] / "manifest.json").exists())

    def test_invalid_document_records_are_rejected_before_deployment(self):
        self.build()
        documents = self.config.local_index_dir / "documents.jsonl"
        for bad_record in [[], {"page_content": "", "metadata": {}}, {"page_content": "text", "metadata": "wrong"}]:
            with self.subTest(record=bad_record):
                documents.write_text(json.dumps(bad_record) + '\n' + json.dumps({"page_content": "two", "metadata": {}}) + '\n')
                with self.assertRaises(ValueError):
                    validate_local_index(self.config)


if __name__ == "__main__":
    unittest.main()
