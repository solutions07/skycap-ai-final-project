import os
import pytest
from intelligent_agent import IntelligentAgent

KB_PATH = os.getenv('SKYCAP_KB_PATH', 'master_knowledge_base.json')

@pytest.fixture(scope='module')
def agent():
    return IntelligentAgent(KB_PATH)

@pytest.mark.parametrize(
    'question', [
        "Who is the finance minister of Nigeria?",
        "Who is the Nigerian finance minister?",
    ]
)
def test_finance_minister_not_misclassified(agent, question):
    res = agent.ask(question)
    # Should not be MARKET_PRICE; likely UNKNOWN or GENERAL_FINANCE (fallback answer acceptable)
    assert res['intent'] not in ('MARKET_PRICE', 'FINANCIAL_METRIC'), res
    # Ensure we still return an answer (fallback path)
    assert res['answer']

@pytest.mark.parametrize(
    'question', [
        "What is dollar-cost averaging?",
        "Explain dollar cost averaging strategy",
    ]
)
def test_concept_dollar_cost_averaging(agent, question):
    res = agent.ask(question)
    # Should classify as GENERAL_FINANCE or CONCEPT; if not, ensure brain 3 answer detected
    assert res['intent'] in ('CONCEPT', 'GENERAL_FINANCE', 'UNKNOWN')
    # If unknown, provenance should not be market/financial
    if res['intent'] == 'UNKNOWN':
        assert res.get('provenance') in (None, 'general_knowledge', 'semantic', 'metadata', 'summary_synthesis')
    assert res['answer']

@pytest.mark.parametrize(
    'question', [
        "What is the share price?",
        "Give me the stock price",
        "Please tell me the price",
    ]
)
def test_generic_price_without_symbol_not_market_price(agent, question):
    res = agent.ask(question)
    # Intent should not incorrectly assert MARKET_PRICE without symbol
    assert res['intent'] != 'MARKET_PRICE', res
    # If answer references need for symbol, that's acceptable
    # Ensure we still produced some guidance
    assert res['answer']
