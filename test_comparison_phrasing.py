import unittest

from intelligent_agent import FinancialDataEngine


class TestComparisonPhrasing(unittest.TestCase):
    def test_how_did_change_from_year_to_year(self):
        kb = {
            "financial_reports": [
                {"report_metadata": {"report_date": "2021-12-31", "metrics": {"Total Assets": 200_000_000}}},
                {"report_metadata": {"report_date": "2022-12-31", "metrics": {"Total Assets": 300_000_000}}},
            ]
        }
        engine = FinancialDataEngine(kb)
        q = "How did the total assets change from 2021 to 2022?"
        ans = engine.search_financial_metric(q)
        self.assertIsInstance(ans, str)
        self.assertIn("Comparing", ans)
        self.assertIn("2021", ans)
        self.assertIn("2022", ans)


if __name__ == '__main__':
    unittest.main()