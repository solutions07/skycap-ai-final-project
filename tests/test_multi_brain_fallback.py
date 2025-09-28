import pytest
from intelligent_agent import IntelligentAgent

@pytest.fixture(scope="module")
def agent():
    return IntelligentAgent()

def test_brain2_live_web_simulated(agent):
    # Query that should trigger web analysis (news/current event style)
    q = "What is the latest stock market news today?"
    result = agent.ask(q)
    assert result['brain_used'] == 'Brain 2', f"Expected Brain 2, got {result['brain_used']} with answer: {result['answer']}"
    assert 'market' in result['answer'].lower() or 'news' in result['answer'].lower()

def test_brain3_general_knowledge(agent):
    # Query definitional concept not answered by local KB engines
    q = "Explain portfolio diversification principles"
    result = agent.ask(q)
    assert result['brain_used'] == 'Brain 3', f"Expected Brain 3, got {result['brain_used']}"
    assert 'diversification' in result['answer'].lower()
    assert 'risk' in result['answer'].lower()
