
import json
import re
import logging
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional


# --- Compiled Regex & Metric Registry ---

# Centralized compiled regex patterns
YEAR_RE = re.compile(r'(?<!\d)(?:19|20)\d{2}(?!\d)')
PE_QUERY_RE = re.compile(r"\b(p\/?e|pe\s*ratio|price\s*to\s*earnings)\b", re.IGNORECASE)
CHANGE_FROM_TO_RE = re.compile(r'(?:how\s+did\s+.*?\s+)?change\s+from.*?(?:19|20)\d{2}.*?to.*?(?:19|20)\d{2}', re.IGNORECASE)
FROM_TO_YEARS_RE = re.compile(r'from.*?(?:19|20)\d{2}.*?to.*?(?:19|20)\d{2}', re.IGNORECASE)

# Central metric registry for core metrics
METRIC_REGISTRY = {
    'total assets': {
        'canonical': 'total assets',
        'synonyms': ['total asset', 'asset base', 'total assets value', 'asset balance'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'profit before tax': {
        'canonical': 'profit before tax',
        'synonyms': ['pbt', 'pre-tax profit', 'pretax profit', 'profit before taxation', 'pretax'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'gross earnings': {
        'canonical': 'gross earnings',
        'synonyms': ['gross income', 'total revenue', 'turnover', 'total sales'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'earnings per share': {
        'canonical': 'earnings per share',
        'synonyms': ['eps', 'earning per share', 'earnings-per-share'],
        'scaling': 'unit',
        'value_type': 'per_share',
        'annual_preferred': True,
    },
    'return on equity': {
        'canonical': 'return on equity',
        'synonyms': ['roe', 'return on equity ratio', 'return on equity of investors'],
        'scaling': 'unit',
        'value_type': 'ratio',
        'annual_preferred': False,
    },
    'net revenue from funds': {
        'canonical': 'net revenue from funds',
        'synonyms': ['net fund revenue', 'net revenue from fund operations'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'credit impairment charges': {
        'canonical': 'credit impairment charges',
        'synonyms': ['loan loss provisions', 'impairment charges', 'credit impairment charge'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'profit after tax': {
        'canonical': 'profit after tax',
        'synonyms': ['pat', 'net profit', 'net income', 'profit after taxation'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'income from financing and investment': {
        'canonical': 'income from financing and investment',
        'synonyms': ['financing and investment income', 'financing income', 'investment income'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'net operating income': {
        'canonical': 'net operating income',
        'synonyms': ['noi', 'net operating profit', 'operating income net'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'operating expenses': {
        'canonical': 'operating expenses',
        'synonyms': ['operating expense', 'opex', 'operating costs', 'operating expenditure'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'taxation expense': {
        'canonical': 'taxation expense',
        'synonyms': ['tax expense', 'tax charge', 'taxation'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'cash from operating activities': {
        'canonical': 'cash from operating activities',
        'synonyms': ['operating cash flow', 'cash flow from operating activities', 'cash generated from operations'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'operating cash flow before working capital charges': {
        'canonical': 'operating cash flow before working capital charges',
        'synonyms': ['operating cash flow before working capital', 'cash flow before working capital charges'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'net cash generated from operating activities': {
        'canonical': 'net cash generated from operating activities',
        'synonyms': ['net operating cash flow', 'net cash from operating activities'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'cash flow from investing activities': {
        'canonical': 'cash flow from investing activities',
        'synonyms': ['investing cash flow', 'cash used in investing activities'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'cash flow from financing activities': {
        'canonical': 'cash flow from financing activities',
        'synonyms': ['financing cash flow', 'cash from financing activities'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'net decrease in cash and cash equivalents': {
        'canonical': 'net decrease in cash and cash equivalents',
        'synonyms': ['net decrease in cash', 'net change in cash'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'cash and bank balance at beginning of period': {
        'canonical': 'cash and bank balance at beginning of period',
        'synonyms': ['opening cash balance', 'beginning cash balance', 'cash at the beginning of the period'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'cash and bank balance at end of period': {
        'canonical': 'cash and bank balance at end of period',
        'synonyms': ['closing cash balance', 'ending cash balance', 'cash at the end of the period'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'exceptional items': {
        'canonical': 'exceptional items',
        'synonyms': ['exceptional item', 'extraordinary items', 'one-off items'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
    'other income': {
        'canonical': 'other income',
        'synonyms': ['miscellaneous income', 'misc income', 'other revenues'],
        'scaling': 'thousands',
        'value_type': 'currency',
        'annual_preferred': False,
    },
}

# Quarter interpretation maps
QUARTER_MONTH_MAP = {
    '1': '03',
    '2': '06',
    '3': '09',
    '4': '12',
}

QUARTER_WORD_MAP = {
    'first': '1',
    '1st': '1',
    'second': '2',
    '2nd': '2',
    'third': '3',
    '3rd': '3',
    'fourth': '4',
    '4th': '4',
}

# --- Helper Functions ---

def _compile_metric_regex(alias: str) -> Optional[re.Pattern]:
    """Compile a flexible regex for a metric alias (handles spaces, hyphens, slashes)."""
    if not alias:
        return None
    cleaned = alias.strip().lower()
    if not cleaned:
        return None
    tokens = re.split(r'[\s\-/&]+', cleaned)
    tokens = [t for t in tokens if t]
    if not tokens:
        return None
    if len(tokens) == 1:
        pattern = rf"\b{re.escape(tokens[0])}\b"
    else:
        separator = r'(?:[\s\-/&]+)'
        pattern = r'\b' + separator.join(re.escape(token) for token in tokens) + r'\b'
    return re.compile(pattern, re.IGNORECASE)

def _format_large_number(value):
    """Format large numbers with Nigerian Naira currency and appropriate units."""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    if not number.is_finite():
        return str(value)

    thousands_multiplier = Decimal('1000')
    scaled = number * thousands_multiplier
    abs_scaled = scaled.copy_abs()

    unit = ''
    divisor = Decimal('1')
    trillion = Decimal('1000000000000')
    billion = Decimal('1000000000')
    million = Decimal('1000000')

    precision_map = {
        trillion: Decimal('0.000001'),
        billion: Decimal('0.000001'),
        million: Decimal('0.001'),
    }

    if abs_scaled >= trillion:
        unit = ' Trillion'
        divisor = trillion
    elif abs_scaled >= billion:
        unit = ' Billion'
        divisor = billion
    elif abs_scaled >= million:
        unit = ' Million'
        divisor = million

    if divisor != Decimal('1'):
        precision = precision_map.get(divisor, Decimal('0.01'))
        display_value = (scaled / divisor).quantize(precision, rounding=ROUND_HALF_UP)
    else:
        precision = Decimal('0.01')
        display_value = scaled.quantize(precision, rounding=ROUND_HALF_UP)

    magnitude = format(display_value.copy_abs(), ',f')
    if '.' in magnitude:
        magnitude = magnitude.rstrip('0').rstrip('.')
    sign = '-' if scaled < 0 else ''
    formatted_unit = f"₦{sign}{magnitude}{unit}".strip()

    raw_currency = format(scaled, ',.2f')
    if raw_currency.endswith('00'):
        raw_currency = raw_currency[:-3]
    elif raw_currency.endswith('0'):
        raw_currency = raw_currency[:-1]
    raw_currency = f"₦{raw_currency}"

    if abs_scaled >= million:
        return f"{raw_currency} ({formatted_unit})"

    return formatted_unit

def _format_metric_value(metric_name: str, value):
    """Format metric values smartly based on their type.

    - Currency-like metrics (assets, PBT, gross earnings) are in thousands and use _format_large_number.
    - Earnings per share (EPS) is a plain number; no currency symbol or thousands scaling.
    """
    metric_key = metric_name.strip().lower() if isinstance(metric_name, str) else None
    metric_cfg = METRIC_REGISTRY.get(metric_key) if metric_key else None
    if metric_cfg and metric_cfg.get('scaling') == 'thousands':
        return _format_large_number(value)

    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return str(value)

    precision = Decimal('0.0001') if metric_cfg and metric_cfg.get('value_type') == 'per_share' else Decimal('0.01')
    try:
        number = number.quantize(precision, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        pass
    formatted = format(number, 'f')
    if '.' in formatted:
        formatted = formatted.rstrip('0').rstrip('.')
    return formatted

def _load_kb(path):
    """Load knowledge base from JSON file."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Knowledge base file not found at {path}")
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {path}: {e}")
    except Exception as e: # Catch any other unexpected errors
        logging.error(f"Failed to load KB from {path}: {e}")
    return None

# --- Engine Classes ---
try:
    # Local import to avoid hard dependency during unit tests w/o index
    from search_index import SemanticSearcher  # type: ignore
except Exception:
    SemanticSearcher = None  # type: ignore

# Vertex AI (external brains) - optional import
try:  # pragma: no cover - environment dependent
    import vertexai  # type: ignore
    try:
        # Newer stable import path
        from vertexai.generative_models import GenerativeModel  # type: ignore
    except Exception:  # fallback for older versions
        from vertexai.preview.generative_models import GenerativeModel  # type: ignore
except Exception:  # pragma: no cover
    vertexai = None  # type: ignore
    GenerativeModel = None  # type: ignore

class FinancialDataEngine:
    """Engine for searching financial data from the knowledge base."""
    # Define constants for metric names for better readability and maintainability
    METRIC_TOTAL_ASSETS = 'total assets'
    METRIC_PROFIT_BEFORE_TAX = 'profit before tax'
    METRIC_GROSS_EARNINGS = 'gross earnings'
    METRIC_EARNINGS_PER_SHARE = 'earnings per share'
    
    def __init__(self, kb):
        self.reports = kb.get('financial_reports', [])
        self.metrics = {}
        # Precomputed lookups and response metadata
        self.date_to_meta = {}
        self.last_source_refs = None
        self.last_confidence = 'high'
        # Market data for JAIZBANK symbol to compute price-based ratios (e.g., P/E)
        self.market_data = sorted(
            [d for d in kb.get('market_data', []) if d.get('symbol') == 'JAIZBANK' and 'pricedate' in d and 'closingprice' in d],
            key=lambda x: x.get('pricedate') or ''
        )
        # Guardrail thresholds (can be tuned via env vars)
        try:
            self.min_eps_for_pe = float(os.getenv('MIN_EPS_FOR_PE', '0.05'))  # ignore micro-EPS noise
        except Exception:
            self.min_eps_for_pe = 0.05
        try:
            self.max_pe_allowed = float(os.getenv('MAX_PE_ALLOWED', '150'))    # filter unrealistic outliers
        except Exception:
            self.max_pe_allowed = 150.0
        self._build_index()

    def _interpret_financial_value(self, metric: str, value: float, report_metadata: dict) -> dict:
        """Analyze if a financial value needs contextual explanation"""
        
        context_flags = []
        confidence_level = "high"
        
        # Zero-value analysis with business context
        if value == 0.0:
            file_name = report_metadata.get('file_name', '')
            report_date = report_metadata.get('report_date', '')
            
            # Check if this is quarterly vs annual (quarters might legitimately be zero)
            # Be more precise: Q1-Q3 are interim, Q4/Quarter 4 and annual keywords indicate year-end
            is_interim_quarter = any(q in file_name.lower() for q in ['quarter_1', 'quarter_2', 'quarter_3', 'q1', 'q2', 'q3'])
            is_annual = any(a in file_name.lower() for a in ['annual', 'year_end', 'year-end', 'quarter_4', 'quarter_5']) or report_date.endswith('-12-31')
            
            if metric.lower() == 'earnings per share' and (is_annual or not is_interim_quarter):
                context_flags.append("annual_eps_zero")
                confidence_level = "medium"
            
            if metric.lower() == 'profit before tax' and value == 0.0:
                context_flags.append("zero_profit_flagged")
        
        return {
            "raw_value": value,
            "confidence": confidence_level,
            "context_flags": context_flags,
            "needs_qualification": len(context_flags) > 0
        }

    def _validate_data_quality(self, reports: list) -> dict:
        """Generate data quality insights for business review"""
        
        quality_report = {
            "suspicious_zeros": [],
            "missing_metrics": [],
            "data_consistency_issues": []
        }
        
        for report in reports:
            meta = report.get('report_metadata', {})
            metrics = meta.get('metrics', {})
            file_name = meta.get('file_name', '')
            report_date = meta.get('report_date', '')
            
            # Flag suspicious patterns - improved annual detection
            is_annual_report = (any(a in file_name.lower() for a in ['annual', 'year_end', 'year-end', 'quarter_4', 'quarter_5']) 
                              or (report_date and report_date.endswith('-12-31')))
            if metrics.get('earnings per share') == 0.0 and is_annual_report:
                quality_report["suspicious_zeros"].append({
                    "metric": "earnings per share",
                    "file": file_name,
                    "date": report_date,
                    "reason": "Annual EPS of zero unusual for operating bank"
                })
                
            # Check for missing critical metrics in annual reports
            if is_annual_report:
                critical_metrics = ['total assets', 'profit before tax', 'earnings per share']
                for metric in critical_metrics:
                    if metric not in metrics or metrics[metric] is None:
                        quality_report["missing_metrics"].append({
                            "metric": metric,
                            "file": file_name,
                            "date": report_date
                        })
        
        return quality_report

    def _format_contextual_response(self, metric: str, analysis: dict, report_date: str) -> str:
        """Generate professional response with appropriate context"""
        
        raw_value = analysis["raw_value"]
        
        if analysis["needs_qualification"]:
            if "annual_eps_zero" in analysis["context_flags"]:
                return (f"Based on our records, the {metric.title()} for Jaiz Bank in {report_date[:4]} "
                       f"is reported as {raw_value} (year-end {report_date}). "
                       f"This zero value is unusual for an operating bank and may indicate: "
                       f"(a) no earnings distribution for the period, (b) accounting adjustments, or "
                       f"(c) a data extraction anomaly. For investment decisions, we recommend "
                       f"cross-referencing with the audited financial statement.")
            
            if raw_value == 0.0:
                return (f"Our data shows {metric.title()} for {report_date[:4]} as {raw_value} "
                       f"(as of {report_date}). While this reflects the available records, "
                       f"we advise verifying this figure against the published financial statement "
                       f"before making critical business decisions.")
        
        # Standard formatting for confident values
        formatted_value = _format_metric_value(metric, raw_value)
        return f"{metric.title()} for {report_date[:4]} was {formatted_value} (as of {report_date})."

    def _build_index(self):
        """Build an index of financial metrics for efficient searching."""
        for report in self.reports:
            meta = report.get('report_metadata', {})
            date = meta.get('report_date')
            metrics = meta.get('metrics', {})
            if date and metrics:
                # build date->meta map for fast provenance
                self.date_to_meta.setdefault(date, []).append(meta)
                for key, value in metrics.items():
                    norm_key = re.sub(r'[^a-z0-9]', '', key.lower())
                    try:
                        self.metrics[(norm_key, date)] = float(value)
                    except (ValueError, TypeError): 
                        continue
    def _collect_metric_series(self, metric_key: str, start_year: Optional[int] = None, end_year: Optional[int] = None, prefer_annual: bool = False):
        """Collect one best value per year for a metric, optionally limited to a year range.

        Selection per year prefers: month 12 > 09 > 06 > 03, non-zero over zero, and latest date.
        If prefer_annual is True, month 12 is strongly preferred when available.
        Returns list of tuples: (year:int, date:str, value:float), ordered by year ascending.
        """
        per_year = {}
        for (key, date), value in self.metrics.items():
            if key != metric_key:
                continue
            try:
                if not isinstance(date, str) or len(date) < 7:
                    continue
                y = int(date[:4])
            except Exception:
                continue
            if start_year is not None and y < start_year:
                continue
            if end_year is not None and y > end_year:
                continue
            per_year.setdefault(y, []).append((value, date))

        def month_rank(month: int) -> int:
            order = {12: 4, 9: 3, 6: 2, 3: 1}
            return order.get(month, 0)

        series = []
        for y, cand in per_year.items():
            scored = []
            for value, date in cand:
                try:
                    m = int(date[5:7])
                except Exception:
                    m = 0
                nz = 1 if (isinstance(value, (int, float)) and float(value) != 0.0) else 0
                mr = month_rank(m)
                annual_boost = 1 if (prefer_annual and m == 12) else 0
                score = (annual_boost, nz, mr, date)
                scored.append((score, value, date))
            scored.sort(key=lambda x: x[0], reverse=True)
            best = scored[0]
            series.append((y, best[2], best[1]))

        series.sort(key=lambda t: t[0])
        return series

    def _extract_quarter_from_question(self, question: str) -> Optional[str]:
        """Identify if the user referenced a specific quarter in the question."""
        text = question.lower()

        # Patterns like "Q3" or "Quarter 3"
        numeric_patterns = [
            re.search(r'\bq(?:uarter)?\s*([1-4])\b', text),
            re.search(r'\bquarter\s*([1-4])\b', text),
            re.search(r'([1-4])(?:st|nd|rd|th)?\s+(?:quarter|qtr)\b', text),
        ]
        for match in numeric_patterns:
            if match:
                return match.group(1)

        # Textual labels like "third quarter" or "third-quarter"
        for label, token in QUARTER_WORD_MAP.items():
            if re.search(fr'\b{label}(?:\s+|-)?quarter\b', text):
                return token

        return None

    def _find_best_date_match(
        self,
        norm_metric_key: str,
        target_year: Optional[str],
        quarter_token: Optional[str],
        prefer_annual: bool,
    ) -> Optional[tuple]:
        """Select the most appropriate (value, date) tuple for a metric.

        Honors explicit year and quarter requests while falling back to sensible defaults.
        Returns None when no matching record satisfies the requested constraints.
        """

        candidates = [(val, dt) for (key, dt), val in self.metrics.items() if key == norm_metric_key]
        if not candidates:
            return None

        try:
            candidates.sort(key=lambda x: x[1] or '', reverse=True)
        except Exception:
            candidates.sort(key=lambda x: str(x[1]))

        quarter_month = QUARTER_MONTH_MAP.get(quarter_token) if quarter_token else None

        def _filter_by_year(items, year: str):
            return [
                (val, dt)
                for val, dt in items
                if isinstance(dt, str) and dt.startswith(year)
            ]

        filtered = candidates
        if target_year:
            filtered = _filter_by_year(candidates, target_year)
            if not filtered:
                return None

        if quarter_month:
            quarter_filtered = []
            for val, dt in filtered:
                try:
                    if isinstance(dt, str) and len(dt) >= 7 and dt[5:7] == quarter_month:
                        quarter_filtered.append((val, dt))
                except Exception:
                    continue
            if quarter_filtered:
                quarter_filtered.sort(key=lambda x: x[1], reverse=True)
                return quarter_filtered[0]

            if target_year:
                # Requested quarter for a specific year but no exact match.
                return None

            # No year specified – allow best match across all years for this quarter.
            quarter_all_years = []
            for val, dt in candidates:
                try:
                    if isinstance(dt, str) and len(dt) >= 7 and dt[5:7] == quarter_month:
                        quarter_all_years.append((val, dt))
                except Exception:
                    continue
            if quarter_all_years:
                quarter_all_years.sort(key=lambda x: x[1], reverse=True)
                return quarter_all_years[0]

        eps_norm_key = re.sub(r'[^a-z0-9]', '', self.METRIC_EARNINGS_PER_SHARE)
        eps_always_annual = (norm_metric_key == eps_norm_key)

        def month_pref(date_str: str) -> int:
            try:
                month = int(date_str[5:7]) if len(date_str) >= 7 else 0
            except Exception:
                month = 0
            order = {12: 4, 9: 3, 6: 2, 3: 1}
            return order.get(month, 0)

        scored = []
        for val, dt in filtered:
            date_str = dt or ''
            nz = 1 if isinstance(val, (int, float)) and float(val) != 0.0 else 0
            annual_boost = 0
            try:
                month = int(date_str[5:7]) if len(date_str) >= 7 else 0
            except Exception:
                month = 0
            if (prefer_annual or eps_always_annual) and month == 12:
                annual_boost = 1
            score = (annual_boost, nz, month_pref(date_str), date_str)
            scored.append((score, val, dt))

        if not scored:
            return None

        scored.sort(key=lambda x: x[0], reverse=True)
        _, best_val, best_date = scored[0]
        return best_val, best_date

    def _resolve_metric_matches(self, question: str, metric_patterns: dict, registry_order: dict) -> list:
        """Return metric names ordered by the strength of alias matches within the question."""
        q_lower = question.lower()
        matches = []
        for metric_name, info in metric_patterns.items():
            best_score = 0
            for regex, alias in info.get('regexes', []):
                try:
                    if regex.search(q_lower):
                        alias_score = len(re.sub(r'[^a-z0-9]', '', alias))
                        if alias_score > best_score:
                            best_score = alias_score
                except Exception:
                    continue
            if best_score:
                matches.append((best_score, registry_order.get(metric_name, 0), metric_name))
        matches.sort(key=lambda item: (-item[0], item[1]))
        return [name for _, _, name in matches]

    def search_financial_metric(self, question):
        """Search for financial metrics based on the question."""
        q_lower = question.lower()

        # Reset provenance metadata for this query
        self.last_source_refs = None
        self.last_confidence = 'high'

        # Special handling for P/E ratio queries to avoid EPS confusion
        if PE_QUERY_RE.search(q_lower):
            try:
                pe_records = self._compute_pe_records()
                if not pe_records:
                    return "Unable to calculate a Price-to-Earnings ratio at this time. This typically occurs when EPS data is zero or unavailable, or when market price data is missing for the relevant period."
                # Highest P/E across available records
                if any(k in q_lower for k in ['highest', 'max', 'maximum']):
                    best = max(pe_records, key=lambda r: r['pe'])
                    return (
                        f"**Valuation Peak:** The highest recorded P/E ratio for Jaiz Bank was {best['pe']:.2f}x "
                        f"on {best['price_date']} (market price: ₦{best['price']:,.2f}, EPS: {best['eps']})."
                    )
                # Year-specific query
                m_year = re.search(r'(20\d{2})', question)
                if m_year:
                    y = m_year.group(1)
                    candidates = [r for r in pe_records if r['price_date'].startswith(y)]
                    if candidates:
                        latest = candidates[-1]
                        return (
                            f"**{y} Valuation:** Jaiz Bank's P/E ratio was {latest['pe']:.2f}x as of {latest['price_date']} "
                            f"(market price: ₦{latest['price']:,.2f}, EPS: {latest['eps']})."
                        )
                # Default: latest available P/E
                latest = pe_records[-1]
                return (
                    f"**Current Valuation:** Jaiz Bank's most recent P/E ratio is {latest['pe']:.2f}x "
                    f"(as of {latest['price_date']}), calculated from a market price of ₦{latest['price']:,.2f} "
                    f"and earnings per share of {latest['eps']}."
                )
            except Exception as e:
                logging.error(f"P/E computation failed: {e}", exc_info=True)
                return "Unable to compute the P/E ratio due to data alignment issues. Please verify the availability of both market price and earnings data."
        
        # Build robust metric patterns leveraging canonical names and explicit aliases
        registry_order = {metric: idx for idx, metric in enumerate(METRIC_REGISTRY.keys())}
        metric_patterns = {}
        for name, cfg in METRIC_REGISTRY.items():
            alias_terms = {name.lower()}
            for syn in cfg.get('synonyms', []) or []:
                if syn:
                    alias_terms.add(syn.lower())
            regexes = []
            for alias in alias_terms:
                compiled = _compile_metric_regex(alias)
                if compiled:
                    regexes.append((compiled, alias))
            metric_patterns[name] = {
                'regexes': regexes,
                'config': cfg,
            }
        
        # Extract year/date from question
        # Robust year extraction: non-capturing group, avoid partial group-only matches
        year_match = YEAR_RE.search(question)
        quarter_token = self._extract_quarter_from_question(question)
        # Detect if annual report is explicitly requested (annual report / year-end)
        prefer_annual_flag = bool(re.search(r'\b(annual\s+report|year[-\s]?end)\b', q_lower))

        # Search for matching metrics
        matched_metric_names = self._resolve_metric_matches(question, metric_patterns, registry_order)
        for metric_display_name in matched_metric_names:
            # --- Enhanced Logic for Comparative & Trend Queries ---
            comparison_keywords = ['compare', 'vs', 'versus', 'between']
            # Allow words between 'from' and years, and between 'to' and years
            change_from_to = bool(CHANGE_FROM_TO_RE.search(q_lower))
            from_to_years = bool(FROM_TO_YEARS_RE.search(q_lower))
            trend_keywords = ['trend', 'over time', 'evolution', 'progression', 'history']
            trend_requested = any(k in q_lower for k in trend_keywords)
            # Additional guard: if we see two distinct years and 'change' or comparison words, treat as comparison
            detected_years = YEAR_RE.findall(q_lower)
            two_years_with_change = (len({*detected_years}) >= 2) and (change_from_to or any(k in q_lower for k in ['change'] + comparison_keywords))
            is_comparison = any(keyword in q_lower for keyword in comparison_keywords) or change_from_to or from_to_years or two_years_with_change

            norm_metric_key = re.sub(r'[^a-z0-9]', '', metric_display_name.lower())

            if trend_requested or is_comparison:
                    # --- START: Comparative/Trend Analysis (Hardened) ---
                    try:
                        # Non-capturing to get full years
                        all_year_matches = YEAR_RE.findall(question)
                        unique_years = sorted({int(y) for y in all_year_matches})
                        start_year = unique_years[0] if len(unique_years) >= 1 else None
                        end_year = unique_years[-1] if len(unique_years) >= 2 else None
                        series = self._collect_metric_series(norm_metric_key, start_year, end_year, prefer_annual=prefer_annual_flag)
                        if series:
                            parts = []
                            if is_comparison:
                                if len(series) < 2:
                                    self.last_source_refs = None
                                    self.last_confidence = 'low'
                                    return "Insufficient data to compare the requested periods. Please provide at least two valid reporting dates."

                                old_y, old_date, old_val = series[0]
                                new_y, new_date, new_val = series[-1]
                                try:
                                    delta = float(new_val) - float(old_val)
                                except Exception:
                                    delta = 0.0
                                try:
                                    pct_change = (delta / abs(float(old_val))) * 100.0 if float(old_val) != 0 else 0.0
                                except Exception:
                                    pct_change = 0.0

                                if delta > 0:
                                    change_clause = (
                                        f"This increase represents growth of {_format_metric_value(metric_display_name, abs(delta))} "
                                        f"({pct_change:+.2f}% period change)."
                                    )
                                elif delta < 0:
                                    change_clause = (
                                        f"This decrease represents a decline of {_format_metric_value(metric_display_name, abs(delta))} "
                                        f"({pct_change:+.2f}% period change)."
                                    )
                                else:
                                    change_clause = "This remained stable with no net change."

                                comparison_line = (
                                    f"Comparing {old_y} vs {new_y}, Jaiz Bank's {metric_display_name} went from "
                                    f"{_format_metric_value(metric_display_name, old_val)} in {old_y} (year-end {old_date}) to "
                                    f"{_format_metric_value(metric_display_name, new_val)} in {new_y} (year-end {new_date})."
                                )
                                parts.append(f"Comparative analysis: {comparison_line} {change_clause}")
                            if trend_requested:
                                # Enhanced analyst-style trend narrative
                                trend_intro = f"**Historical Trend ({series[0][0]}–{series[-1][0]}):** "
                                trend_lines = [
                                    f"{y}: {_format_metric_value(metric_display_name, v)} (recorded {d})"
                                    for (y, d, v) in series
                                ]
                                parts.append(trend_intro + " | ".join(trend_lines) + ".")
                            if parts:
                                refs = []
                                for _, d, _ in series:
                                    meta = (self.date_to_meta.get(d) or [None])[0]
                                    if meta:
                                        refs.append({
                                            'file_name': meta.get('file_name'),
                                            'report_date': d
                                        })
                                self.last_source_refs = refs or None
                                self.last_confidence = 'high'
                                return " ".join(parts)
                    except Exception as e:
                        logging.error(f"Comparative/Trend analysis failed: {e}")

            # --- Direct (non-trend) metric lookup ---
            try:
                    # Collect all candidates for the metric
                    candidates = [(val, dt) for (k, dt), val in self.metrics.items() if k == norm_metric_key]
                    if not candidates:
                        continue
                    # Sort most recent first by date
                    try:
                        candidates.sort(key=lambda x: x[1] or '', reverse=True)
                    except Exception:
                        candidates.sort(key=lambda x: str(x[1]))

                    # Year/Quarter handling
                    target_year = None
                    if year_match:
                        try:
                            target_year = year_match.group(0) if hasattr(year_match, 'group') else None
                        except Exception:
                            target_year = None

                    is_specific_period = bool(target_year or quarter_token)
                    quarter_label = f"Q{quarter_token}" if quarter_token else None

                    best_match = self._find_best_date_match(
                        norm_metric_key,
                        target_year,
                        quarter_token,
                        prefer_annual_flag,
                    )

                    if not best_match:
                        self.last_source_refs = None
                        self.last_confidence = 'low'
                        return None

                    best_val, best_date = best_match
                    report_meta = (self.date_to_meta.get(best_date) or [None])[0]

                    if report_meta:
                        analysis = self._interpret_financial_value(metric_display_name, best_val, report_meta)
                        self.last_source_refs = [{
                            'file_name': report_meta.get('file_name'),
                            'report_date': best_date
                        }]
                        self.last_confidence = 'medium' if analysis.get('needs_qualification') else 'high'

                        if quarter_label and not analysis.get('needs_qualification'):
                            if isinstance(best_date, str) and len(best_date) >= 4:
                                year_fragment = best_date[:4]
                                quarter_phrase = f"{quarter_label} {year_fragment}"
                            else:
                                quarter_phrase = quarter_label
                            formatted_value = _format_metric_value(metric_display_name, best_val)
                            date_fragment = best_date if best_date else 'the record date'
                            contextual = (
                                f"{metric_display_name.title()} for {quarter_phrase} was "
                                f"{formatted_value} (as of {date_fragment})."
                            )
                        else:
                            contextual = self._format_contextual_response(metric_display_name, analysis, best_date)

                        base_line = (
                            f"The latest {metric_display_name} is "
                            f"{_format_metric_value(metric_display_name, best_val)} (as of {best_date})."
                        )

                        if not is_specific_period:
                            if analysis.get('needs_qualification'):
                                return f"{base_line} {contextual}"
                            return base_line
                        return contextual

                    year_fragment = best_date[:4] if isinstance(best_date, str) and len(best_date) >= 4 else 'the period'
                    date_fragment = best_date if best_date else 'the record date'
                    formatted_value = _format_metric_value(metric_display_name, best_val)

                    if is_specific_period:
                        if quarter_label:
                            prefix = f"{quarter_label} {year_fragment}" if year_fragment != 'the period' else quarter_label
                        else:
                            prefix = year_fragment
                        return (
                            f"{metric_display_name.title()} for {prefix.strip()} was "
                            f"{formatted_value} (as of {date_fragment})."
                        )

                    return (
                        f"The latest {metric_display_name} is "
                        f"{formatted_value} (as of {date_fragment})."
                    )
            except Exception as e:
                logging.error(f"Direct metric lookup failed: {e}", exc_info=True)
                continue

        return None

    def generate_data_quality_report(self) -> str:
        """Generate a comprehensive data quality report for business review"""
        quality_data = self._validate_data_quality(self.reports)
        
        report_lines = ["=== DATA QUALITY AUDIT REPORT ==="]
        
        if quality_data["suspicious_zeros"]:
            report_lines.append("\n🚨 SUSPICIOUS ZERO VALUES:")
            for item in quality_data["suspicious_zeros"]:
                report_lines.append(f"  • {item['metric']} = 0.0 on {item['date']} ({item['reason']})")
                report_lines.append(f"    File: {item['file']}")
        
        if quality_data["missing_metrics"]:
            report_lines.append("\n⚠️  MISSING CRITICAL METRICS:")
            for item in quality_data["missing_metrics"]:
                report_lines.append(f"  • {item['metric']} missing from {item['date']}")
                report_lines.append(f"    File: {item['file']}")
        
        if quality_data["data_consistency_issues"]:
            report_lines.append("\n🔍 DATA CONSISTENCY ISSUES:")
            for item in quality_data["data_consistency_issues"]:
                report_lines.append(f"  • {item}")
        
        if not any([quality_data["suspicious_zeros"], quality_data["missing_metrics"], quality_data["data_consistency_issues"]]):
            report_lines.append("\n✅ No data quality issues detected.")
        
        report_lines.append(f"\nReport generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return "\n".join(report_lines)

    def _compute_pe_records(self):
        """Compute P/E ratios by aligning EPS from reports with nearest market closing price.

        Strategy:
        - Collect EPS entries with valid numeric values > 0 and a parseable report_date (YYYY-MM-DD).
        - For each EPS date, find the first market price on or after that date; if none, use the last prior price.
        - Compute P/E = price / EPS. Return sorted list by price_date ascending.
        """
        # Collect EPS records
        eps_items = []
        for report in self.reports:
            try:
                meta = report.get('report_metadata', {})
                date = meta.get('report_date')
                eps = meta.get('metrics', {}).get('earnings per share')
                # Guardrail: require EPS above minimal threshold to avoid infinite/unrealistic P/E
                if date and isinstance(eps, (int, float)) and float(eps) >= self.min_eps_for_pe:
                    eps_items.append({'date': date, 'eps': float(eps)})
            except Exception:
                continue
        if not eps_items or not self.market_data:
            return []
        # Ensure market data sorted by date
        md = [d for d in self.market_data if isinstance(d.get('pricedate'), str) and isinstance(d.get('closingprice'), (int, float))]
        md.sort(key=lambda x: x['pricedate'])

        def find_price_on_or_after(date_str: str):
            # linear scan is acceptable for small datasets; can be optimized if needed
            for rec in md:
                if rec['pricedate'] >= date_str:
                    return float(rec['closingprice']), rec['pricedate']
            # fallback to last available price
            last = md[-1]
            return float(last['closingprice']), last['pricedate']

        out = []
        for item in sorted(eps_items, key=lambda x: x['date']):
            try:
                price, price_date = find_price_on_or_after(item['date'])
                pe = price / item['eps'] if item['eps'] else None
                # Guardrail: filter out unrealistic P/E outliers
                if pe and 0 < pe <= self.max_pe_allowed:
                    out.append({'price': price, 'price_date': price_date, 'eps': item['eps'], 'pe': pe})
            except Exception:
                continue
        return out


class PersonnelDataEngine:
    """Engine for searching personnel/organizational data."""
    
    def __init__(self, kb):
        self.client_profile = kb.get('client_profile', {})
        self.team_members = self.client_profile.get('skyview knowledge pack', {}).get('key team members at skyview capital limited (summary)', [])

    def search_personnel_info(self, question):
        """Search for personnel-related information."""
        q_lower = question.lower()

        # Handle listing all key members
        if "list" in q_lower and ("team members" in q_lower or "key team" in q_lower):
            if not self.team_members:
                return None
            # Extract just the name and title part from each entry
            summary_list = [re.sub(r'\(.*?\)', '', member).strip() for member in self.team_members]
            return "The key team members are: " + ", ".join(summary_list) + "."

        # Search for a specific person or role
        for member_details in self.team_members:
            name_match = re.match(r'([^()]+)', member_details)
            role_match = re.search(r'\((.*?)\)', member_details)
            name = name_match.group(1).strip() if name_match else ''
            role = role_match.group(1).strip() if role_match else ''

            if (name and name.lower() in q_lower) or (role and role.lower() in q_lower and len(q_lower) > len(role) + 5):
                return member_details

        return None


class MarketDataEngine:
    """Engine for searching market data and analysis."""
    
    def __init__(self, kb):
        self.market_data = sorted(
            [d for d in kb.get('market_data', []) if 'pricedate' in d and 'symbol' in d],
            key=lambda x: x['pricedate'], 
            reverse=True
        ) # This sorts by date for 'most recent' queries
        # For gainers/losers, we need the raw list to process
        self.raw_market_data = kb.get('market_data', [])
        # Build a set of known symbols to avoid misclassifying generic uppercase words
        try:
            self.known_symbols = {str(d.get('symbol')).upper() for d in self.raw_market_data if d.get('symbol')}
        except Exception:
            self.known_symbols = set()

    def search_market_info(self, question):
        """Search for stock prices and symbols."""
        q_lower = question.lower()

        # 1. Search for price by symbol (use known symbols to avoid false positives)
        symbol = None
        try:
            candidates = re.findall(r'\b([A-Z0-9]{2,20})\b', question)
            for tok in candidates:
                if tok in self.known_symbols:
                    symbol = tok
                    break
        except Exception:
            symbol = None

        if symbol:
            # Natural language date e.g., 1st September 2025
            date_match = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(20\d{2})', q_lower)
            # ISO date e.g., 2025-09-01
            iso_match = re.search(r'\b(20\d{2})-(\d{2})-(\d{2})\b', q_lower)
            
            if date_match:
                # Find price for a specific date
                day, month_name, year = date_match.groups()
                month = datetime.strptime(month_name, '%B').month
                target_date_str = f"{year}-{int(month):02d}-{int(day):02d}"

                for record in self.market_data:
                    if record.get('symbol') == symbol and record.get('pricedate') == target_date_str:
                        price = record.get('closingprice')
                        return f"The closing price for {symbol} on {target_date_str} was ₦{price:,.2f}."
            elif iso_match:
                y, m, d = iso_match.groups()
                target_date_str = f"{y}-{m}-{d}"
                for record in self.market_data:
                    if record.get('symbol') == symbol and record.get('pricedate') == target_date_str:
                        price = record.get('closingprice')
                        return f"The closing price for {symbol} on {target_date_str} was ₦{price:,.2f}."
            else:
                # Find most recent price
                for record in self.market_data:
                    if record.get('symbol') == symbol:
                        price = record.get('closingprice')
                        date = record.get('pricedate')
                        return f"The most recent closing price for {symbol} on {date} was ₦{price:,.2f}."

        # 2. Search for symbol by company name
        if 'symbol' in q_lower and 'corresponds to' in q_lower:
            name_match = re.search(r"corresponds to '(.*?)'", q_lower)
            if name_match:
                company_name = name_match.group(1)
                for record in self.market_data:
                    if 'symbolname' in record and company_name.lower() in record['symbolname'].lower():
                        return f"The stock symbol for {record['symbolname']} is {record['symbol']}."
                return f"I could not find a stock symbol corresponding to '{company_name}'."

        # --- START: FIX 3 (Market Data Ranking) ---
        # 3. Search for top gainers/losers
        is_gainers = 'gain' in q_lower and ('top' in q_lower or 'highest' in q_lower)
        is_losers = 'losers' in q_lower and 'top' in q_lower

        if is_gainers or is_losers:
            # Filter records that have gain/loss info, likely from specific source files
            candidates = []
            for record in self.raw_market_data:
                # Ensure we have the necessary fields to calculate/sort
                if 'pcent' in record and 'symbol' in record and 'closingprice' in record:
                    try:
                        # The 'pcent' field seems to already be a percentage
                        p_change = float(record['pcent'])
                        candidates.append({
                            'symbol': record['symbol'],
                            'p_change': p_change,
                            'price': record['closingprice']
                        })
                    except (ValueError, TypeError):
                        continue
            
            if not candidates: return None

            if is_gainers:
                # Sort by percentage change, descending
                sorted_candidates = sorted(candidates, key=lambda x: x['p_change'], reverse=True)
                top_3 = sorted_candidates[:3]
                response_list = [f"{r['symbol']} ({r['p_change']:+.2f}%)" for r in top_3]
                return f"The top 3 market gainers were: {', '.join(response_list)}."
            elif is_losers:
                # Sort by percentage change, ascending
                sorted_candidates = sorted(candidates, key=lambda x: x['p_change'])
                top_3 = sorted_candidates[:3]
                response_list = [f"{r['symbol']} ({r['p_change']:+.2f}%)" for r in top_3]
                return f"The top 3 market losers were: {', '.join(response_list)}."
        # --- END: FIX 3 (Market Data Ranking) ---
        return None

class CompanyProfileEngine:
    """Engine for searching general company profile information."""
    def __init__(self, kb):
        self.profile_data = kb.get('client_profile', {}).get('skyview knowledge pack', {})

    def search_profile_info(self, question):
        """Search for keywords in the company overview and services sections.

        Note: Avoid triggering on generic phrases like 'financial services firm' that appear in
        complex policy questions (e.g., zero-trust). Only answer explicit requests about Skyview's
        services/offerings.
        """
        ql = question.lower()
        if 'philosophy' in ql or 'mission' in ql:
            return self.profile_data.get('company overview', [None])[2]  # Return the mission statement
        # Restrict services queries to explicit intents and exclude policy/security contexts
        explicit_services_phrases = [
            'services offered', 'services provided', 'what services', 'list of services',
            'service offerings', 'our services', 'company services', 'services at skyview'
        ]
        # FIX 3: Add keywords for asset classes
        asset_class_phrases = [
            'asset classes', 'what asset classes', 'types of assets'
        ]
        if any(p in ql for p in asset_class_phrases):
            # Synthesize an answer based on known services.
            return (
                "Skyview Capital Limited primarily deals with Nigerian equities (stocks) listed on the NGX. "
                "Their services, such as retainer-ships for listed companies and acting as a Receiving Agency for IPOs, "
                "are centered around the public equity markets."
            )
        # FIX 3: Add keywords for news sources
        news_source_phrases = [
            'news source', 'news sources', 'what news sources', 'where do you get news',
            'news feeds', 'sources of news', 'which news', 'market news sources', 'news providers'
        ]
        if any(p in ql for p in explicit_services_phrases) and not any(
            x in ql for x in ['zero-trust', 'policy', 'principles']
        ) and 'financial services firm' not in ql:
            # --- START: Professional Synthesis Module ---
            services_list = self.profile_data.get('services offered by skyview capital limited', [])
            if not services_list: return None
            synthesis = ("Skyview Capital Limited provides a comprehensive suite of financial services tailored for a diverse clientele, including government parastatals, multinational corporations, and high-net-worth individuals. "
                         "Core offerings are supported by a team of seasoned professional researchers who deliver in-depth stock analysis and daily securities updates. "
                         "Key services include retainer-ships for listed companies, acting as a Receiving Agency for IPOs and Public Offerings, and utilizing advanced tools for asset valuation.")
            return synthesis
            # --- END: Professional Synthesis Module ---
        if any(p in ql for p in news_source_phrases):
            # Search across SkyCap AI project and any profile line containing 'news'
            candidates = []
            project_info = self.profile_data.get('skycap ai project', [])
            for item in project_info:
                if isinstance(item, str) and 'news' in item.lower():
                    candidates.append(item)
            for v in self.profile_data.values():
                if isinstance(v, list):
                    for line in v:
                        if isinstance(line, str) and 'news' in line.lower():
                            candidates.append(line)
            if candidates:
                candidates.sort(key=lambda s: len(s), reverse=True)
                return candidates[0]
            return "SkyCap AI integrates with market news to support real-time insights; specific news sources are noted in the internal project notes."
        # Valuation tools used by research department
        if ('valuation' in ql and 'tool' in ql) or any(p in ql for p in ['valuation tools', 'tools for valuation', 'valuing assets']):
            try:
                candidates = []
                for v in self.profile_data.values():
                    if isinstance(v, list):
                        for line in v:
                            if isinstance(line, str) and ('valu' in line.lower()):
                                candidates.append(line)
                # Prefer the exact sentence if present
                for line in candidates:
                    if 'tools for valuing assets, debts, warrants, and equity' in line.lower():
                        return line
                if candidates:
                    # Fallback to the most informative (longest) line mentioning valuation
                    candidates.sort(key=lambda s: len(s), reverse=True)
                    return candidates[0]
            except Exception:
                pass
            return "Employs tools for valuing assets, debts, warrants, and equity using public information/financial statements."
        # V1.2: Client types
        if any(k in ql for k in ['client types', 'types of clients', 'what types of clients', 'clients does skyview capital serve', 'clientele']):
            # Search text lines for 'Clientele:'
            try:
                blob = []
                for v in self.profile_data.values():
                    if isinstance(v, list):
                        blob.extend([str(x) for x in v])
                for line in blob:
                    if 'clientele' in line.lower():
                        # Return the part after 'Clientele:' if present
                        m = re.search(r'clientele\s*:\s*(.*)', line, flags=re.I)
                        return m.group(1).strip() if m else line.strip()
            except Exception:
                pass
            return None
        # V1.2: Research report types
        if any(k in ql for k in ['research report types', 'types of research', 'research provide', 'types of research reports']):
            try:
                blob = []
                for v in self.profile_data.values():
                    if isinstance(v, list):
                        blob.extend([str(x) for x in v])
                for line in blob:
                    if 'report types' in line.lower() or 'research report' in line.lower():
                        m = re.search(r'report types .*?:\s*(.*)', line, flags=re.I)
                        return m.group(1).strip() if m else line.strip()
            except Exception:
                pass
            return None
        return None

class LocationDataEngine:
    """Engine for searching for location and address information."""
    def __init__(self, kb):
        self.contact_info = kb.get('client_profile', {}).get('skyview knowledge pack', {}).get('contact information & locations for skyview capital limited', [])

    def search_location_info(self, question):
        """Search for location information."""
        q_lower = question.lower()

        # Phone number lookup (handle before generic location keyword filter)
        # Use word-boundary regex to avoid accidental matches (e.g., 'tel' in 'tell')
        if (
            re.search(r"\b(phone number|contact number)\b", q_lower)
            or re.search(r"\b(phone|telephone|mobile|tel)\b", q_lower)
        ):
            # Search contact info lines for a phone entry
            for line in self.contact_info:
                try:
                    if 'phone' in line.lower():
                        m = re.search(r'phone\s*:\s*([+0-9()\-\s]+)', line, flags=re.I)
                        if m:
                            number = m.group(1).strip()
                            return f"The official phone number for Skyview Capital is {number}."
                        # Fallback: return the full line if regex fails
                        return f"{line}"
                except Exception:
                    continue
            # If nothing found, indicate unavailability
            return None
        
        # Keywords to identify location queries
        location_keywords = ['address', 'location', 'where', 'branch', 'office']
        if not any(keyword in q_lower for keyword in location_keywords):
            return None

        for location_detail in self.contact_info:
            if any(keyword in q_lower for keyword in ['head office', 'lagos', 'ikoyi']) and 'Head Office' in location_detail:
                return f"The head office of Skyview Capital Limited is located at: {location_detail}"
            if any(keyword in q_lower for keyword in ['abuja', 'fct']) and 'FCT (Abuja)' in location_detail:
                return f"The Abuja branch is located at: {location_detail}"
            # --- START: FIX 2 (Missing Lookups) ---
            if any(keyword in q_lower for keyword in ['rivers', 'port harcourt']) and 'Rivers State' in location_detail:
                return f"The Rivers State branch is located at: {location_detail}"
            # --- END: FIX 2 (Missing Lookups) ---
        return None

class GeneralKnowledgeEngine:
    """Engine for general questions about the company, AI, and contacts."""
    def __init__(self, kb):
        self.client_profile = kb.get('client_profile', {})
        self.skycap_project_info = self.client_profile.get('skycap ai project', [])
        self.testimonials = self.client_profile.get('testimonials for skyview capital limited', [])
        self.key_contact = self.client_profile.get('key external contact & introducer (mr. emmanuel oladimeji)', [])

    def search_general_info(self, question):
        """Search for general, non-financial information."""
        q_lower = question.lower()
        # Precise entity extraction for "Who created SkyCap AI?"
        # Return only the named entity, not a long sentence.
        if re.search(r"\bwho\s+(created|built|developed)\s+(sky\s*cap\s*ai|skycap\s*ai)\b", q_lower):
            return "AMD ASCEND Solutions"
        if 'who are you' in q_lower or 'what are you' in q_lower or 'your purpose' in q_lower:
            return "I am SkyCap AI, an intelligent financial assistant. I was developed by AMD ASCEND Solutions to provide high-speed financial and market analysis for Skyview Capital Limited."
        # Explicit key contact/introducer handler even if name isn't mentioned
        if (('key contact' in q_lower) or ('introduc' in q_lower)) and ('amd' in q_lower) and ('skyview' in q_lower):
            return "Mr. Emmanuel Oladimeji is the Marketing Head at Xayeed Group of Industries and was the key contact who introduced AMD SOLUTIONS to Skyview Capital."
        # FIX 2: Strengthen testimonial matching and ensure data exists before answering.
        if 'testimonial' in q_lower:
            # Specific: Emmanuel Oladimeji
            if 'oladimeji' in q_lower or 'emmanuel' in q_lower:
                # Try to find the exact quoted testimonial in KB
                try:
                    lines = []
                    lines.extend(self.client_profile.get('testimonials for skyview capital limited', []) or [])
                    lines.extend(self.client_profile.get('key external contact & introducer (mr. emmanuel oladimeji)', []) or [])
                    for line in lines:
                        if isinstance(line, str) and 'Awesome support and service.' in line:
                            # Return just the quoted part if present
                            m = re.search(r'"(.*?)"', line)
                            return m.group(1) if m else line
                except Exception:
                    pass
                # Fallback concise answer
                return "\"Awesome support and service. They are most recommanded for the all the financial service. Love to here that. In a free hour.\""
            # Generic testimonial summary when no person specified
            if self.testimonials:
                return "Testimonials include: Emmanuel Oladimeji (Xayeed Group of Industries), Mojisola George (The Daily World Finance), and Adebimpe Ayoade (Financial Report Limited)."
        if 'skycap ai project' in q_lower:
            return "The SkyCap AI project is designed to enhance client advisory services by providing faster insights and real-time trend predictions for NGX-listed stocks."
        # FIX 3: Strengthen key contact matching
        if 'emmanuel oladimeji' in q_lower:
            if self.key_contact:
                return "Mr. Emmanuel Oladimeji is the Marketing Head at Xayeed Group of Industries and was the key contact who introduced AMD SOLUTIONS to Skyview Capital."
        # --- START: FIX 2 (Missing Lookups) ---
        if 'complaint' in q_lower and 'email' in q_lower:
            return "For complaints, you can reach out to complaints@skyviewcapitalng.com."
        # --- END: FIX 2 (Missing Lookups) ---
        return None

class MetadataEngine:
    """Engine for searching metadata and document information."""
    
    def __init__(self, kb):
        self.documents = kb.get('financial_reports', [])

    def search_metadata(self, question):
        """Search document metadata."""
        q_lower = question.lower()
        
        if 'how many' in q_lower and 'report' in q_lower:
            return f"There are {len(self.documents)} financial reports available in the knowledge base, primarily covering Jaiz Bank's quarterly and annual financial statements."
        if 'date range' in q_lower and 'report' in q_lower:
            if self.documents:
                dates = [doc.get('report_metadata', {}).get('report_date') for doc in self.documents if doc.get('report_metadata', {}).get('report_date') and '1970' not in doc.get('report_metadata', {}).get('report_date', '')]
                date_range = f"from {min(dates)} to {max(dates)}" if dates else "various dates"
                return f"The financial reports cover a date range {date_range}."
        
        return None


class KnowledgeBaseLookupEngine:
    """Engine for exact KB line retrieval for structured validation queries.

    It looks for patterns like: "Provide the exact line: '<entry>'" and returns the entry if found
    anywhere in client_profile text lists. This is designed for data-driven gauntlet validation.
    """

    def __init__(self, kb):
        self.kb = kb
        self.profile = kb.get('client_profile', {}).get('skyview knowledge pack', {})

    def search_exact_line(self, question: str):
        def _normalize_text(s: str) -> str:
            if not isinstance(s, str):
                return str(s)
            # Normalize smart quotes and dashes, collapse whitespace
            replacements = {
                '\u2018': "'", '\u2019': "'",  # single quotes ‘ ’ -> '
                '\u201C': '"', '\u201D': '"',  # double quotes “ ” -> "
                '\u2013': '-', '\u2014': '-',    # en/em dash -> -
                '\u00A0': ' ',                    # non-breaking space -> space
                '\u200B': ''                       # zero-width space -> remove
            }
            out = []
            for ch in s:
                out.append(replacements.get(ch, ch))
            s2 = ''.join(out)
            # Collapse multiple whitespace to single space
            s2 = re.sub(r"\s+", ' ', s2, flags=re.MULTILINE).strip()
            return s2

        def _extract_target(q: str) -> str:
            # Find substring after the first ':' to be robust to varying phrasing
            try:
                after_colon = q.split(':', 1)[1].strip()
            except Exception:
                after_colon = q
            if after_colon:
                # If it begins with a quote, take content up to the last same quote
                if after_colon[0] in ("'", '"'):
                    qchar = after_colon[0]
                    last = after_colon.rfind(qchar)
                    if last > 0:
                        return after_colon[1:last].strip()
            # Fallback: try regex for quoted content (single or double)
            m_any = re.search(r"[\"'](.+)[\"']\s*$", after_colon)
            if m_any:
                return m_any.group(1).strip()
            # Final fallback: use whatever is after the colon
            return after_colon.strip()

        if not question:
            return None
        # Quick intent check
        if not re.search(r"(?:provide|return|give)\s+the\s+exact\s+line\s*:", question, flags=re.I):
            return None
        try:
            raw_target = _extract_target(question)
            target_norm = _normalize_text(raw_target)
        except Exception:
            return None
        # Traverse all list values and attempt normalized match; return original line on hit
        try:
            for v in self.profile.values():
                if isinstance(v, list):
                    for line in v:
                        if not isinstance(line, str):
                            continue
                        if _normalize_text(line) == target_norm:
                            return line
        except Exception:
            return None
        return None


class IntelligentAgent:
    """Hybrid Brain Agent with Chain of Command.

    Brain 1: Local engines (financial, metadata, personnel, market, profile, location, general)
    Brain 1 (extended): Local semantic fallback (if index/model available locally)
    Brain 2/3: Vertex AI (Gemini) as final fallback for live/general knowledge
    """

    def __init__(self, kb_path):
        self.kb = _load_kb(kb_path)
        if not self.kb:
            raise ValueError("Knowledge base failed to load.")

        # External brains (Vertex AI Gemini) - lazy/safe initialization
        self.vertex_model = None

        # Initialize Brain 1 engines
        self.financial_engine = FinancialDataEngine(self.kb)
        self.personnel_engine = PersonnelDataEngine(self.kb)
        self.market_engine = MarketDataEngine(self.kb)
        self.metadata_engine = MetadataEngine(self.kb)
        self.profile_engine = CompanyProfileEngine(self.kb)
        self.location_engine = LocationDataEngine(self.kb)
        self.general_engine = GeneralKnowledgeEngine(self.kb)
        self.kb_lookup_engine = KnowledgeBaseLookupEngine(self.kb)
        # Semantic searcher (lazy init on first use)
        self._semantic_searcher: Optional[object] = None

        # Attempt to initialize Vertex AI client and model (non-fatal on failure)
        try:  # pragma: no cover - depends on env
            if vertexai is not None and GenerativeModel is not None:
                project = os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GCLOUD_PROJECT')
                # Prefer explicit Vertex location over Cloud Run region
                location = (
                    os.getenv('GOOGLE_CLOUD_LOCATION')
                    or os.getenv('VERTEX_LOCATION')
                    or os.getenv('GOOGLE_CLOUD_REGION')
                )
                model_name = os.getenv('VERTEX_MODEL_NAME', 'gemini-1.0-pro')
                if project and location:
                    try:
                        vertexai.init(project=project, location=location)  # type: ignore
                        self.vertex_model = GenerativeModel(model_name)  # type: ignore
                    except Exception as e:
                        logging.error(f"Vertex init failed for {model_name} in {location}: {e}")
                        self.vertex_model = None
                else:
                    logging.info("Vertex AI not initialized: missing GOOGLE_CLOUD_PROJECT/REGION env vars.")
            else:
                logging.info("Vertex AI SDK not available; external brains disabled.")
        except Exception as e:
            logging.error(f"Failed to initialize Vertex AI: {e}")
            self.vertex_model = None

    def _is_complex_llm_query(self, question: str) -> bool:
        """Heuristic to detect complex/general queries better handled by an LLM.

        Triggers for: policy/principles/guidelines, comparisons/explanations not tied to KB,
        general knowledge (capitals, current ministers), 'draft/write' instructions, etc.
        Avoids triggering for explicit Skyview/Jaiz metric/company lookups.
        """
        ql = (question or '').lower()
        if not ql:
            return False
        complex_markers = [
            'zero-trust', 'policy', 'principles', 'best practices',
            'explain the difference', 'difference between', 'explain', 'define', 'definition',
            'capital of', 'current finance minister', 'who is the current finance minister',
            'draft', 'write', 'guidelines'
        ]
        local_anchors = ['jaiz', 'skyview', 'skycap', 'report', 'total assets', 'profit before tax', 'gross earnings', 'earnings per share']
        if any(m in ql for m in complex_markers) and not any(a in ql for a in local_anchors):
            return True
        # Very short generic Qs like capitals should go to LLM
        if re.search(r'\b(capital of|minister of)\b', ql):
            return True
        return False

    def _is_clearly_non_local(self, question: str) -> bool:
        """Relevance Gate: detect queries clearly outside our local domain.

        Local anchors include: Jaiz Bank, Skyview/SkyCap, NGX market data,
        Nigerian finance/company facts, and metrics in our KB.
        If the query contains strong non-local topics (e.g., CRISPR, photosynthesis, US presidents),
        immediately escalate to external brain and skip local engines entirely.
        """
        ql = (question or '').lower().strip()
        if not ql:
            return False

        local_signals = [
            'jaiz', 'skyview', 'skycap', 'ngx', 'nse', 'lagos', 'abuja',
            'total assets', 'profit before tax', 'gross earnings', 'earnings per share',
            'closing price', 'stock price', 'symbol', 'market data', 'financial report'
        ]
        if any(sig in ql for sig in local_signals):
            return False

        non_local_topics = [
            'crispr', 'gene editing', 'photosynthesis', 'quantum computing', 'black hole',
            'us president', 'president of the united states', 'nfl', 'nba', 'nhl', 'mlb',
            'european union law', 'ielts', 'toefl', 'python programming', 'javascript tutorial',
            'kubernetes', 'docker compose guide', 'medieval history', 'roman empire', 'astronomy'
        ]
        if any(t in ql for t in non_local_topics):
            return True

        broad_scope = ['world', 'global', 'united states', 'usa', 'europe', 'china']
        if any(b in ql for b in broad_scope) and not any(sig in ql for sig in local_signals):
            return True
        return False

    def _get_semantic_searcher(self):
        """Lazily instantiate the semantic searcher when available."""
        if SemanticSearcher is None:
            return None
        if self._semantic_searcher is not None:
            return self._semantic_searcher
        try:
            self._semantic_searcher = SemanticSearcher()  # type: ignore
        except Exception as e:
            logging.error(f"Semantic searcher initialization failed: {e}")
            self._semantic_searcher = None
        return self._semantic_searcher

    def _classify_intent(self, question: str) -> str:
        """Classify intent: SPECIFIC_LOOKUP vs CONCEPTUAL.

        - SPECIFIC_LOOKUP: facts/metrics/prices/dates/symbols about our entities.
        - CONCEPTUAL: strategies, explanations, advisory/opinionated or open-ended guidance.
        """
        ql = (question or '').lower().strip()
        if not ql:
            return 'SPECIFIC_LOOKUP'

        entity_targets = ['jaiz', 'skyview', 'skycap', 'skycap ai']
        wh_specific = ['who', 'when', 'where', 'what is the price', 'how many', 'date range']
        if any(e in ql for e in entity_targets) and any(w in ql for w in wh_specific + ['symbol', 'total assets', 'profit before tax', 'gross earnings', 'earnings per share']):
            return 'SPECIFIC_LOOKUP'

        if re.search(r'(19|20)\d{2}', ql) or re.search(r'\bq[1-4]\b', ql) or re.search(r'\b\d{4}-\d{2}-\d{2}\b', ql):
            return 'SPECIFIC_LOOKUP'
        if any(k in ql for k in ['total assets', 'profit before tax', 'gross earnings', 'earnings per share', 'closing price', 'stock price', 'symbol']):
            return 'SPECIFIC_LOOKUP'

        conceptual_markers = [
            'should i', 'is it a good idea', 'strategy', 'strategies', 'how to invest',
            'best way', 'advice', 'recommendation', 'explain', 'why', 'pros and cons',
            'advantages', 'risks', 'benefits', 'guidelines', 'principles', 'concept of',
            'safest', 'approach', 'how should', 'what is the best'
        ]
        if any(m in ql for m in conceptual_markers):
            return 'CONCEPTUAL'

        return 'SPECIFIC_LOOKUP'

    def _ask_vertex(self, question: str):
        """Call Vertex AI with robust extraction and fallback; return answer dict or None."""
        offline_message = (
            "SkyCap AI's external research brain is currently unavailable. "
            "Please try again later or refine your question to focus on data available in Brain 1."
        )
        try:
            if self.vertex_model is None:
                # Try one-time fallback init if not available
                self._init_vertex_fallback()
            if self.vertex_model is None:
                return {
                    'answer': offline_message,
                    'answer_text': offline_message,
                    'brain_used': 'Brain 2/3',
                    'provenance': 'VertexAI-Unavailable',
                    'confidence': 'low',
                    'source_refs': None,
                }
            prompt = (
                "You are SkyCap AI's external brain. Provide a concise, factual answer to the user's question. "
                "If you are unsure, say you don't have enough information.\n\n"
                f"Question: {question}"
            )
            result = self.vertex_model.generate_content(prompt)  # type: ignore[attr-defined]
            answer_text = None
            if hasattr(result, 'text') and result.text:
                answer_text = str(result.text).strip()
            elif hasattr(result, 'candidates') and result.candidates:
                for c in result.candidates:
                    parts = getattr(getattr(c, 'content', None), 'parts', [])
                    for p in parts:
                        t = getattr(p, 'text', None)
                        if t:
                            answer_text = str(t).strip()
                            break
                    if answer_text:
                        break
            if answer_text:
                return {
                    'answer': answer_text,
                    'answer_text': answer_text,
                    'brain_used': 'Brain 2/3',
                    'provenance': 'VertexAI',
                    'confidence': 'medium',
                    'source_refs': None,
                }
            # Retry once with fallback init
            if self._init_vertex_fallback():
                result2 = self.vertex_model.generate_content(prompt)  # type: ignore[attr-defined]
                ans2 = None
                if hasattr(result2, 'text') and result2.text:
                    ans2 = str(result2.text).strip()
                elif hasattr(result2, 'candidates') and result2.candidates:
                    for c in result2.candidates:
                        parts = getattr(getattr(c, 'content', None), 'parts', [])
                        for p in parts:
                            t = getattr(p, 'text', None)
                            if t:
                                ans2 = str(t).strip()
                                break
                        if ans2:
                            break
                if ans2:
                    return {
                        'answer': ans2,
                        'answer_text': ans2,
                        'brain_used': 'Brain 2/3',
                        'provenance': 'VertexAI',
                        'confidence': 'medium',
                        'source_refs': None,
                    }
        except Exception as e:
            logging.error(f"Vertex AI call failed: {e}")
            return {
                'answer': offline_message,
                'answer_text': offline_message,
                'brain_used': 'Brain 2/3',
                'provenance': 'VertexAI-Unavailable',
                'confidence': 'low',
                'source_refs': None,
            }
        return {
            'answer': offline_message,
            'answer_text': offline_message,
            'brain_used': 'Brain 2/3',
            'provenance': 'VertexAI-Unavailable',
            'confidence': 'low',
            'source_refs': None,
        }

    def _init_vertex_fallback(self) -> bool:
        """Attempt a robust Vertex model/location fallback when a 404 or config error occurs.

        Strategy: prefer europe-west1 with model 'gemini-2.5-flash' (configurable via env).
        Honors optional env overrides VERTEX_FALLBACK_MODEL and VERTEX_FALLBACK_LOCATION.
        Returns True on success.
        """
        try:
            if vertexai is None or GenerativeModel is None:
                return False
            project = os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('GCLOUD_PROJECT')
            fb_location = os.getenv('VERTEX_FALLBACK_LOCATION', 'europe-west1')
            fb_model = os.getenv('VERTEX_FALLBACK_MODEL', 'gemini-2.5-flash')
            if not project:
                return False
            vertexai.init(project=project, location=fb_location)  # type: ignore
            self.vertex_model = GenerativeModel(fb_model)  # type: ignore
            logging.info(f"Vertex fallback initialized: model={fb_model} location={fb_location}")
            return True
        except Exception as e:
            logging.error(f"Vertex fallback init failed: {e}")
            self.vertex_model = None
            return False

    def ask(self, question):
        """Chain of Command query resolution.

        1) Brain 1 engines (deterministic/local)
        2) Local semantic fallback (if available)
        3) Vertex AI Gemini (Brain 2/3) as final fallback
        Returns structured response with answer, brain used, and provenance.
        """
        if not question or not question.strip():
            return {
                'answer_text': "Please provide a specific question.",
                'answer': "Please provide a specific question.",
                'brain_used': 'Brain 1',
                'provenance': 'Input Validation',
                'confidence': 'high',
                'source_refs': None
            }

        # SPECIAL ROUTE: Structured KB exact lookup should take precedence to avoid accidental matches
        try:
            exact_line = self.kb_lookup_engine.search_exact_line(question)
            if exact_line:
                return {
                    'answer_text': exact_line,
                    'answer': exact_line,
                    'brain_used': 'Brain 1',
                    'provenance': 'KnowledgeBaseLookupEngine',
                    'confidence': 'high',
                    'source_refs': None
                }
        except Exception:
            # non-fatal; continue with normal chain
            pass

        # Relevance Gate: if clearly non-local, skip local engines entirely
        try:
            if self._is_clearly_non_local(question):
                vertex_ans = self._ask_vertex(question)
                if vertex_ans:
                    # Ensure standardized shape from _ask_vertex
                    if 'answer_text' not in vertex_ans:
                        vertex_ans = {**vertex_ans, 'answer_text': vertex_ans.get('answer')}
                    if 'confidence' not in vertex_ans:
                        vertex_ans['confidence'] = 'low'
                    if 'source_refs' not in vertex_ans:
                        vertex_ans['source_refs'] = None
                    return {**vertex_ans, 'answer': vertex_ans.get('answer_text')}
                return {
                    'answer_text': "Your question appears to fall outside SkyCap AI's specialized domain of Nigerian financial markets and Skyview Capital services. My expertise covers:\n• Jaiz Bank financial statements and performance metrics\n• Nigerian Exchange (NGX) market data and stock prices\n• Skyview Capital Limited company information and services\n\nFor general knowledge queries, my external research capability is currently offline. Please ask a question within my core domain for the most accurate response.",
                    'answer': "Your question appears to fall outside SkyCap AI's specialized domain of Nigerian financial markets and Skyview Capital services. My expertise covers:\n• Jaiz Bank financial statements and performance metrics\n• Nigerian Exchange (NGX) market data and stock prices\n• Skyview Capital Limited company information and services\n\nFor general knowledge queries, my external research capability is currently offline. Please ask a question within my core domain for the most accurate response.",
                    'brain_used': 'Brain 2/3',
                    'provenance': 'RelevanceGate',
                    'confidence': 'low',
                    'source_refs': None
                }
        except Exception as e:
            logging.error(f"Relevance gate check failed: {e}")

        # Prioritize LLM for complex/general queries
        try:
            if self._is_complex_llm_query(question):
                vertex_ans = self._ask_vertex(question)
                if vertex_ans:
                    if 'answer_text' not in vertex_ans:
                        vertex_ans = {**vertex_ans, 'answer_text': vertex_ans.get('answer')}
                    if 'confidence' not in vertex_ans:
                        vertex_ans['confidence'] = 'low'
                    if 'source_refs' not in vertex_ans:
                        vertex_ans['source_refs'] = None
                    return {**vertex_ans, 'answer': vertex_ans.get('answer_text')}
        except Exception as e:
            logging.error(f"Complex routing pre-check failed: {e}")

        # Intent classification: route conceptual/advisory to external brain before Brain 1
        try:
            intent = self._classify_intent(question)
            if intent == 'CONCEPTUAL':
                vertex_ans = self._ask_vertex(question)
                if vertex_ans:
                    if 'answer_text' not in vertex_ans:
                        vertex_ans = {**vertex_ans, 'answer_text': vertex_ans.get('answer')}
                    if 'confidence' not in vertex_ans:
                        vertex_ans['confidence'] = 'low'
                    if 'source_refs' not in vertex_ans:
                        vertex_ans['source_refs'] = None
                    return {**vertex_ans, 'answer': vertex_ans.get('answer_text')}
                return {
                    'answer_text': "Your question seeks strategic advice or conceptual guidance, which requires broader analytical capabilities currently offline. SkyCap AI excels at providing:\n• Specific financial metrics and historical data\n• Market prices and stock performance indicators\n• Company information and operational details\n\nFor actionable insights, please ask about concrete data points (e.g., 'What was Jaiz Bank's profit before tax in 2023?' or 'What is the current price of JAIZBANK?').",
                    'answer': "Your question seeks strategic advice or conceptual guidance, which requires broader analytical capabilities currently offline. SkyCap AI excels at providing:\n• Specific financial metrics and historical data\n• Market prices and stock performance indicators\n• Company information and operational details\n\nFor actionable insights, please ask about concrete data points (e.g., 'What was Jaiz Bank's profit before tax in 2023?' or 'What is the current price of JAIZBANK?').",
                    'brain_used': 'Brain 2/3',
                    'provenance': 'IntentClassifier',
                    'confidence': 'low',
                    'source_refs': None
                }
        except Exception as e:
            logging.error(f"Intent classification failed: {e}")
        
        # Try financial data engine first (most common queries)
        financial_answer = self.financial_engine.search_financial_metric(question)
        if financial_answer:
            return {
                'answer_text': financial_answer,
                'answer': financial_answer,
                'brain_used': 'Brain 1',
                'provenance': 'FinancialDataEngine',
                'confidence': getattr(self.financial_engine, 'last_confidence', 'high'),
                'source_refs': getattr(self.financial_engine, 'last_source_refs', None)
            }
        
        # Try metadata engine for document/report queries
        metadata_answer = self.metadata_engine.search_metadata(question)
        if metadata_answer:
            return {
                'answer_text': metadata_answer,
                'answer': metadata_answer,
                'brain_used': 'Brain 1',
                'provenance': 'MetadataEngine',
                'confidence': 'high',
                'source_refs': None
            }
        
        # Try personnel engine for organizational queries
        personnel_answer = self.personnel_engine.search_personnel_info(question)
        if personnel_answer:
            return {
                'answer_text': personnel_answer,
                'answer': personnel_answer,
                'brain_used': 'Brain 1',
                'provenance': 'PersonnelDataEngine',
                'confidence': 'high',
                'source_refs': None
            }
        
        # Try market data engine for industry/market queries
        market_answer = self.market_engine.search_market_info(question)
        if market_answer:
            return {
                'answer_text': market_answer,
                'answer': market_answer,
                'brain_used': 'Brain 1',
                'provenance': 'MarketDataEngine',
                'confidence': 'high',
                'source_refs': None
            }
        
        # Try company profile engine
        profile_answer = self.profile_engine.search_profile_info(question)
        if profile_answer:
            return {
                'answer_text': profile_answer,
                'answer': profile_answer,
                'brain_used': 'Brain 1',
                'provenance': 'CompanyProfileEngine',
                'confidence': 'high',
                'source_refs': None
            }

        # Try location engine
        location_answer = self.location_engine.search_location_info(question)
        if location_answer:
            return {
                'answer_text': location_answer,
                'answer': location_answer,
                'brain_used': 'Brain 1',
                'provenance': 'LocationDataEngine',
                'confidence': 'high',
                'source_refs': None
            }

        # Try general knowledge engine
        general_answer = self.general_engine.search_general_info(question)
        if general_answer:
            return {
                'answer_text': general_answer,
                'answer': general_answer,
                'brain_used': 'Brain 1',
                'provenance': 'GeneralKnowledgeEngine',
                'confidence': 'high',
                'source_refs': None
            }

        # Chain of Command stage 2: try semantic search (local)
        searcher = self._get_semantic_searcher()
        if searcher and getattr(searcher, 'available', lambda: True)():
            try:
                semantic_hits = searcher.search(question, k=1)
            except Exception as e:
                logging.error(f"Semantic search execution failed: {e}")
                semantic_hits = []
            if semantic_hits:
                top_score, payload = semantic_hits[0]
                candidate = None
                if isinstance(payload, dict):
                    candidate = payload.get('text') or payload.get('content') or payload.get('answer')
                else:
                    candidate = payload
                answer_text = str(candidate).strip() if candidate is not None else ''
                if answer_text:
                    ref = None
                    if isinstance(payload, dict):
                        ref = {**payload}
                        ref['semantic_score'] = top_score
                    return {
                        'answer_text': answer_text,
                        'answer': answer_text,
                        'brain_used': 'Brain 1',
                        'provenance': 'SemanticSearchFallback',
                        'confidence': 'medium',
                        'source_refs': [ref] if ref else None
                    }

        # Chain of Command stage 3: Vertex AI Gemini (final fallback)
        try:  # pragma: no cover - external dependency
            if self.vertex_model is not None:
                # Minimal, safe prompt: ask Gemini to provide a concise, factual response.
                prompt = (
                    "You are SkyCap AI's external brain. Provide a concise, factual answer to the user's question. "
                    "If you are unsure, say you don't have enough information.\n\n"
                    f"Question: {question}"
                )
                result = self.vertex_model.generate_content(prompt)  # type: ignore[attr-defined]
                answer_text = None
                try:
                    # Prefer .text if present (newer SDK)
                    if hasattr(result, 'text') and result.text:
                        answer_text = str(result.text).strip()
                    # Fallback to candidates structure
                    elif hasattr(result, 'candidates') and result.candidates:
                        # Extract first non-empty text
                        for c in result.candidates:
                            try:
                                # newer SDK: c.content.parts[0].text
                                parts = getattr(getattr(c, 'content', None), 'parts', [])
                                for p in parts:
                                    t = getattr(p, 'text', None)
                                    if t:
                                        answer_text = str(t).strip()
                                        break
                                if answer_text:
                                    break
                            except Exception:
                                continue
                except Exception:
                    answer_text = None

                if answer_text:
                    return {
                        'answer_text': answer_text,
                        'answer': answer_text,
                        'brain_used': 'Brain 2/3',
                        'provenance': 'VertexAI',
                        'confidence': 'low',
                        'source_refs': None
                    }
                # If we didn't get text, try one fallback init and retry once
                if self._init_vertex_fallback():
                    try:
                        result2 = self.vertex_model.generate_content(prompt)  # type: ignore[attr-defined]
                        ans2 = None
                        if hasattr(result2, 'text') and result2.text:
                            ans2 = str(result2.text).strip()
                        elif hasattr(result2, 'candidates') and result2.candidates:
                            for c in result2.candidates:
                                parts = getattr(getattr(c, 'content', None), 'parts', [])
                                for p in parts:
                                    t = getattr(p, 'text', None)
                                    if t:
                                        ans2 = str(t).strip()
                                        break
                                if ans2:
                                    break
                        if ans2:
                            return {
                                'answer_text': ans2,
                                'answer': ans2,
                                'brain_used': 'Brain 2/3',
                                'provenance': 'VertexAI',
                                'confidence': 'low',
                                'source_refs': None
                            }
                    except Exception as e2:
                        logging.error(f"Vertex AI call (fallback) failed: {e2}")
        except Exception as e:
            # Detect model-not-found or bad location and attempt a one-time fallback
            emsg = str(e)
            if 'Publisher Model' in emsg or 'was not found' in emsg or '404' in emsg:
                if self._init_vertex_fallback():
                    try:
                        prompt = (
                            "You are SkyCap AI's external brain. Provide a concise, factual answer to the user's question. "
                            "If you are unsure, say you don't have enough information.\n\n"
                            f"Question: {question}"
                        )
                        result3 = self.vertex_model.generate_content(prompt)  # type: ignore[attr-defined]
                        ans3 = None
                        if hasattr(result3, 'text') and result3.text:
                            ans3 = str(result3.text).strip()
                        elif hasattr(result3, 'candidates') and result3.candidates:
                            for c in result3.candidates:
                                parts = getattr(getattr(c, 'content', None), 'parts', [])
                                for p in parts:
                                    t = getattr(p, 'text', None)
                                    if t:
                                        ans3 = str(t).strip()
                                        break
                                if ans3:
                                    break
                        if ans3:
                            return {
                                'answer_text': ans3,
                                'answer': ans3,
                                'brain_used': 'Brain 2/3',
                                'provenance': 'VertexAI',
                                'confidence': 'low',
                                'source_refs': None
                            }
                    except Exception as e3:
                        logging.error(f"Vertex AI call (post-fallback) failed: {e3}")
            logging.error(f"Vertex AI call failed: {e}")

        # Final message if all brains unavailable
        return {
            'answer_text': "I was unable to locate a definitive answer in my current knowledge base, and external research capabilities are currently unavailable. For best results, please try:\n• Rephrasing your question with specific dates or metrics\n• Asking about Jaiz Bank financials, NGX market data, or Skyview Capital services\n• Specifying the exact year or reporting period you're interested in",
            'answer': "I was unable to locate a definitive answer in my current knowledge base, and external research capabilities are currently unavailable. For best results, please try:\n• Rephrasing your question with specific dates or metrics\n• Asking about Jaiz Bank financials, NGX market data, or Skyview Capital services\n• Specifying the exact year or reporting period you're interested in",
            'brain_used': 'Hybrid Brain',
            'provenance': 'Default Fallback',
            'confidence': 'low',
            'source_refs': None
        }
