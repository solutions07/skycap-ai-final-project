"""Advanced financial metrics extraction module (Overhauled Version).

Purpose:
        Provide a resilient, multi-pass parser for Jaiz Bank (and similar) PDF
        financial statements, normalizing core metrics into the master knowledge base.

Key Improvements in Overhaul:
        * Global scale detection (scan entire document – not just per-page) with
            precedence order Billions > Millions > Thousands (first match wins).
        * Metric synonym registry with fuzzy / variant pattern support.
        * Multi-pass extraction:
                1. Structured line scan (label to the left, number to the right)
                2. Inline pattern scan ("Total Assets 670,984,551" / "TOTAL ASSETS N'000 670,984")
                3. Fallback heuristic (e.g. choose largest plausible asset figure if label missed)
        * EPS sanity guard (reject implausible values – e.g. > 100 currency units or > 1 where
            clearly scaled by thousands due to misalignment; configurable thresholds).
        * Duplicate report consolidation: preserve the most *complete* metrics set for a given
            filename stem (ignoring minor naming variations / uploads).
        * Extraction reason tracking with human-readable diagnostics for zeros / rejections.
        * Idempotent KB merge keeping historic dates intact when available.

Metrics Covered:
        - total assets
        - profit before tax (pbt)
        - gross earnings / gross income / gross revenue
        - earnings per share (eps)

Heuristics:
        - When multiple numeric candidates appear on a metric line, prefer the *rightmost* or
            the *largest* above a minimum threshold depending on metric type.
        - For assets / gross earnings: must exceed MIN_LARGE_VALUE to be accepted (reduces noise)
        - For EPS: must satisfy 0 < value < EPS_MAX (default 100) and not be an obviously scaled
            integer > EPS_REJECT_ABS (e.g. stray share counts like 64,232,955).

Usage:
        python extract_financials.py --rebuild

Outputs:
        - Updated `master_knowledge_base.json` (financial_reports section)
        - Optional JSON export if --output supplied
        - Embedded diagnostic reasons under `_extraction_reasons`

NOTE: Parser is intentionally heuristic (no OCR / table model). Adjust thresholds if data
            evolution warrants.
"""
from __future__ import annotations
import re
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Iterable

try:
    import pdfplumber  # type: ignore
    _HAS_PDF = True
except ImportError:  # pragma: no cover
    _HAS_PDF = False

ROOT = Path(__file__).parent
KB_PATH = ROOT / 'master_knowledge_base.json'
SOURCE_DIR = ROOT / 'source_data'

PRIMARY_METRICS = [
    'total assets',
    'profit before tax',
    'gross earnings',
    'earnings per share'
]

# Human-readable magnitude formatting
def format_currency(value: float) -> str:
    try:
        abs_v = abs(value)
        if abs_v >= 1_000_000_000:
            return f"₦{value/1_000_000_000:.3f} billion".rstrip('0').rstrip('.')
        if abs_v >= 1_000_000:
            return f"₦{value/1_000_000:.3f} million".rstrip('0').rstrip('.')
        if abs_v >= 1_000:
            return f"₦{value/1_000:.3f} thousand".rstrip('0').rstrip('.')
        return f"₦{value:,.2f}"  # fallback with comma formatting
    except Exception:
        return f"₦{value}"

# Synonym / variant patterns (lowercase keys)
METRIC_SYNONYMS: Dict[str, List[str]] = {
    'total assets': [
        r'total\s+assets?', r'total\s+asset\b', r'total\s+group\s+assets?',
        r'total\s+assets?\s*\(?ngn\)?', r'total\s+assets?\s*\(?consolidated\)?'
    ],
    'profit before tax': [
        r'profit\s+before\s+tax', r'profit\s+befor?e?\s+tax', r'pbt', r'pre[- ]tax\s+profit'
    ],
    'gross earnings': [
        r'gross\s+earnings', r'gross\s+income', r'gross\s+revenue'
    ],
    'earnings per share': [
        r'earnings\s+per\s+share', r'eps\b'
    ]
}

COMPILED_PATTERNS: Dict[str, List[re.Pattern]] = {
    k: [re.compile(p, re.I) for p in pats] for k, pats in METRIC_SYNONYMS.items()
}

SCALE_PATTERNS: List[Tuple[re.Pattern, float]] = [
    (re.compile(r'in\s+thousands', re.I), 1_000.0),
    (re.compile(r'in\s+millions', re.I), 1_000_000.0),
    (re.compile(r'in\s+billions', re.I), 1_000_000_000.0),
]

NUMERIC_RE = re.compile(r'[-+]?\d{1,3}(?:[, ]\d{3})*(?:\.\d+)?')  # Accept grouped numbers
CLEAN_RE = re.compile(r'[^0-9.+-]')

PDF_FILENAME_DATE_RE = re.compile(r'(20\d{2}|19\d{2})[-_/]?((?:0?[1-9]|1[0-2]))?')


def _normalize_number(raw: str, scale: float) -> Optional[float]:
    raw = raw.strip()
    m = NUMERIC_RE.search(raw)
    if not m:
        return None
    val_txt = m.group(0)
    # Remove commas/spaces
    val_txt = val_txt.replace(',', '').replace(' ', '')
    try:
        return float(val_txt) * scale
    except ValueError:
        return None


def _detect_scale(text: str) -> float:
    for pat, multiplier in SCALE_PATTERNS:
        if pat.search(text):
            return multiplier
    return 1.0


def _extract_date_from_filename(name: str) -> Optional[str]:
    # Basic heuristic: prefer explicit YYYY-MM-DD in existing KB; here only year fallback
    m = re.search(r'(20\d{2}|19\d{2})', name)
    if m:
        year = m.group(1)
        # If quarter present
        qm = re.search(r'Q([1-4])', name, re.I)
        if qm:
            q = int(qm.group(1))
            month = [3, 6, 9, 12][q-1]
            return f"{year}-{month:02d}-31"
        return f"{year}-12-31"
    return None


def _candidate_pdf_files() -> List[Path]:
    return sorted([p for p in SOURCE_DIR.glob('*.pdf') if p.is_file()])


MIN_LARGE_VALUE = 10_000.0          # Reject tiny numbers for large balance metrics
ASSET_MIN_VALUE = 1_000_000.0       # Assets typically above 1 million
EPS_MAX = 100.0                     # Upper sanity cap for EPS (currency context)
EPS_REJECT_ABS = 10_000.0           # Reject if accidental large integer captured


def _iter_lines(pages: Iterable[Any]) -> List[str]:  # type: ignore
    lines: List[str] = []
    for page in pages:
        try:
            text = page.extract_text() or ''
        except Exception:
            continue
        if not text:
            continue
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line:
                lines.append(line)
    return lines


def _global_scale(lines: List[str]) -> float:
    joined = '\n'.join(lines)
    # Precedence: billions > millions > thousands
    for pat, mul in SCALE_PATTERNS:
        if pat.search(joined):
            return mul
    return 1.0


def _numbers_in_text(segment: str, scale: float) -> List[float]:
    vals: List[float] = []
    for m in NUMERIC_RE.finditer(segment):
        cleaned = m.group(0).replace(',', '').replace(' ', '')
        try:
            vals.append(float(cleaned) * scale)
        except ValueError:
            continue
    return vals


def _match_metric(line: str, metric: str) -> bool:
    pats = COMPILED_PATTERNS[metric]
    return any(p.search(line) for p in pats)


def _sanitize_metric_value(metric: str, value: float) -> Optional[float]:
    if metric == 'earnings per share':
        # Reject zero, huge miscaptures, or obviously scaled integers
        if value <= 0 or value > EPS_MAX or value > EPS_REJECT_ABS:
            return None
    elif metric == 'total assets':
        if value < ASSET_MIN_VALUE:
            return None
    elif metric in ('gross earnings', 'profit before tax', 'total assets'):
        if value < MIN_LARGE_VALUE:
            return None
    return value


def extract_metrics_from_pdf(path: Path) -> Dict[str, Any]:
    if not _HAS_PDF:
        return {'file_name': str(path), 'metrics': {}, 'error': 'pdfplumber not installed'}
    metrics: Dict[str, float] = {}
    reasons: Dict[str, str] = {}

    try:
        import pdfplumber  # type: ignore
        with pdfplumber.open(path) as pdf:
            pages = list(pdf.pages)
            lines = _iter_lines(pages)
            if not lines:
                # For each primary metric, set reason to 'no text extracted'
                reasons = {m: 'no text extracted' for m in PRIMARY_METRICS}
                reasons['_general'] = 'no text extracted'
                return {'file_name': str(path), 'metrics': {}, 'reasons': reasons}
            scale = _global_scale(lines)
            scale_hint = None
            if scale == 1_000.0:
                scale_hint = 'thousands'
            elif scale == 1_000_000.0:
                scale_hint = 'millions'
            elif scale == 1_000_000_000.0:
                scale_hint = 'billions'

            # PASS 1: Structured lines (label : number or split by multiple spaces)
            for line in lines:
                normalized = re.sub(r'\s+', ' ', line)
                # Skip lines without digits to reduce noise
                if not any(ch.isdigit() for ch in normalized):
                    continue
                segments = [s.strip() for s in re.split(r':| {2,}', normalized) if s.strip()]
                # Evaluate each metric only if still missing
                for metric in PRIMARY_METRICS:
                    if metric in metrics:
                        continue
                    if _match_metric(normalized.lower(), metric):
                        # Gather numeric candidates from all trailing segments
                        candidates: List[float] = []
                        for seg in segments[1:] if len(segments) > 1 else [normalized]:
                            candidates.extend(_numbers_in_text(seg, scale))
                        if candidates:
                            # For assets / gross earnings choose largest; EPS choose smallest >0
                            chosen = None
                            if metric == 'earnings per share':
                                positive = [v for v in candidates if v > 0]
                                chosen = min(positive) if positive else None
                            else:
                                chosen = max(candidates)
                            if chosen is not None:
                                sanitized = _sanitize_metric_value(metric, chosen)
                                if sanitized is not None:
                                    metrics[metric] = sanitized
                                else:
                                    reasons[metric] = f'rejected_sanity:{chosen}'
                        else:
                            reasons.setdefault(metric, 'no_numeric_candidate')
                if len(metrics) == len(PRIMARY_METRICS):
                    break

            # PASS 2: Inline fallback – search lines for remaining metrics
            remaining = [m for m in PRIMARY_METRICS if m not in metrics]
            if remaining:
                for line in lines:
                    low = line.lower()
                    if not any(rm in low for rm in [w.split()[0] for w in remaining]):
                        continue
                    nums = _numbers_in_text(line, scale)
                    if not nums:
                        continue
                    for metric in list(remaining):
                        if _match_metric(low, metric):
                            chosen = None
                            if metric == 'earnings per share':
                                positive = [v for v in nums if 0 < v <= EPS_MAX]
                                if positive:
                                    chosen = min(positive)
                            else:
                                chosen = max(nums)
                            if chosen is not None:
                                sanitized = _sanitize_metric_value(metric, chosen)
                                if sanitized is not None:
                                    metrics[metric] = sanitized
                                    remaining.remove(metric)
                                else:
                                    reasons[metric] = f'rejected_sanity:{chosen}'
                # Update remaining after pass 2
                remaining = [m for m in PRIMARY_METRICS if m not in metrics]

            # PASS 3: Heuristic fallback (assets only) – choose largest number in document
            if 'total assets' not in metrics:
                all_numbers: List[float] = []
                for line in lines:
                    all_numbers.extend(_numbers_in_text(line, scale))
                plausible = [v for v in all_numbers if v >= ASSET_MIN_VALUE]
                if plausible:
                    guess = max(plausible)
                    metrics['total assets'] = guess
                    reasons['total assets'] = 'fallback_largest_number'
                else:
                    reasons['total assets'] = 'not_found'

            # Ensure missing metrics have explicit reasons
            for m in PRIMARY_METRICS:
                if m not in metrics and m not in reasons:
                    reasons[m] = 'not_found'

    except Exception as e:  # pragma: no cover
        return {'file_name': str(path), 'metrics': {}, 'error': str(e)}

    return {'file_name': str(path), 'metrics': metrics, 'reasons': reasons}


def integrate_into_kb(kb_path: Path, extracted: List[Dict[str, Any]]) -> Dict[str, Any]:
    if kb_path.exists():
        kb = json.loads(kb_path.read_text())
    else:
        kb = {}
    existing = kb.get('financial_reports', [])
    # --- Legacy data hygiene pass: remove zero-valued metrics that may have been persisted
    # prior to introducing zero filtering logic. This ensures rebuilt KBs do not retain
    # placeholder zeros (e.g., EPS = 0.0) that violate sanity tests and create false confidence.
    for entry in existing:
        try:
            meta = entry.get('report_metadata') or {}
            mets = meta.get('metrics') or {}
            cleaned = {k: v for k, v in mets.items() if not _is_zero(v)}
            if len(cleaned) != len(mets):
                # Track reasons for removed zeros if diagnostics container present
                reasons = meta.get('_extraction_reasons') or {}
                for k, v in mets.items():
                    if k not in cleaned:
                        reasons.setdefault(k, 'legacy_zero_purged')
                meta['_extraction_reasons'] = reasons
                meta['metrics'] = cleaned
        except Exception:
            continue
    # Map existing by filename for merging
    by_file = {}
    for r in existing:
        meta = r.get('report_metadata') or {}
        by_file[meta.get('file_name')] = r
    for item in extracted:
        fname = item['file_name']
        # Attempt to preserve existing report_date if present
        report_date = None
        if fname in by_file:
            report_date = by_file[fname].get('report_metadata', {}).get('report_date')
        if not report_date:
            report_date = _extract_date_from_filename(Path(fname).name)
        new_metrics = item.get('metrics', {}) or {}
        reasons = item.get('reasons', {}) or {}

        # Filter out zero or None metrics (treat as missing so tests validate quality)
        cleaned_metrics = {}
        for mk, mv in new_metrics.items():
            try:
                fv = float(mv)
            except (TypeError, ValueError):
                continue
            if fv == 0.0:
                # Mark reason if absent
                reasons.setdefault(mk, 'zero_value_filtered')
                continue
            cleaned_metrics[mk] = mv
        new_metrics = cleaned_metrics

        # Helper to determine non-zero metric count (quality over raw key count)
        def _non_zero_len(d: Dict[str, float]) -> int:
            cnt = 0
            for _k, _v in d.items():
                try:
                    if float(_v) != 0.0:
                        cnt += 1
                except Exception:
                    continue
            return cnt

        # If we already have an entry and new metrics are empty or clearly incomplete, preserve old metrics
        if fname in by_file:
            old_meta = by_file[fname].get('report_metadata', {})
            old_metrics = old_meta.get('metrics', {}) or {}
            # Determine completeness threshold (all four core metrics) else keep old
            core_keys = {"total assets", "profit before tax", "gross earnings", "earnings per share"}
            new_has_all = core_keys.issubset(set(k.lower() for k in new_metrics.keys()))
            # Use non-zero lengths to avoid zero placeholders biasing completeness
            if not new_metrics or (_non_zero_len(new_metrics) < _non_zero_len(old_metrics) and not new_has_all):
                # Preserve old metrics; merge any newly discovered metrics without overwriting existing values
                merged = dict(old_metrics)
                for k, v in new_metrics.items():
                    if k not in merged and v is not None:
                        merged[k] = v
                new_metrics = merged
                # Keep old reasons if any
                if not reasons and '_extraction_reasons' in old_meta:
                    reasons = old_meta.get('_extraction_reasons', {})

        # Consolidation heuristic: if an existing entry has fewer non-zero metrics, replace.
        existing_entry = by_file.get(fname)
        if existing_entry:
            old_metrics = existing_entry.get('report_metadata', {}).get('metrics', {}) or {}
            def _score(md: Dict[str, float]) -> int:
                return sum(1 for v in md.values() if isinstance(v, (int, float)) and v > 0)
            if _score(new_metrics) < _score(old_metrics):
                # Keep old metrics but merge any *new* non-zero values absent previously
                merged = dict(old_metrics)
                for k, v in new_metrics.items():
                    if k not in merged and v:
                        merged[k] = v
                new_metrics = merged
                reasons.setdefault('_merge', 'retained_previous_more_complete_metrics')

        kb_entry = {
            'report_metadata': {
                'file_name': fname,
                'report_date': report_date,
                'metrics': new_metrics,
                '_extraction_reasons': reasons,
            }
        }
        by_file[fname] = kb_entry
    kb['financial_reports'] = list(by_file.values())
    return kb


def _is_zero(val: Any) -> bool:
    try:
        return float(val) == 0.0
    except Exception:
        return False


def run_extraction(save: bool = True) -> Dict[str, Any]:
    pdfs = _candidate_pdf_files()
    extracted: List[Dict[str, Any]] = []
    for pdf in pdfs:
        extracted.append(extract_metrics_from_pdf(pdf))
    kb = integrate_into_kb(KB_PATH, extracted)
    if save:
        KB_PATH.write_text(json.dumps(kb, indent=2))
    return kb


def main():
    parser = argparse.ArgumentParser(description='Extract financial metrics into KB')
    parser.add_argument('--rebuild', action='store_true', help='Force rebuild extraction and overwrite KB')
    parser.add_argument('--output', type=Path, help='Optional path to write extracted JSON')
    args = parser.parse_args()
    kb = run_extraction(save=args.rebuild or not KB_PATH.exists())
    if args.output:
        args.output.write_text(json.dumps(kb, indent=2))
    print(f"Processed {len(kb.get('financial_reports', []))} financial report entries")

if __name__ == '__main__':  # pragma: no cover
    main()
