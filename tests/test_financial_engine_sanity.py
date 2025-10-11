import json
from intelligent_agent import FinancialDataEngine


def test_latest_metric_lookup_sanity():
    kb = {
        'financial_reports': [
            {
                'report_metadata': {
                    'report_date': '2024-12-31',
                    'metrics': {
                        'total assets': 1000.0,
                        'profit before tax': 50.0,
                        'gross earnings': 200.0,
                        'earnings per share': 1.2,
                    },
                }
            }
        ],
        'market_data': [
            {
                'symbol': 'JAIZBANK',
                'pricedate': '2025-01-10',
                'closingprice': 20.0,
            }
        ],
    }

    eng = FinancialDataEngine(kb)
    out = eng.search_financial_metric('What is the total assets?')
    assert 'The latest total assets is' in out
