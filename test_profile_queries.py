import unittest

from intelligent_agent import CompanyProfileEngine


class TestProfileQueries(unittest.TestCase):
    def setUp(self):
        # Minimal KB slice reflecting client profile lines used by the engine
        self.kb = {
            "client_profile": {
                "skyview knowledge pack": {
                    "company overview": [
                        "Skyview Capital Limited is a full-service capital markets firm.",
                        "We provide research and advisory.",
                        "Stated Philosophy/Mission: \"Understand that excellent service...\""
                    ],
                    "services offered by skyview capital limited": [
                        "Retainerships for listed companies",
                        "Receiving Agency for IPOs",
                        "Asset valuation tooling"
                    ],
                    # Free-form text lines used by the logic to extract answers
                    "misc": [
                        "Clientele: Government parastatals, multinational and indigenous companies, high net worth individuals.",
                        "Report types mentioned: Skyview Research Report, Weekly, Monthly, Quarterly, Annual Reports."
                    ]
                }
            }
        }
        self.engine = CompanyProfileEngine(self.kb)

    def test_client_types_answer(self):
        q = "What types of clients does Skyview Capital serve?"
        ans = self.engine.search_profile_info(q)
        self.assertIsInstance(ans, str)
        self.assertIn("Government parastatals", ans)
        self.assertIn("high net worth individuals", ans)

    def test_research_report_types_answer(self):
        q = "What types of research reports does Skyview Research provide?"
        ans = self.engine.search_profile_info(q)
        self.assertIsInstance(ans, str)
        self.assertIn("Weekly", ans)
        self.assertIn("Quarterly", ans)


if __name__ == '__main__':
    unittest.main()