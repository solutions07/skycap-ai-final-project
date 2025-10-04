import unittest
import json
from pathlib import Path

# Import the functions and classes to be tested
from extract_financials import _sanitize_metric_value
from intelligent_agent import MarketDataEngine

class TestPhase2Hardening(unittest.TestCase):

    def setUp(self):
        """Set up a dummy knowledge base for testing the agent."""
        self.dummy_kb = {
            "market_data": [
                {
                    "pricedate": "2025-09-17",
                    "symbol": "JAIZBANK",
                    "closingprice": 4.55
                }
            ]
        }
        self.market_engine = MarketDataEngine(self.dummy_kb)

    # Test Case 1: Financial Metric Sanity (SCALING FIX)
    def test_sanitize_rejects_implausible_large_metrics(self):
        """
        Validates that the scalar audit in extract_financials.py rejects
        nonsensically small values for major financial metrics.
        """
        # Total Assets should be very large
        self.assertIsNone(_sanitize_metric_value('total assets', 1.0), "Should reject 1.0 for total assets")
        self.assertIsNone(_sanitize_metric_value('total assets', 999999.0), "Should reject value below ASSET_MIN_VALUE")
        self.assertIsNotNone(_sanitize_metric_value('total assets', 1000000.0), "Should accept valid asset value")

        # PBT and Gross Earnings should be larger than a minimal threshold
        self.assertIsNone(_sanitize_metric_value('profit before tax', 24.0), "Should reject 24.0 for PBT")
        self.assertIsNone(_sanitize_metric_value('gross earnings', 82.0), "Should reject 82.0 for gross earnings")
        self.assertIsNotNone(_sanitize_metric_value('profit before tax', 10000.0), "Should accept valid PBT value")

    # Test Case 2: Intent Classifier Guardrail (ROUTING FIX)
    def test_market_engine_avoids_misclassification(self):
        """
        Validates that the tightened heuristic in intelligent_agent.py does not
        misclassify common words as stock tickers.
        """
        # These queries should NOT be interpreted as asking for a stock price.
        self.assertIsNone(self.market_engine.search_market_info("What is the concept of Islamic banking?"), "Should not match 'concept'")
        self.assertIsNone(self.market_engine.search_market_info("Tell me about Nigeria's economy"), "Should not match 'Nigeria'")
        self.assertIsNone(self.market_engine.search_market_info("What is the PRICE of oil?"), "Should not match 'PRICE'")

        # This query SHOULD be interpreted as asking for a stock price.
        self.assertIsNotNone(self.market_engine.search_market_info("What is the price of JAIZBANK?"), "Should match 'JAIZBANK'")


if __name__ == '__main__':
    unittest.main()