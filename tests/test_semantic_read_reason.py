"""Test suite for Task 2: Read-and-Reason semantic fallback.

Validates that semantic fallback returns:
- Natural language answers (no raw JSON braces '{' or '}')
- Professional tone and presence of confidence qualifier
- Key concept coverage for representative queries
"""
from __future__ import annotations
import re
import pytest
from intelligent_agent import IntelligentAgent

QUERIES = [
    ("Tell me about Skyview Capital company", ["skyview", "financial"], []),
    ("Describe Skyview Capital services", ["services", "financial"], []),
    ("What can you tell me about Skyview financial performance?", ["financial", "report"], []),
]

CONFIDENCE_PATTERN = re.compile(r"confidence", re.I)


def _invoke_semantic(agent: IntelligentAgent, query: str) -> str:
    # Directly leverage semantic fallback to avoid interference from rule-based engines
    answer = agent.semantic.query(query) if agent.semantic else None
    if not answer:
        pytest.fail(f"Semantic fallback did not return an answer for query: {query}")
    return answer


def test_semantic_read_and_reason_outputs_natural_language():
    agent = IntelligentAgent()
    # Ensure semantic model loaded (skip test if not available) – this environment may not have STS model
    if not agent.semantic:
        pytest.skip("Semantic model not available in environment")

    for q, must_phrases, forbidden in QUERIES:
        ans = _invoke_semantic(agent, q)
        # Assert no raw JSON braces
        assert '{' not in ans and '}' not in ans, f"Raw JSON leakage for query: {q}\nAnswer: {ans}"

        # Professional sentence structure heuristic: at least one period and > 40 chars
        assert len(ans) > 40 and '.' in ans, f"Answer too short/unstructured: {ans}"

        # Confidence qualifier present
        assert CONFIDENCE_PATTERN.search(ans), f"Confidence qualifier missing: {ans}"

        # Key phrase presence (case-insensitive simple containment)
        lower_ans = ans.lower()
        for phrase in must_phrases:
            assert phrase in lower_ans, f"Expected phrase '{phrase}' missing in answer: {ans}"
        for forb in forbidden:
            assert forb not in lower_ans, f"Forbidden phrase '{forb}' should not appear: {ans}"
