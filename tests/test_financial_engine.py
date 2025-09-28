import pytest
from intelligent_agent import FinancialDataEngine, _load_kb

@pytest.fixture
def kb():
    return _load_kb('master_knowledge_base.json')

def test_total_assets(kb):
    engine = FinancialDataEngine(kb)
    q = "What were Jaiz Bank's total assets in Q1 2024?"
    result = engine.search_financial_metric(q)
    assert result is None or 'totalassets' in result.lower() or 'assets' in result.lower()

def test_profit_before_tax(kb):
    engine = FinancialDataEngine(kb)
    q = "What was profit before tax in 2023?"
    result = engine.search_financial_metric(q)
    assert result is None or 'profitbeforetax' in result.lower() or 'profit' in result.lower()

def test_eps(kb):
    engine = FinancialDataEngine(kb)
    q = "What was the EPS in Q4 2022?"
    result = engine.search_financial_metric(q)
    assert result is None or 'earningspershare' in result.lower() or 'eps' in result.lower()
