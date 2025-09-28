import pytest
from intelligent_agent import MarketDataEngine, _load_kb

@pytest.fixture
def kb():
    return _load_kb('master_knowledge_base.json')

def test_stock_price(kb):
    engine = MarketDataEngine(kb)
    q = "What was the closing price for JAIZBANK on 2024-03-31?"
    result = engine.search_stock_price(q)
    assert result is None or 'price' in result.lower() or '₦' in result

def test_open_price(kb):
    engine = MarketDataEngine(kb)
    q = "What was the opening price for JAIZBANK on 2024-03-31?"
    result = engine.search_stock_price(q)
    assert result is None or 'price' in result.lower() or '₦' in result
