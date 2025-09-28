import pytest
from intelligent_agent import MetadataEngine, _load_kb

@pytest.fixture
def kb():
    return _load_kb('master_knowledge_base.json')

def test_financial_report_count(kb):
    engine = MetadataEngine(kb)
    q = 'How many financial reports are in the knowledge base?'
    assert 'financial reports' in engine.search(q)

def test_market_data_count(kb):
    engine = MetadataEngine(kb)
    q = 'How many market data records are in the knowledge base?'
    assert 'market data records' in engine.search(q)

def test_data_sources(kb):
    engine = MetadataEngine(kb)
    q = 'What are the data sources?'
    result = engine.search(q)
    assert result is None or 'Data sources:' in result
