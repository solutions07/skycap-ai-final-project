import json
import os
import tempfile
import unittest

from intelligent_agent import IntelligentAgent


class DummySemanticSearcher:
    def __init__(self, *args, **kwargs):
        pass

    def available(self):
        return True

    def search(self, query, k=1):
        return [(0.99, {"text": "Semantic fallback OK"})]


class TestHybridBrainSemanticFallback(unittest.TestCase):
    def setUp(self):
        # Create a minimal KB that forces Brain 1 engines to return None
        self.tmpdir = tempfile.TemporaryDirectory()
        self.kb_path = os.path.join(self.tmpdir.name, 'kb.json')
        kb = {
            "financial_reports": [],
            "market_data": [],
            "client_profile": {"skyview knowledge pack": {}},
        }
        with open(self.kb_path, 'w', encoding='utf-8') as f:
            json.dump(kb, f)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_semantic_fallback_engaged(self):
        # Monkeypatch the SemanticSearcher in the agent module
        import intelligent_agent as ia
        original = getattr(ia, 'SemanticSearcher', None)
        try:
            ia.SemanticSearcher = DummySemanticSearcher  # type: ignore
            agent = IntelligentAgent(kb_path=self.kb_path)
            result = agent.ask("What is something unknown?")
            self.assertIsInstance(result, dict)
            self.assertEqual(result.get('provenance'), 'SemanticSearchFallback')
            self.assertIn('Semantic fallback OK', result.get('answer', ''))
        finally:
            ia.SemanticSearcher = original


if __name__ == '__main__':
    unittest.main()
