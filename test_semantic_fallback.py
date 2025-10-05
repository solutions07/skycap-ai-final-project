import json
import tempfile
import unittest
from unittest import mock

from intelligent_agent import IntelligentAgent


class TestSemanticFallback(unittest.TestCase):
    def setUp(self):
        # Minimal KB with no data to satisfy constructor and force fallbacks
        self.kb_data = {
            "financial_reports": [],
            "market_data": [],
            "client_profile": {}
        }
        # Create a temporary KB file
        self.tmp = tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False)
        json.dump(self.kb_data, self.tmp)
        self.tmp.flush()
        self.kb_path = self.tmp.name

    def tearDown(self):
        try:
            self.tmp.close()
        except Exception:
            pass

    def test_semantic_search_fallback_is_used(self):
        # Stub SemanticSearcher to avoid loading models or index files
        class StubSearcher:
            def __init__(self, *args, **kwargs):
                pass
            def available(self):
                return True
            def search(self, query, k=1):
                return [(0.99, {"text": "Mocked semantic answer"})]

        with mock.patch("intelligent_agent.SemanticSearcher", new=StubSearcher):
            agent = IntelligentAgent(self.kb_path)
            # Ask a question that should not be answered by any specific engine
            q = "Tell me something unrelated that is not in the structured engines"
            res = agent.ask(q)
            self.assertIsInstance(res, dict)
            self.assertEqual(res.get("provenance"), "SemanticSearchFallback")
            self.assertEqual(res.get("answer"), "Mocked semantic answer")


if __name__ == "__main__":
    unittest.main()