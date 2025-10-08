import json
from pathlib import Path
from typing import List, Dict, Any

KB_PATH = 'data/master_knowledge_base.json'
OUT_PATH = 'data/gauntlet_questions_full.json'


def load_kb(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def gen_financial_questions(kb: Dict[str, Any]) -> List[str]:
    questions = []
    for report in kb.get('financial_reports', []):
        meta = report.get('report_metadata', {})
        date = meta.get('report_date')
        metrics = meta.get('metrics', {})
        if not (date and isinstance(metrics, dict)):
            continue
        year = date[:4]
        for metric_name in metrics.keys():
            # Ask directly using metric name and year
            questions.append(f"What was the {metric_name} for Jaiz Bank in {year}?")
    return questions


def gen_market_questions(kb: Dict[str, Any]) -> List[str]:
    questions = []
    for rec in kb.get('market_data', []):
        sym = rec.get('symbol')
        date = rec.get('pricedate')
        if not (sym and date):
            continue
        questions.append(f"What is the price of {sym} on {date}?")
        # Also include recent price question once per symbol later
    # Add a most recent price question per unique symbol
    seen = set()
    for rec in kb.get('market_data', []):
        sym = rec.get('symbol')
        if sym and sym not in seen:
            seen.add(sym)
            questions.append(f"What is the price of {sym}?")
    return questions


def flatten_profile(obj) -> List[str]:
    out = []
    if isinstance(obj, dict):
        for v in obj.values():
            out.extend(flatten_profile(v))
    elif isinstance(obj, list):
        for x in obj:
            out.extend(flatten_profile(x))
    else:
        if isinstance(obj, str):
            out.append(obj)
    return out


def gen_profile_questions(kb: Dict[str, Any]) -> List[str]:
    questions = []
    profile_root = kb.get('client_profile', {}).get('skyview knowledge pack', {})
    lines = flatten_profile(profile_root)
    for line in lines:
        line = str(line).strip()
        if not line:
            continue
        # Ask for the exact line back (used by KnowledgeBaseLookupEngine)
        questions.append(f"Provide the exact line: '{line}'")
    return questions


def main():
    kb = load_kb(KB_PATH)
    q_fin = gen_financial_questions(kb)
    q_mkt = gen_market_questions(kb)
    q_prof = gen_profile_questions(kb)

    questions = q_fin + q_mkt + q_prof

    # De-duplicate while preserving order
    seen = set()
    deduped = []
    for q in questions:
        if q not in seen:
            seen.add(q)
            deduped.append(q)

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump({'questions': deduped}, f, indent=2)

    print(f"Wrote {len(deduped)} questions to {OUT_PATH}")


if __name__ == '__main__':
    main()
