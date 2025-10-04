import unittest

from intelligent_agent import FinancialDataEngine


class TestComparisonHardening(unittest.TestCase):
    def test_valid_comparison_two_years(self):
        kb = {
            "financial_reports": [
                {"report_metadata": {"report_date": "2022-12-31", "metrics": {"Total Assets": 1_000_000_000}}},
                {"report_metadata": {"report_date": "2023-12-31", "metrics": {"Total Assets": 1_500_000_000}}},
                # An irrelevant/malformed entry should be ignored gracefully
                {"report_metadata": {"report_date": "2024-12-31", "metrics": {"Total Assets": "N/A"}}},
            ]
        }
        engine = FinancialDataEngine(kb)
        q = "Compare the total assets between 2022 and 2023."
        answer = engine.search_financial_metric(q)
        self.assertIsInstance(answer, str)
        self.assertIn("Comparing", answer)
        self.assertIn("2022", answer)
        self.assertIn("2023", answer)

    def test_missing_year_returns_safe_message(self):
        kb = {
            "financial_reports": [
                {"report_metadata": {"report_date": "2022-12-31", "metrics": {"Total Assets": 2_000_000_000}}}
            ]
        }
        engine = FinancialDataEngine(kb)
        q = "Compare total assets between 2022 and 2023."
        answer = engine.search_financial_metric(q)
        self.assertIsInstance(answer, str)
        self.assertIn("Insufficient data", answer)

    def test_zero_baseline_message(self):
        kb = {
            "financial_reports": [
                {"report_metadata": {"report_date": "2022-12-31", "metrics": {"Total Assets": 0}}},
                {"report_metadata": {"report_date": "2023-12-31", "metrics": {"Total Assets": 100}}},
            ]
        }
        engine = FinancialDataEngine(kb)
        q = "Compare Total Assets between 2022 and 2023"
        answer = engine.search_financial_metric(q)
        self.assertIsInstance(answer, str)
        self.assertIn("went from ₦0", answer)


if __name__ == '__main__':
    unittest.main()
