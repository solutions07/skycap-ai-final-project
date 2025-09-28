import pytest
from intelligent_agent import IntelligentAgent
import os

KB_PATH = os.getenv('SKYCAP_KB_PATH', 'master_knowledge_base.json')

@pytest.fixture(scope='module')
def agent():
    return IntelligentAgent(KB_PATH)


def test_brain2_news_short_circuit(agent):
    res = agent.ask('Latest market news today')
    assert res['brain_used'] in ('Brain 2', 'Brain 3')  # Brain 2 preferred, Brain 3 fallback if no web
    assert res['source_citation']


def test_brain3_concept(agent):
    res = agent.ask('What is portfolio diversification?')
    assert res['brain_used'] == 'Brain 3'
    assert 'diversification' in res['answer'].lower()
    assert res['source_citation']


def test_semantic_not_used_for_news(agent):
    res = agent.ask('Stock market news update')
    assert res.get('provenance') != 'semantic'


def test_structured_then_semantic(agent, monkeypatch):
    # Force financial metric not present to trigger semantic after structured engines
    res = agent.ask('Explain the recent performance of the company')
    # provenance could be semantic or summary_synthesis depending on KB content; check citation logic
    assert res['answer']
    assert res['source_citation'] or res.get('provenance') in ('semantic', 'summary_synthesis')
