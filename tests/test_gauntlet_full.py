import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pytest

from intelligent_agent import IntelligentAgent

KB_PATH = Path("data/master_knowledge_base.json")
DEFAULT_QUESTIONS_PATH = Path("data/gauntlet_questions_full.json")
FAILURE_PATTERNS = [
    "i couldn't find a specific answer",
    "external search is unavailable",
    "please try rephrasing",
    "i don't have enough information",
    "unable to complete the comparison",
    "insufficient data found",
]


def _load_questions(path: Path) -> List[str]:
    """Load gauntlet questions from JSON or derive defaults from the KB."""
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "questions" in data:
            return [str(q) for q in data["questions"]]
        if isinstance(data, list):
            return [str(q) for q in data]
        raise ValueError("Unsupported questions file format: expected list or {'questions': [...]}.")

    kb = json.loads(KB_PATH.read_text(encoding="utf-8"))
    questions: List[str] = []
    for report in kb.get("financial_reports", []):
        meta = report.get("report_metadata", {})
        date = meta.get("report_date")
        if not isinstance(date, str) or len(date) < 4:
            continue
        year = date[:4]
        questions.extend(
            [
                f"What were the total assets for Jaiz Bank in {year}?",
                f"What was the profit before tax for Jaiz Bank in {year}?",
                f"What were the gross earnings for Jaiz Bank in {year}?",
                f"What was the earnings per share for Jaiz Bank in {year}?",
            ]
        )

    symbols = {
        entry.get("symbol")
        for entry in kb.get("market_data", [])
        if isinstance(entry, dict) and entry.get("symbol")
    }
    for symbol in sorted(sym for sym in symbols if sym and len(sym) >= 3):
        questions.append(f"What is the price of {symbol}?")

    questions.extend(
        [
            "Who created SkyCap AI?",
            "List key team members at Skyview Capital Limited",
            "What services does Skyview Capital provide?",
            "What is the official phone number for Skyview Capital?",
            "Where is the head office of Skyview Capital located?",
            "How many financial reports are available?",
            "What is the date range covered by the financial reports?",
        ]
    )

    deduped: List[str] = []
    seen = set()
    for question in questions:
        if question not in seen:
            deduped.append(question)
            seen.add(question)
    return deduped


def _run_gauntlet(agent: IntelligentAgent, questions: List[str], out_path: Path) -> Dict[str, Any]:
    """Execute the gauntlet suite and persist the structured report."""
    failures: List[Dict[str, Any]] = []
    results: List[Dict[str, Any]] = []

    for idx, question in enumerate(questions, 1):
        try:
            response = agent.ask(question)
        except Exception as exc:  # pragma: no cover - defensive guardrail
            answer = f"Exception: {exc}"
            provenance = "exception"
            brain_used = "N/A"
        else:
            answer = str(response.get("answer", "")).strip()
            provenance = response.get("provenance")
            brain_used = response.get("brain_used")

        lower_answer = answer.lower()
        failed = not answer or any(pattern in lower_answer for pattern in FAILURE_PATTERNS)
        if failed:
            failures.append({"question": question, "answer": answer})

        results.append(
            {
                "n": idx,
                "question": question,
                "answer": answer,
                "brain_used": brain_used,
                "provenance": provenance,
                "pass": not failed,
            }
        )

    report: Dict[str, Any] = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "kb_path": str(KB_PATH),
        "total": len(questions),
        "passed": sum(1 for r in results if r["pass"]),
        "failed": len(failures),
        "results": results,
    }

    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if failures:
        report["failures"] = failures
    return report


@pytest.mark.gauntlet
def test_gauntlet_full_suite(tmp_path):
    questions = _load_questions(DEFAULT_QUESTIONS_PATH)
    assert questions, "Gauntlet question set resolved to an empty list."

    agent = IntelligentAgent(str(KB_PATH))
    report_path = tmp_path / "gauntlet_report.json"
    report = _run_gauntlet(agent, questions, report_path)

    assert report_path.exists(), "Gauntlet report file not written."  # ensure parity with prior workflow
    assert report["total"] == len(questions)
    assert report["passed"] + report["failed"] == report["total"]

    if report.get("failed"):
        sample = report.get("failures", [])[:5]
        formatted = "\n".join(
            f"- {item['question']} -> {item['answer'][:200]}" for item in sample
        )
        pytest.fail(
            f"Gauntlet validation failed for {report['failed']} of {report['total']} questions:\n{formatted}"
        )