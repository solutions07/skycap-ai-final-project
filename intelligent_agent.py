
import json
import re
import logging
from datetime import datetime
from typing import Optional


# --- Helper Functions ---

def _format_large_number(value):
    """Format large numbers with Nigerian Naira currency and appropriate units.

    NOTE (V1.2): Source metrics are expressed in thousands; convert to full value before formatting.
    Example: 580131058.0 (thousands) -> ₦580.131 Billion
    """
    if not isinstance(value, (int, float)):
        return str(value)
    try:
        scaled = float(value) * 1_000.0  # convert 'in thousands' to actual ₦
    except Exception:
        scaled = 0.0
    if scaled >= 1_000_000_000_000:
        return f"₦{scaled / 1_000_000_000_000:.3f} Trillion"
    if scaled >= 1_000_000_000:
        return f"₦{scaled / 1_000_000_000:.3f} Billion"
    if scaled >= 1_000_000:
        return f"₦{scaled / 1_000_000:.3f} Million"
    return f"₦{scaled:,.2f}"

def _format_metric_value(metric_name: str, value):
    """Format metric values smartly based on their type.

    - Currency-like metrics (assets, PBT, gross earnings) are in thousands and use _format_large_number.
    - Earnings per share (EPS) is a plain number; no currency symbol or thousands scaling.
    """
    if metric_name and isinstance(metric_name, str) and metric_name.strip().lower() in {
        'total assets', 'profit before tax', 'gross earnings'
    }:
        return _format_large_number(value)
    # EPS and others: return as-is, formatted to sensible precision
    try:
        if isinstance(value, (int, float)):
            # show up to 4 decimals for small EPS
            return f"{float(value):g}"
    except Exception:
        pass
    return str(value)

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
        self._build_index()

    def _build_index(self):
        """Build an index of financial metrics for efficient searching."""
        for report in self.reports:
            meta = report.get('report_metadata', {})
            date = meta.get('report_date')
            metrics = meta.get('metrics', {})
            if date and metrics:
                for key, value in metrics.items():
                    norm_key = re.sub(r'[^a-z0-9]', '', key.lower())
                    try:
                        self.metrics[(norm_key, date)] = float(value)
                    except (ValueError, TypeError): 
                        continue

    def search_financial_metric(self, question):
        """Search for financial metrics based on the question."""
        q_lower = question.lower()
        norm_q = re.sub(r'[^a-z0-9]', '', q_lower)
        
        # Define metric patterns and their normalized keys
        # Use constants for metric names
        # Define metric patterns with improved specificity and priority order
        # 1) EPS first to avoid collision with 'gross earnings'
        # 2) Gross Earnings requires explicit phrasing or synonyms like 'revenue'
        # 3) Total Assets and PBT are specific, avoid overly-generic tokens
        metric_patterns = {
            self.METRIC_EARNINGS_PER_SHARE: ['earningspershare', 'eps'],
            self.METRIC_GROSS_EARNINGS: ['grossearnings', 'revenue', 'grossincome'],
            self.METRIC_TOTAL_ASSETS: ['totalassets'],
            self.METRIC_PROFIT_BEFORE_TAX: ['profitbeforetax', 'pbt']
        }
        
        # Extract year/date from question
        year_match = re.search(r'(20\d{2})', question)
        quarter_match = re.search(r'q([1-4])', q_lower)
        
        # Search for matching metrics
        for metric_display_name, patterns in metric_patterns.items():
            for pattern in patterns:
                if pattern not in re.sub(r'[^a-z0-9]', '', q_lower):
                    continue

                # --- Enhanced Logic for Comparative Queries ---
                comparison_keywords = ['compare', 'vs', 'versus', 'between']
                # Recognize conversational phrasing like: "how did X change from 2021 to 2022"
                change_from_to = bool(re.search(r'change\s+from\s+20\d{2}\s+to\s+20\d{2}', q_lower))
                from_to_years = bool(re.search(r'from\s+20\d{2}.*to\s+20\d{2}', q_lower))
                is_comparison = any(keyword in q_lower for keyword in comparison_keywords) or change_from_to or from_to_years
                
                if is_comparison:
                    # --- START: Comparative Analysis Module (Hardened) ---
                    try:
                        # Extract at least two distinct years for a valid comparison
                        all_year_matches = re.findall(r'(20\d{2})', question)
                        unique_years = sorted({int(y) for y in all_year_matches})
                        if len(unique_years) < 2:
                            continue  # Not a valid comparison; fall back to single-metric handling

                        results = []
                        norm_metric_key = re.sub(r'[^a-z0-9]', '', metric_display_name.lower())

                        # For each requested year, attempt to find a matching metric
                        for y in unique_years:
                            try:
                                match = self._find_best_date_match(norm_metric_key, str(y), None)
                                if match and isinstance(match[0], (int, float)):
                                    results.append({'value': float(match[0]), 'date': match[1], 'year': int(y)})
                                else:
                                    results.append({'value': None, 'date': None, 'year': int(y)})
                            except Exception as e:
                                logging.error(f"Error locating data for year {y}: {e}")
                                results.append({'value': None, 'date': None, 'year': int(y)})

                        # Discard years with no available value
                        valid_results = [r for r in results if isinstance(r.get('value'), (int, float))]
                        if len(valid_results) < 2:
                            return "Insufficient data found for a comparative trend between the requested years."

                        # Sort chronologically and compute change
                        valid_results.sort(key=lambda x: x.get('year', 0))
                        old, new = valid_results[0], valid_results[-1]

                        old_val = float(old.get('value', 0))
                        new_val = float(new.get('value', 0))
                        old_date = old.get('date') or 'N/A'
                        new_date = new.get('date') or 'N/A'

                        delta = new_val - old_val
                        if old_val != 0:
                            try:
                                pct_change = (delta / abs(old_val)) * 100.0
                            except Exception:
                                pct_change = 0.0
                            change_str = "an increase" if delta > 0 else ("a decrease" if delta < 0 else "no change")
                            return (
                                f"Comparing {metric_display_name} between {old['year']} and {new['year']}: "
                                f"The value changed from {_format_metric_value(metric_display_name, old_val)} (as of {old_date}) "
                                f"to {_format_metric_value(metric_display_name, new_val)} (as of {new_date}). "
                                f"This represents {change_str} of {_format_metric_value(metric_display_name, abs(delta))} ({pct_change:+.2f}%)."
                            )
                        else:
                            return (
                                f"Comparing {metric_display_name} from {old['year']} to {new['year']}: "
                                f"The value went from ₦0 (as of {old_date}) to {_format_metric_value(metric_display_name, new_val)} (as of {new_date})."
                            )
                    except Exception as e:
                        logging.error(f"Unhandled error in comparative analysis: {e}", exc_info=True)
                        return "Unable to complete the comparison due to inconsistent data. Please refine the years or metric and try again."
                    # --- END: Comparative Analysis Module (Hardened) ---

                # --- Original Logic for Single Metric Queries ---
                norm_metric_key_for_index = re.sub(r'[^a-z0-9]', '', metric_display_name.lower())
                best_match = self._find_best_date_match(norm_metric_key_for_index, year_match, quarter_match)
                if best_match:
                    metric_value, date = best_match
                    formatted_value = _format_metric_value(metric_display_name, metric_value)
                    return f"The {metric_display_name} for Jaiz Bank as of {date} was {formatted_value}."
        
        return None

    def _find_best_date_match(self, metric_key, year_match, quarter_match):
        """Find the best matching date for a given metric.

        Accepts a year as a regex match object OR a plain string (e.g., '2023').
        Quarter can be a match object or a string like 'Q1'/'1'.
        Returns (value, date) tuple or None.
        """
        candidates = []

        for (key, date), value in self.metrics.items():
            if key == metric_key:
                candidates.append((value, date))

        if not candidates:
            return None

        # Sort by date (most recent first)
        try:
            candidates.sort(key=lambda x: x[1] or '', reverse=True)
        except Exception:
            # If any date is malformed, fall back to simple sort without reverse to avoid crash
            candidates.sort(key=lambda x: str(x[1]))

        # Helper to extract a 4-digit year
        def _extract_year(y):
            if not y:
                return None
            try:
                if isinstance(y, str):
                    m = re.search(r'(19|20)\d{2}', y)
                    return m.group(0) if m else None
                if hasattr(y, 'group'):
                    try:
                        gy = y.group(1)
                    except IndexError:
                        gy = y.group(0)
                    m = re.search(r'(19|20)\d{2}', gy)
                    return m.group(0) if m else None
            except Exception:
                return None
            return None

        target_year = _extract_year(year_match)

        # If specific year/quarter requested, try to match
        if target_year:
            year_candidates = []
            # Strict filtering for the requested year
            for value, date in candidates:
                try:
                    if isinstance(date, str) and date.startswith(target_year):
                        year_candidates.append((value, date))
                except Exception:
                    continue

            if not year_candidates:
                return None  # No data for the requested year

            # Extract quarter safely if provided
            q_val = None
            if quarter_match:
                try:
                    if isinstance(quarter_match, str):
                        m = re.search(r'([1-4])', quarter_match)
                        q_val = m.group(1) if m else None
                    elif hasattr(quarter_match, 'group'):
                        try:
                            q_val = quarter_match.group(1)
                        except IndexError:
                            q_val = None
                except Exception:
                    q_val = None

            if q_val:
                quarter_months = {'1': '03', '2': '06', '3': '09', '4': '12'}
                target_month = quarter_months.get(q_val)
                if target_month:
                    for value, date in year_candidates:
                        try:
                            if f"-{target_month}-" in (date or ''):
                                return (value, date)
                        except Exception:
                            continue

            # If no quarter match or no quarter requested, return the latest entry for that year
            return year_candidates[0] if year_candidates else None

        # If no year is specified, do not guess. Return the latest available record.
        return candidates[0] if candidates else None


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
            # Check if a name or role from the KB is in the question
            # Example: "Olufemi Adesiyan (Managing Director): ..."
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

    def search_market_info(self, question):
        """Search for stock prices and symbols."""
        q_lower = question.lower()

        # 1. Search for price by symbol
        # Stricter regex: require uppercase and word boundaries to avoid matching common words.
        symbol_match = re.search(r'\b([A-Z]{3,10})\b', question)
        if symbol_match:
            symbol = symbol_match.group(1)
            date_match = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(20\d{2})', q_lower)
            
            if date_match:
                # Find price for a specific date
                day, month_name, year = date_match.groups()
                month = datetime.strptime(month_name, '%B').month
                target_date_str = f"{year}-{int(month):02d}-{int(day):02d}"

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
        """Search for keywords in the company overview and services sections."""
        ql = question.lower()
        if 'philosophy' in ql or 'mission' in ql:
            return self.profile_data.get('company overview', [None])[2]  # Return the mission statement
        if 'services' in ql:
            # --- START: Professional Synthesis Module ---
            services_list = self.profile_data.get('services offered by skyview capital limited', [])
            if not services_list: return None
            synthesis = ("Skyview Capital Limited provides a comprehensive suite of financial services tailored for a diverse clientele, including government parastatals, multinational corporations, and high-net-worth individuals. "
                         "Core offerings are supported by a team of seasoned professional researchers who deliver in-depth stock analysis and daily securities updates. "
                         "Key services include retainer-ships for listed companies, acting as a Receiving Agency for IPOs and Public Offerings, and utilizing advanced tools for asset valuation.")
            return synthesis
            # --- END: Professional Synthesis Module ---
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
        phone_keywords = ['phone', 'telephone', 'phone number', 'contact number', 'mobile', 'tel']
        if any(k in q_lower for k in phone_keywords):
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
        if 'who are you' in q_lower or 'what are you' in q_lower or 'your purpose' in q_lower:
            return "I am SkyCap AI, an intelligent financial assistant. I was developed by AMD ASCEND Solutions to provide high-speed financial and market analysis for Skyview Capital Limited."
        if 'testimonial' in q_lower:
            return "I have access to testimonials from clients like Emmanuel Oladimeji of Xayeed Group, Mojisola George of The Daily World Finance, and Adebimpe Ayoade of Financial Report Limited."
        if 'skycap ai project' in q_lower:
            return "The SkyCap AI project is designed to enhance client advisory services by providing faster insights and real-time trend predictions for NGX-listed stocks."
        if 'emmanuel oladimeji' in q_lower:
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


class IntelligentAgent:
    """Brain 1 Only - Simplified Intelligent Agent for local knowledge base queries."""

    def __init__(self, kb_path):
        self.kb = _load_kb(kb_path)
        if not self.kb:
            raise ValueError("Knowledge base failed to load.")

        # --- START: FIX 3 (Disable External Brains) ---
        # External brain model is explicitly disabled.
        self.vertex_model = None
        # --- END: FIX 3 (Disable External Brains) ---

        # Initialize Brain 1 engines
        self.financial_engine = FinancialDataEngine(self.kb)
        self.personnel_engine = PersonnelDataEngine(self.kb)
        self.market_engine = MarketDataEngine(self.kb)
        self.metadata_engine = MetadataEngine(self.kb)
        self.profile_engine = CompanyProfileEngine(self.kb)
        self.location_engine = LocationDataEngine(self.kb)
        self.general_engine = GeneralKnowledgeEngine(self.kb)
        # Semantic searcher (lazy init on first use)
        self._semantic_searcher: Optional[object] = None

    def ask(self, question):
        """
        Brain 1 Only - Query local knowledge base engines.
        Returns structured response with answer, brain used, and data provenance.
        """
        if not question or not question.strip():
            return {
                'answer': "Please provide a specific question.",
                'brain_used': 'Brain 1',
                'provenance': 'Input Validation'
            }
        
        # Try financial data engine first (most common queries)
        financial_answer = self.financial_engine.search_financial_metric(question)
        if financial_answer:
            return {
                'answer': financial_answer,
                'brain_used': 'Brain 1',
                'provenance': 'FinancialDataEngine'
            }
        
        # Try metadata engine for document/report queries
        metadata_answer = self.metadata_engine.search_metadata(question)
        if metadata_answer:
            return {
                'answer': metadata_answer,
                'brain_used': 'Brain 1',
                'provenance': 'MetadataEngine'
            }
        
        # Try personnel engine for organizational queries
        personnel_answer = self.personnel_engine.search_personnel_info(question)
        if personnel_answer:
            return {
                'answer': personnel_answer,
                'brain_used': 'Brain 1',
                'provenance': 'PersonnelDataEngine'
            }
        
        # Try market data engine for industry/market queries
        market_answer = self.market_engine.search_market_info(question)
        if market_answer:
            return {
                'answer': market_answer,
                'brain_used': 'Brain 1',
                'provenance': 'MarketDataEngine'
            }
        
        # Try company profile engine
        profile_answer = self.profile_engine.search_profile_info(question)
        if profile_answer:
            return {
                'answer': profile_answer,
                'brain_used': 'Brain 1',
                'provenance': 'CompanyProfileEngine'
            }

        # Try location engine
        location_answer = self.location_engine.search_location_info(question)
        if location_answer:
            return {
                'answer': location_answer,
                'brain_used': 'Brain 1',
                'provenance': 'LocationDataEngine'
            }

        # Try general knowledge engine
        general_answer = self.general_engine.search_general_info(question)
        if general_answer:
            return {
                'answer': general_answer,
                'brain_used': 'Brain 1',
                'provenance': 'GeneralKnowledgeEngine'
            }
        
        # Professional default response when no data is found
        # Try semantic search as final fallback
        try:
            if SemanticSearcher is not None:
                if self._semantic_searcher is None:
                    self._semantic_searcher = SemanticSearcher()
                searcher = self._semantic_searcher
                if hasattr(searcher, 'available') and searcher.available():  # type: ignore[attr-defined]
                    results = searcher.search(question, k=1)  # type: ignore[attr-defined]
                    if results:
                        top_score, top_doc = results[0]
                        answer_text = top_doc.get('text') if isinstance(top_doc, dict) else str(top_doc)
                        return {
                            'answer': answer_text,
                            'brain_used': 'Brain 1',
                            'provenance': 'SemanticSearchFallback'
                        }
        except Exception as e:
            logging.error(f"Semantic fallback failed: {e}")

        # Final message if semantic search also unavailable
        return {
            'answer': "I don't have specific information about that query in my knowledge base. Please try rephrasing or asking about financial data, stock prices, or company information.",
            'brain_used': 'Brain 1',
            'provenance': 'Default Fallback'
        }