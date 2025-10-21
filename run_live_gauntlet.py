#!/usr/bin/env python3
import json
import re
import sys
import time
import urllib.request
from urllib.error import URLError, HTTPError
from typing import Dict, Any, List, Optional, Tuple

import intelligent_agent as ia

SERVICE_URL = "https://skycap-live-service-472059152731.europe-west1.run.app/ask"
GAUNTLET_PATH = "data/gauntlet_questions_full.json"
KB_PATH = "data/master_knowledge_base.json"


def http_post_json(url: str, payload: Dict[str, Any], origin: Optional[str] = None) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    if origin:
        req.add_header("Origin", origin)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_questions(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    return obj.get("questions", [])


def build_expected_for_metric(fin: ia.FinancialDataEngine, metric_display: str, year: str) -> Optional[str]:
    # mirror engine logic for within-year selection and formatting
    norm_key = re.sub(r"[^a-z0-9]", "", metric_display.lower())
    candidates = [(val, dt) for (k, dt), val in fin.metrics.items() if k == norm_key and isinstance(dt, str) and dt.startswith(year)]
    if not candidates:
        return None
    # prefer month 12, non-zero, then 09, 06, 03 and latest
    def _month_pref(m: int) -> int:
        order = {12: 4, 9: 3, 6: 2, 3: 1}
        return order.get(m, 0)
    scored = []
    for val, dt in candidates:
        try:
            m = int(dt[5:7])
        except Exception:
            m = 0
        nz = 1 if (isinstance(val, (int, float)) and float(val) != 0.0) else 0
        annual_boost = 1 if m == 12 else 0
        score = (annual_boost, nz, _month_pref(m), dt)
        scored.append((score, val, dt))
    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0]
    formatted = ia._format_metric_value(metric_display, best[1], best[2])
    return f"{metric_display.title()} for {year} was {formatted} (as of {best[2]})."


def build_expected_for_price(kb: Dict[str, Any], symbol: str, date: Optional[str]) -> Optional[str]:
    md = kb.get("market_data", [])
    if date:
        for rec in md:
            if rec.get("symbol") == symbol and rec.get("pricedate") == date:
                price = rec.get("closingprice")
                if isinstance(price, (int, float)):
                    return f"The closing price for {symbol} on {date} was ₦{price:,.2f}."
        return None
    # latest
    records = [r for r in md if r.get("symbol") == symbol and isinstance(r.get("pricedate"), str)]
    if not records:
        return None
    records.sort(key=lambda x: x.get("pricedate"), reverse=True)
    r = records[0]
    price = r.get("closingprice")
    date_str = r.get("pricedate")
    if isinstance(price, (int, float)) and isinstance(date_str, str):
        return f"The most recent closing price for {symbol} on {date_str} was ₦{price:,.2f}."
    return None


def norm_text(s: str) -> str:
    # replicate normalization used by KnowledgeBaseLookupEngine
    replacements = {
        '\u2018': "'", '\u2019': "'",
        '\u201C': '"', '\u201D': '"',
        '\u2013': '-', '\u2014': '-',
        '\u00A0': ' ', '\u200B': ''
    }
    out = []
    for ch in s:
        out.append(replacements.get(ch, ch))
    s2 = ''.join(out)
    s2 = re.sub(r"\s+", ' ', s2, flags=re.MULTILINE).strip()
    return s2


def build_expected_for_exact_line(kb: Dict[str, Any], target: str) -> Optional[str]:
    client_profile = kb.get('client_profile', {}).get('skyview knowledge pack', {})
    needle = norm_text(target)
    for v in client_profile.values():
        if isinstance(v, list):
            for line in v:
                if isinstance(line, str) and norm_text(line) == needle:
                    return line
    return None


def classify_and_expected(fin: ia.FinancialDataEngine, kb: Dict[str, Any], q: str) -> Tuple[str, Optional[str]]:
    ql = q.lower()
    # exact line
    if re.search(r"(provide|return|give)\s+the\s+exact\s+line\s*:", ql):
        # extract text within last quotes
        m = re.search(r"[\"'](.+)[\"']\s*$", q)
        if not m:
            return ("exact", None)
        target = m.group(1)
        return ("exact", build_expected_for_exact_line(fin.reports and fin.reports[0].get('kb', {}) or kb, target) or build_expected_for_exact_line(kb, target))

    # metric year
    m_year = re.search(r"(20\d{2}|19\d{2})", q)
    if m_year and "jaiz bank" in ql:
        year = m_year.group(1)
        if "total assets" in ql:
            return ("metric", build_expected_for_metric(fin, ia.FinancialDataEngine.METRIC_TOTAL_ASSETS, year))
        if "profit before tax" in ql:
            return ("metric", build_expected_for_metric(fin, ia.FinancialDataEngine.METRIC_PROFIT_BEFORE_TAX, year))
        if "gross earnings" in ql:
            return ("metric", build_expected_for_metric(fin, ia.FinancialDataEngine.METRIC_GROSS_EARNINGS, year))
        if "earnings per share" in ql:
            return ("metric", build_expected_for_metric(fin, ia.FinancialDataEngine.METRIC_EARNINGS_PER_SHARE, year))

    # symbol price with date
    m_sym_date = re.search(r"what is the price of\s+([A-Z0-9]+)\s+on\s+(\d{4}-\d{2}-\d{2})\?", q)
    if m_sym_date:
        sym = m_sym_date.group(1)
        date = m_sym_date.group(2)
        return ("price_date", build_expected_for_price(kb, sym, date))

    # symbol price latest
    m_sym = re.search(r"what is the price of\s+([A-Z0-9]+)\?", q)
    if m_sym:
        sym = m_sym.group(1)
        return ("price_latest", build_expected_for_price(kb, sym, None))

    return ("unknown", None)


def paraphrases_for(q: str) -> List[str]:
    out: List[str] = []
    ql = q.lower()
    # Metrics with explicit year
    m_year = re.search(r"(20\d{2}|19\d{2})", q)
    if m_year and "jaiz bank" in ql and any(k in ql for k in ["total assets", "profit before tax", "gross earnings", "earnings per share"]):
        year = m_year.group(1)
        metric = None
        for k in ["total assets", "profit before tax", "gross earnings", "earnings per share"]:
            if k in ql:
                metric = k
                break
        if metric:
            out.append(f"Tell me the {metric} for Jaiz Bank in {year}.")
            out.append(f"Provide {metric} for Jaiz Bank, {year}.")
            out.append(f"What is the {metric} for Jaiz Bank for {year}?")
    # Prices with date
    m_sym_date = re.search(r"what is the price of\s+([A-Z0-9]+)\s+on\s+(\d{4}-\d{2}-\d{2})\?", q)
    if m_sym_date:
        sym, date = m_sym_date.group(1), m_sym_date.group(2)
        out.append(f"Tell me the closing price of {sym} on {date}.")
        out.append(f"What did {sym} close at on {date}?")
    # Exact line
    if re.search(r"(provide|return|give)\s+the\s+exact\s+line\s*:", ql):
        m = re.search(r"([\"'].*[\"'])\s*$", q)
        if m:
            quoted = m.group(1)
            out.append(f"Return the exact line: {quoted}")
            out.append(f"Give the exact line: {quoted}")
    return out


def main():
    with open(KB_PATH, "r", encoding="utf-8") as f:
        kb = json.load(f)
    fin = ia.FinancialDataEngine(kb)
    questions = load_questions(GAUNTLET_PATH)
    total = 0
    passed = 0
    failed: List[Dict[str, Any]] = []
    skipped: List[str] = []

    def run_one(question: str):
        nonlocal total, passed
        total += 1
        kind, expected = classify_and_expected(fin, kb, question)
        try:
            resp = http_post_json(SERVICE_URL, {"query": question})
            got = resp.get("answer")
        except (HTTPError, URLError) as e:
            failed.append({"q": question, "error": str(e), "kind": kind})
            return
        if expected is None:
            # we can't auto-validate; mark skipped
            skipped.append(question)
            return
        if got == expected:
            passed += 1
        else:
            failed.append({"q": question, "expected": expected, "got": got, "kind": kind})

    # Run exact questions
    for q in questions:
        run_one(q)
        time.sleep(0.02)  # be gentle

    # Optional paraphrase run (limited to questions we can auto-validate)
    for q in questions:
        for p in paraphrases_for(q):
            kind, expected = classify_and_expected(fin, kb, q)  # expected remains same for paraphrase
            if expected is None:
                continue
            total += 1
            try:
                resp = http_post_json(SERVICE_URL, {"query": p})
                got = resp.get("answer")
            except (HTTPError, URLError) as e:
                failed.append({"q": p, "error": str(e), "kind": kind})
                continue
            if got == expected:
                passed += 1
            else:
                failed.append({"q": p, "expected": expected, "got": got, "kind": kind, "paraphrase_of": q})
            time.sleep(0.02)

    summary = {
        "total": total,
        "passed": passed,
        "failed": len(failed),
        "skipped": len(skipped),
    }
    print(json.dumps({"summary": summary, "failed_samples": failed[:25]}, indent=2))


if __name__ == "__main__":
    main()
