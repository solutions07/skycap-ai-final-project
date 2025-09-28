import json
import os
import pytest

from intelligent_agent import IntelligentAgent

KB_PATH = os.getenv('SKYCAP_KB_PATH', 'master_knowledge_base.json')

@pytest.fixture(scope='module')
def agent():
    return IntelligentAgent(KB_PATH)

@pytest.mark.parametrize(
    'question,expected_intent,expected_provenance_fragment', [
        ("Latest market news today", 'NEWS', 'web_analysis'),
        ("What was the share price of JAIZBANK?", 'MARKET_PRICE', 'market'),
        ("What were Jaiz Bank's total assets in 2023?", 'FINANCIAL_METRIC', 'financial'),
        ("Who is the managing director of Skyview Capital?", 'PERSONNEL', 'personnel'),
        ("Give me a company overview of Skyview Capital", 'COMPANY_PROFILE', 'metadata'),
        ("Provide a financial performance summary", 'SUMMARY', 'summary_synthesis'),
        ("What is earnings per share?", 'CONCEPT', 'general_knowledge'),
    ]
)
def test_intent_classification_and_routing(agent, question, expected_intent, expected_provenance_fragment):
    res = agent.ask(question)
    assert res.get('intent') == expected_intent
    assert res.get('answer'), 'Answer should not be empty'
    prov = res.get('provenance') or ''
    assert expected_provenance_fragment in prov
    assert 'source_citation' in res and res['source_citation'], 'Citation required'


def test_unknown_intent_fallback(agent):
    res = agent.ask('Tell me something entirely unrelated to dataset quantum flux')
    # Should either classify as UNKNOWN and attempt fallbacks resulting in some default response
    assert res.get('answer')
    assert 'response_time' in res


def test_citation_presence_all_brains(agent):
    queries = [
        'Latest market news today',  # Brain 2
        "What were Jaiz Bank's total assets in 2023?",  # Brain 1 structured
        'What is earnings per share?',  # Brain 3
    ]
    for q in queries:
        res = agent.ask(q)
        assert res.get('source_citation'), f'Missing citation for {q}'
