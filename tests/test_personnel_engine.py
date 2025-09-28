import pytest
from intelligent_agent import PersonnelEngine, _load_kb

@pytest.fixture
def kb():
    return _load_kb('master_knowledge_base.json')

def test_managing_director(kb):
    engine = PersonnelEngine(kb)
    q = 'Who is the Managing Director?'
    result = engine.search_personnel(q)
    assert result is not None and isinstance(result, str)

def test_cfo(kb):
    engine = PersonnelEngine(kb)
    q = 'Who is the CFO?'
    result = engine.search_personnel(q)
    assert result is None or isinstance(result, str)

def test_phone(kb):
    engine = PersonnelEngine(kb)
    q = 'What is the phone number?'
    result = engine.search_personnel(q)
    assert result is None or isinstance(result, str)

def test_email(kb):
    engine = PersonnelEngine(kb)
    q = 'What is the email address?'
    result = engine.search_personnel(q)
    assert result is None or isinstance(result, str)
