import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from intelligent_agent import IntelligentAgent

KB_PATH = 'data/master_knowledge_base.json'
DEFAULT_QUESTIONS_PATH = 'data/gauntlet_questions_full.json'
REPORT_PATH = 'gauntlet_report.json'

# Failure phrases to flag generic or fallback responses
FAILURE_PATTERNS = [
    "I couldn't find a specific answer",
    "external search is unavailable",
    "please try rephrasing",
    "I don't have enough information",
    "Unable to complete the comparison",
    "Insufficient data found",
]


def load_questions(path: str) -> List[str]:
    p = Path(path)
    if p.exists():
        with p.open('r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict) and 'questions' in data:
                return [str(q) for q in data['questions']]
            if isinstance(data, list):
                return [str(q) for q in data]
            raise ValueError("Unsupported questions file format: expected list or { 'questions': [...] }")
    # If no external file provided, derive a basic set from KB as fallback
    with open(KB_PATH, 'r', encoding='utf-8') as f:
        kb = json.load(f)
    questions: List[str] = []
    # Financial metrics per year
    for report in kb.get('financial_reports', []):
        meta = report.get('report_metadata', {})
        date = meta.get('report_date')
        if not date:
            continue
        year = date[:4]
        questions.extend([
            f"What were the total assets for Jaiz Bank in {year}?",
            f"What was the profit before tax for Jaiz Bank in {year}?",
            f"What were the gross earnings for Jaiz Bank in {year}?",
            f"What was the earnings per share for Jaiz Bank in {year}?",
        ])
    # Market data
    symbols = {d.get('symbol') for d in kb.get('market_data', []) if d.get('symbol')}
    for sym in sorted(s for s in symbols if s and len(s) >= 3):
        questions.append(f"What is the price of {sym}?")
    # Profile & general
    questions.extend([
        "Who created SkyCap AI?",
        "List key team members at Skyview Capital Limited",
        "What services does Skyview Capital provide?",
        "What is the official phone number for Skyview Capital?",
        "Where is the head office of Skyview Capital located?",
        "How many financial reports are available?",
        "What is the date range covered by the financial reports?",
    ])
    # De-duplicate while preserving order
    seen = set()
    out = []
    for q in questions:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


def run_gauntlet(questions: List[str], out_path: str = REPORT_PATH) -> Dict[str, Any]:
    agent = IntelligentAgent(KB_PATH)
    results: List[Dict[str, Any]] = []

    failures = 0
    for idx, q in enumerate(questions, 1):
        try:
            res = agent.ask(q)
        except Exception as e:
            res = {
                'answer': f"Exception: {e}",
                'brain_used': 'N/A',
                'provenance': 'Exception'
            }
        answer = str(res.get('answer', '')).strip()
        brain = res.get('brain_used')
        provenance = res.get('provenance')
        failed = any(p.lower() in answer.lower() for p in FAILURE_PATTERNS)
        if failed:
            failures += 1
        results.append({
            'n': idx,
            'question': q,
            'answer': answer,
            'brain_used': brain,
            'provenance': provenance,
            'pass': not failed
        })

    report = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'kb_path': KB_PATH,
        'total': len(questions),
        'passed': len(questions) - failures,
        'failed': failures,
        'results': results
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2)

    return report


def main():
    parser = argparse.ArgumentParser(description='Run the SkyCap AI Gauntlet validation.')
    parser.add_argument('--questions', type=str, default=DEFAULT_QUESTIONS_PATH,
                        help='Path to JSON file with a list of questions or {"questions": [...]}')
    parser.add_argument('--out', type=str, default=REPORT_PATH, help='Output report JSON file path')
    args = parser.parse_args()

    questions = load_questions(args.questions)
    report = run_gauntlet(questions, args.out)

    print("=== Gauntlet Summary ===")
    print(f"Total: {report['total']} | Passed: {report['passed']} | Failed: {report['failed']}")
    if report['failed']:
        print("\nSample Failures:")
        for r in report['results']:
            if not r['pass']:
                print(f"- Q{r['n']}: {r['question']} -> Brain={r['brain_used']} Provenance={r['provenance']}\n  A: {r['answer'][:300]}...")
                # Show up to 5 examples
                if sum(1 for x in report['results'] if not x['pass']) >= 5:
                    break


if __name__ == '__main__':
    main()
