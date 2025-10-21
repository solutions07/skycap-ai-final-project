import re

import pytest

from intelligent_agent import IntelligentAgent


@pytest.fixture(scope="module")
def agent():
    return IntelligentAgent("data/master_knowledge_base.json")


def test_eps_query_returns_client_value(agent):
    response = agent.ask("What was the EPS for Jaizbank for full year 2023?")
    answer = response["answer"]
    assert "0.3253" in answer
    assert response["brain_used"] == "Brain 1"


def _extract_thousands_value(answer: str) -> float:
    match = re.search(r"₦([\d,.]+)\s*(Trillion|Billion|Million)?", answer)
    if not match:
        pytest.fail(f"Could not parse currency figure from answer: {answer}")
    numeric = float(match.group(1).replace(",", ""))
    unit = match.group(2)
    multiplier = 1.0
    if unit == "Million":
        multiplier = 1_000_000.0
    elif unit == "Billion":
        multiplier = 1_000_000_000.0
    elif unit == "Trillion":
        multiplier = 1_000_000_000_000.0
    actual_naira = numeric * multiplier
    return actual_naira / 1_000.0


def test_profit_after_tax_query_matches_expected_value(agent):
    response = agent.ask("What was the last profit after tax for Jaiz bank?")
    answer = response["answer"]
    thousands_value = _extract_thousands_value(answer)
    assert thousands_value == pytest.approx(11_237_187_000.0, rel=0, abs=2_000_000.0)
    assert response["brain_used"] == "Brain 1"
