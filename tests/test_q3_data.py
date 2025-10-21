from typing import Iterable

import pytest

from intelligent_agent import IntelligentAgent

KB_PATH = "data/master_knowledge_base.json"
FAILURE_TOKENS: Iterable[str] = (
    "don't have",
    "insufficient data",
    "try rephrasing",
    "unable to",
    "error",
)


@pytest.fixture(scope="module")
def financial_agent() -> IntelligentAgent:
    return IntelligentAgent(kb_path=KB_PATH)


@pytest.mark.parametrize(
    "question, expected_tokens",
    [
        (
            "What was the return on equity for Q3 2024?",
            ("return on equity", "q3 2024", "2024-09-30"),
        ),
        (
            "Find the Net Revenue from Funds for the third quarter of 2024.",
            ("net revenue from funds", "₦14.605", "2024-09-30"),
        ),
        (
            "What was the Profit After Tax for Jaiz Bank in Q3 2024?",
            ("profit after tax", "₦5.517", "2024-09-30"),
        ),
        (
            "Show me the credit impairment charges for the 3rd quarter of 2024.",
            ("credit impairment charges", "₦-1,886", "2024-09-30"),
        ),
    ],
)
def test_q3_metric_lookups(financial_agent: IntelligentAgent, question: str, expected_tokens):
    response = financial_agent.ask(question)
    answer = response.get("answer", "")
    normalized = " ".join(answer.split())
    lower_answer = normalized.lower()

    assert normalized, f"Empty answer returned for question: {question}"
    for token in FAILURE_TOKENS:
        assert token not in lower_answer, f"Unexpected fallback for question: {question}"

    for token in expected_tokens:
            assert token.lower() in lower_answer, f"Missing token '{token}' in answer: {normalized}"