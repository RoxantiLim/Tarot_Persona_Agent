from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np

from scripts import prepare_modal_data
from src.tarot_agent.config import AppConfig
from src.tarot_agent.documents import Document
from src.tarot_agent.vector_store import _write_numpy_store


class ModalBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        with patch.dict(os.environ, {}, clear=True), patch('src.tarot_agent.config.load_dotenv'):
            config = AppConfig.load()
        self.config = replace(config, embedding_provider='api', embedding_api_key='', data_dir=self.root / 'data',
            local_index_dir=self.root / 'data/indexes/api_vectors', personas_dir=self.root / 'data/personas',
            cases_dir=self.root / 'data/cases', build_chroma=False, vector_store_backend='numpy')
        _write_numpy_store(self.config, [Document(page_content='synthetic knowledge', metadata={'chunk_id': 'one'})], np.array([[1, 0]], dtype=np.float32))
        self.config.personas_dir.mkdir()
        self.config.cases_dir.mkdir()
        (self.config.personas_dir / 'reader.json').write_text('{}')
        (self.config.cases_dir / 'one_reviewed.jsonl').write_text(json.dumps({'case': 'synthetic'}))
        (self.config.cases_dir / 'one_candidates.jsonl').write_text('must not copy')
        (self.root / '.env').write_text('private-api-key')
        (self.root / 'Doc').mkdir()
        (self.root / 'Doc/private.pdf').write_text('must not copy')
        self.bundle = self.root / 'data/deploy/modal'

    def prepare(self, *args):
        with patch.object(prepare_modal_data, 'ROOT', self.root), patch.object(AppConfig, 'load', return_value=self.config), patch('sys.argv', ['prepare_modal_data.py', *args]):
            prepare_modal_data.main()

    def test_explicit_bundle_excludes_secrets_raw_files_and_candidates_without_api_calls(self):
        self.prepare()
        paths = {file.relative_to(self.bundle).as_posix() for file in self.bundle.rglob('*') if file.is_file()}
        self.assertEqual({'indexes/api_vectors/vectors.npy', 'indexes/api_vectors/documents.jsonl', 'indexes/api_vectors/manifest.json', 'personas/reader.json', 'cases/one_reviewed.jsonl'}, paths)

    def test_invalid_reviewed_data_preserves_previous_bundle(self):
        self.prepare()
        original = (self.bundle / 'cases/one_reviewed.jsonl').read_bytes()
        (self.config.cases_dir / 'one_reviewed.jsonl').write_text('invalid json')
        with self.assertRaises(json.JSONDecodeError):
            self.prepare()
        self.assertEqual(original, (self.bundle / 'cases/one_reviewed.jsonl').read_bytes())

    def test_without_cases_removes_only_cases_from_new_bundle(self):
        self.prepare('--without-cases')
        self.assertFalse((self.bundle / 'cases').exists())
        self.assertTrue((self.bundle / 'personas/reader.json').exists())


if __name__ == '__main__':
    unittest.main()
