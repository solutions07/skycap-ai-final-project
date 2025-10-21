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
            "How did Gross Earnings for Jaiz Bank change from year-end 2023 to year-end 2024?",
            ("comparative analysis", "2023-12-31", "2024-12-31", "growth"),
        ),
        (
            "What was the Earnings Per Share for Jaiz Bank in their 2018 annual report?",
            ("earnings per share", "2018-12-31", "audited financial statement"),
        ),
        (
            "Tell me about a testimonial from Emmanuel Oladimeji.",
            ("awesome support", "financial service"),
        ),
    ],
)
def test_final_critical_regressions(financial_agent: IntelligentAgent, question: str, expected_tokens):
    response = financial_agent.ask(question)
    answer = response.get("answer", "")
    normalized = " ".join(answer.split())
    lower_answer = normalized.lower()

    assert normalized, f"Empty answer returned for question: {question}"
    for token in FAILURE_TOKENS:
        assert token not in lower_answer, f"Unexpected fallback for question: {question}"

    for token in expected_tokens:
        assert token.lower() in lower_answer, f"Missing token '{token}' in answer: {normalized}"