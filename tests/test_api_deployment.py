from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.tarot_agent.config import AppConfig
from src.tarot_agent.agent_graph import run_persona_reading


class DeploymentApiTests(unittest.TestCase):
    def setUp(self):
        with patch.dict(os.environ, {}, clear=True), patch("src.tarot_agent.config.load_dotenv"):
            from api import main
            self.config = AppConfig.load()
        self.main = main
        self.main._request_times.clear()
        self.config = replace(self.config, api_access_token="demo-test-token")
        patcher = patch("api.main.get_config", return_value=self.config)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(self.main.app)

    def test_token_protects_endpoints_and_cors_preflight_remains_available(self):
        self.assertEqual(401, self.client.get('/api/cards').status_code)
        headers = {'Authorization': 'Bearer demo-test-token'}
        self.assertEqual(200, self.client.get('/api/cards', headers=headers).status_code)
        response = self.client.options('/api/cards', headers={'Origin': 'http://localhost:3000', 'Access-Control-Request-Method': 'GET'})
        self.assertEqual(200, response.status_code)
        self.assertEqual('http://localhost:3000', response.headers.get('access-control-allow-origin'))

    def test_rate_limit_rejects_before_second_model_request(self):
        headers = {'Authorization': 'Bearer demo-test-token'}
        with patch.dict(os.environ, {'API_REQUESTS_PER_MINUTE': '1'}), patch('api.main.retrieve_context', return_value=[]) as retrieve:
            first = self.client.post('/api/knowledge/query', json={'mode': '资料检索', 'query': 'hello'}, headers=headers)
            second = self.client.post('/api/knowledge/query', json={'mode': '资料检索', 'query': 'hello'}, headers=headers)
        self.assertEqual(200, first.status_code)
        self.assertEqual(429, second.status_code)
        self.assertEqual(1, retrieve.call_count)

    def test_api_mode_health_detects_missing_key_and_index_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            config = replace(self.config, data_dir=Path(directory), local_index_dir=Path(directory) / 'api_vectors', embedding_provider='api', embedding_api_key='', vector_store_backend='numpy')
            with patch('api.main.get_config', return_value=config):
                response = self.client.get('/api/health')
        self.assertEqual(200, response.status_code)
        self.assertFalse(response.json()['embedding_configured'])
        self.assertFalse(response.json()['index_compatible'])
        self.assertNotIn('demo-test-token', response.text)

    def test_runtime_graph_failure_does_not_repeat_paid_generation(self):
        with patch('src.tarot_agent.agent_graph.retrieve_context', return_value=[]), patch('src.tarot_agent.agent_graph.retrieve_similar_cases', return_value=[]), patch('src.tarot_agent.agent_graph.deepseek_chat', side_effect=RuntimeError('upstream failed')) as generate:
            with self.assertRaisesRegex(RuntimeError, 'upstream failed'):
                run_persona_reading(self.config, 'tarotist_1', 'hello', [{'name': '隐士', 'orientation': '正位'}], include_check=False)
            self.assertEqual(1, generate.call_count)


if __name__ == '__main__':
    unittest.main()
