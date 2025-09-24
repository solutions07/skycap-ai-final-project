"""
SkyCap AI - Intelligent Agent (Fixed Version)

Clean, working version of the intelligent agent with proper knowledge base loading
and no Vertex AI errors.
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Set knowledge base path
KB_PATH = os.getenv('SKYCAP_KB_PATH', 'master_knowledge_base.json')

# Optional imports - handle gracefully if not available
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    _HAS_STS = True
except ImportError:
    SentenceTransformer = None
    np = None
    _HAS_STS = False

def _load_kb(path: str) -> Dict[str, Any]:
    """Load knowledge base with detailed diagnostics."""
    print(f"DEBUG: Attempting to load knowledge base from: {path}")
    print(f"DEBUG: Current working directory: {os.getcwd()}")
    print(f"DEBUG: File exists: {os.path.exists(path)}")
    
    if not os.path.exists(path):
        print(f"ERROR: Knowledge base file not found at {path}")
        print(f"DEBUG: Current directory contents: {os.listdir('.')}")
        return {}
    
    print(f"DEBUG: File size: {os.path.getsize(path)} bytes")
    
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            kb = json.load(fh)
            print(f"DEBUG: Successfully loaded knowledge base with {len(kb)} top-level keys")
            
            # Detailed diagnostics
            if 'financial_reports' in kb:
                print(f"DEBUG: Found {len(kb['financial_reports'])} financial reports")
            if 'market_data' in kb:
                print(f"DEBUG: Found {len(kb['market_data'])} market data entries")
            if 'client_profile' in kb:
                print(f"DEBUG: Found client profile section")
            if 'metadata' in kb:
                print(f"DEBUG: Found metadata section")
                
            return kb
    except Exception as e:
        print(f"ERROR: Failed to load knowledge base: {e}")
        return {}

def _iso_from_any(val: Optional[str]) -> Optional[str]:
    """Convert various date formats to ISO format."""
    if not val or not isinstance(val, str):
        return None
    try:
        return datetime.fromisoformat(val).date().isoformat()
    except Exception:
        pass
    
    # Try DD-MMM-YYYY format
    m = re.match(r"(\d{1,2})-([A-Za-z]{3,})-(\d{4})", val)
    if m:
        d, mon, y = m.groups()
        try:
            dt = datetime.strptime(f"{d} {mon} {y}", "%d %b %Y")
            return dt.date().isoformat()
        except Exception:
            pass
    
    # Try YYYY-MM-DD or YYYY/MM/DD format
    m = re.search(r"(\d{4})[\-/](\d{1,2})[\-/](\d{1,2})", val)
    if m:
        y, mm, dd = m.groups()
        try:
            return datetime(int(y), int(mm), int(dd)).date().isoformat()
        except Exception:
            pass
    
    return None

def _normalize_symbol(s: Optional[str]) -> str:
    """Normalize stock symbol."""
    if not s:
        return ''
    return re.sub(r"\s+", '', s).upper()

class MetadataEngine:
    """Engine for metadata queries."""
    
    def __init__(self, kb: Dict[str, Any]):
        self.kb = kb
        self.metadata = kb.get('metadata', {})
        self.data_sources = self.metadata.get('data_sources', []) if isinstance(self.metadata.get('data_sources'), list) else []

    def search(self, question: str) -> Optional[str]:
        ql = question.lower()
        
        # Count queries
        if 'how many' in ql and 'financial' in ql:
            count = len(self.kb.get('financial_reports', []))
            return f"There are {count} financial reports in the knowledge base."
        
        if 'how many' in ql and 'market' in ql:
            count = len(self.kb.get('market_data', []))
            return f"There are {count} market data records in the knowledge base."
        
        # Data sources
        if 'data source' in ql or 'sources' in ql:
            if self.data_sources:
                return 'Data sources: ' + ', '.join(self.data_sources)
        
        # List symbols
        if 'list' in ql and 'symbols' in ql:
            syms = set()
            for md in self.kb.get('market_data', []):
                sym = md.get('symbol') or md.get('ticker')
                if sym:
                    syms.add(str(sym).upper())
            if syms:
                return 'Symbols: ' + ', '.join(sorted(syms))
        
        return None

class PersonnelEngine:
    """Engine for personnel queries."""
    
    def __init__(self, kb: Dict[str, Any]):
        self.kb = kb
        self.profile = kb.get('client_profile', {})
        self.simple_index: Dict[str, str] = {}
        self._build_index()

    def _build_index(self):
        """Build searchable index from client profile."""
        pack = self.profile.get('skyview knowledge pack', {}) if isinstance(self.profile, dict) else {}
        
        # Team members
        team = pack.get('key team members at skyview capital limited (summary)', [])
        if isinstance(team, list):
            for s in team:
                if not isinstance(s, str):
                    continue
                name = s.split('—')[0].strip() if '—' in s else s.strip()
                key = re.sub(r'[^a-z]', '', name.lower())
                if key:
                    self.simple_index[key] = name
                
                # Add role-based lookups
                for title in ['managing director', 'chief financial officer', 'cfo']:
                    if title in s.lower():
                        self.simple_index[title] = name
        
        # Contact info
        contact = pack.get('contact information & locations for skyview capital limited', [])
        if isinstance(contact, list):
            for c in contact:
                if isinstance(c, str):
                    if 'phone' in c.lower() or '+' in c:
                        m = re.search(r"(\+?\d[\d\s\-]{6,})", c)
                        if m:
                            self.simple_index['phone'] = m.group(1).strip()
                    if '@' in c and 'email' in c.lower():
                        m = re.search(r"[\w\.-]+@[\w\.-]+", c)
                        if m:
                            self.simple_index['email'] = m.group(0).strip()
                    if 'address' in c.lower() or 'head office' in c.lower():
                        self.simple_index['address'] = c.strip()

    def search_personnel(self, question: str) -> Optional[str]:
        ql = question.lower()
        
        # Role-based searches
        if 'managing director' in ql or 'md ' in ql:
            return self.simple_index.get('managing director')
        
        if 'cfo' in ql or 'chief financial' in ql:
            return self.simple_index.get('chief financial officer') or self.simple_index.get('cfo')
        
        # Contact info
        if 'phone' in ql or 'contact number' in ql:
            return self.simple_index.get('phone')
        
        if 'email' in ql:
            return self.simple_index.get('email')
        
        if 'address' in ql or 'head office' in ql:
            return self.simple_index.get('address')
        
        # Name lookup
        for k, v in self.simple_index.items():
            if k in ql and len(k) > 3:
                return v
        
        return None

class FinancialDataEngine:
    """Engine for financial data queries."""
    
    def __init__(self, kb: Dict[str, Any]):
        self.kb = kb
        self.reports = kb.get('financial_reports', [])
        self.metrics: Dict[Tuple[str, str], Any] = {}
        self._build_index()

    def _norm_metric(self, s: str) -> str:
        """Normalize metric name."""
        return re.sub(r'[^a-z0-9]', '', s.lower())

    def _build_index(self):
        """Build searchable financial metrics index."""
        for r in self.reports:
            meta = r.get('report_metadata') if isinstance(r, dict) else None
            metrics = {}
            date_raw = None
            
            if isinstance(meta, dict):
                date_raw = meta.get('report_date') or meta.get('date')
                metrics = meta.get('metrics', {}) or {}
            else:
                date_raw = r.get('report_date') or r.get('date')
                metrics = r.get('metrics', {}) or {}
            
            iso = _iso_from_any(date_raw) or date_raw
            if not iso:
                continue
            
            if isinstance(metrics, dict):
                for k, v in metrics.items():
                    nk = self._norm_metric(str(k))
                    self.metrics[(nk, iso)] = v

    def search_financial_metric(self, question: str) -> Optional[str]:
        ql = question.lower()
        
        # Extract year
        year = None
        ym = re.search(r'(\d{4})', ql)
        if ym:
            year = ym.group(1)
        
        # Extract quarter
        qdate = None
        qm = re.search(r'q([1-4])\s*(\d{4})', ql)
        if qm:
            qn = int(qm.group(1))
            y = int(qm.group(2))
            month = [3, 6, 9, 12][qn - 1]
            qdate = f"{y}-{month:02d}-31"
        elif year:
            qdate = f"{year}-12-31"

        # Identify metric
        metric = None
        if 'total asset' in ql or 'totalassets' in ql:
            metric = 'totalassets'
        elif 'profit before tax' in ql or 'pbt' in ql:
            metric = 'profitbeforetax'
        elif 'earnings per share' in ql or 'eps' in ql:
            metric = 'earningspershare'
        elif 'revenue' in ql:
            metric = 'revenue'

        if not metric or not qdate:
            return None

        # Direct lookup
        if (metric, qdate) in self.metrics:
            value = self.metrics[(metric, qdate)]
            return f"The {metric.replace('totalassets', 'total assets').replace('profitbeforetax', 'profit before tax')} for {qdate} was {value}."
        
        # Try same year fallback
        try:
            ty = int(qdate[:4])
            candidates = [(d, v) for (m, d), v in self.metrics.items() if m == metric]
            same_year = [(d, self.metrics[(metric, d)]) for d in set(d for d, _ in candidates) if int(d[:4]) == ty]
            if same_year:
                same_year.sort(key=lambda x: x[0], reverse=True)
                d, v = same_year[0]
                return f"The {metric.replace('totalassets', 'total assets').replace('profitbeforetax', 'profit before tax')} for {d} was {v}."
        except Exception:
            pass
        
        return None

class MarketDataEngine:
    """Engine for market data queries."""
    
    def __init__(self, kb: Dict[str, Any]):
        self.kb = kb
        self.rows = kb.get('market_data', [])
        self.by_symbol: Dict[str, Dict[str, Any]] = {}
        self.by_date: Dict[str, List[Dict[str, Any]]] = {}
        self._build_index()

    def _build_index(self):
        """Build market data indices."""
        for r in self.rows:
            sym = _normalize_symbol(r.get('symbol') or r.get('ticker') or '')
            date_raw = r.get('date') or r.get('price_date') or r.get('pricedate')
            iso = _iso_from_any(date_raw) or date_raw
            
            if sym:
                self.by_symbol[sym] = r
            if iso:
                self.by_date.setdefault(iso, []).append(r)

    def search_stock_price(self, question: str) -> Optional[str]:
        ql = question.lower()
        
        # Extract symbol
        m = re.search(r'(?:for|of|symbol)\s+([A-Za-z0-9]+)', question)
        symbol = None
        if m:
            symbol = _normalize_symbol(m.group(1))
        else:
            # Try to find symbol in question
            for s in self.by_symbol.keys():
                if s.lower() in ql:
                    symbol = s
                    break
        
        if not symbol:
            return None
        
        # Extract date if specified
        date_iso = None
        ym = re.search(r'(\d{4}-\d{2}-\d{2})', question)
        if ym:
            date_iso = ym.group(1)
        dm = re.search(r'(\d{1,2}-[A-Za-z]{3}-\d{4})', question)
        if dm:
            date_iso = _iso_from_any(dm.group(1))

        # Find the data row
        row = self.by_symbol.get(symbol)
        if date_iso and date_iso in self.by_date:
            for r in self.by_date[date_iso]:
                if _normalize_symbol(r.get('symbol') or r.get('ticker')) == symbol:
                    row = r
                    break
        
        if not row:
            return None
        
        # Determine price field
        price_field = 'close'
        if 'open' in ql or 'opening' in ql:
            price_field = 'open'
        
        val = row.get(price_field) or row.get('last') or row.get('price')
        if val is None:
            return None
        
        dt_text = f" on {date_iso}" if date_iso else ''
        try:
            return f"The {price_field} price for {symbol}{dt_text} was ₦{float(val):,.2f}."
        except Exception:
            return f"The {price_field} price for {symbol}{dt_text} was {val}."

    def search_market_analysis(self, question: str) -> Optional[str]:
        """Placeholder for market analysis."""
        return None

class SemanticFallback:
    """Optional semantic search fallback."""
    
    def __init__(self, kb: Dict[str, Any], model_name: str = 'all-MiniLM-L6-v2'):
        self.kb = kb
        self.model = None
        self.texts: List[str] = []
        self.emb = None
        
        if _HAS_STS:
            try:
                self.model = SentenceTransformer(model_name)
                self._build_index()
            except Exception as e:
                print(f"DEBUG: Failed to initialize semantic model: {e}")
                self.model = None

    def _build_index(self):
        """Build semantic search index."""
        if not self.model:
            return
        
        # Add client profile
        cp = self.kb.get('client_profile', {})
        if cp:
            self.texts.append(json.dumps(cp))
        
        # Add financial reports (limited)
        for fr in self.kb.get('financial_reports', [])[:50]:
            self.texts.append(json.dumps(fr))
        
        # Add market data (limited)
        for md in self.kb.get('market_data', [])[:100]:
            self.texts.append(json.dumps(md))
        
        if self.texts:
            try:
                self.emb = np.asarray(self.model.encode(self.texts, convert_to_numpy=True))
                print(f"DEBUG: Built semantic index with {len(self.texts)} documents")
            except Exception as e:
                print(f"DEBUG: Failed to build semantic embeddings: {e}")
                self.emb = None

    def query(self, question: str) -> Optional[str]:
        """Query semantic index."""
        if not self.model or self.emb is None or not self.texts:
            return None
        
        try:
            v = np.asarray(self.model.encode([question], convert_to_numpy=True))[0]
            sims = (self.emb @ v) / (np.linalg.norm(self.emb, axis=1) * (np.linalg.norm(v) + 1e-12))
            idx = int(sims.argmax())
            
            if sims[idx] > 0.3:  # Threshold
                return f"(from semantic search) {self.texts[idx][:500]}"
        except Exception as e:
            print(f"DEBUG: Semantic query failed: {e}")
        
        return None

class IntelligentAgent:
    """Main intelligent agent class."""
    
    def __init__(self, kb_path: str = KB_PATH):
        print(f"DEBUG: Initializing IntelligentAgent with kb_path: {kb_path}")
        
        # Load knowledge base
        self.kb = _load_kb(kb_path)
        if not self.kb:
            print("ERROR: Empty knowledge base loaded - agent will not function properly")
        else:
            print(f"DEBUG: Knowledge base loaded successfully with keys: {list(self.kb.keys())}")
        
        # Initialize engines
        self.metadata = MetadataEngine(self.kb)
        self.personnel = PersonnelEngine(self.kb)
        self.financial = FinancialDataEngine(self.kb)
        self.market = MarketDataEngine(self.kb)
        
        # Optional semantic fallback
        self.semantic = None
        if _HAS_STS:
            try:
                self.semantic = SemanticFallback(self.kb)
            except Exception as e:
                print(f"DEBUG: Semantic fallback disabled: {e}")
        
        print("DEBUG: IntelligentAgent initialization complete")

    def ask(self, question: str) -> Dict[str, Any]:
        """Main query processing method."""
        start = datetime.utcnow()
        result = {
            'answer': '',
            'brain_used': 'Brain 1',
            'response_time': 0.0,
            'provenance': None
        }
        
        if not question or not question.strip():
            result['answer'] = 'Please ask a specific question.'
            result['response_time'] = (datetime.utcnow() - start).total_seconds()
            return result
        
        q = question.strip()
        print(f"DEBUG: Processing query: '{q}'")
        
        # Try each engine in sequence
        engines = [
            ('metadata', self.metadata.search),
            ('personnel', self.personnel.search_personnel),
            ('financial', self.financial.search_financial_metric),
            ('market_price', self.market.search_stock_price),
            ('market_analysis', self.market.search_market_analysis),
        ]
        
        for engine_name, engine_func in engines:
            try:
                answer = engine_func(q)
                if answer:
                    result['answer'] = answer
                    result['provenance'] = engine_name
                    result['response_time'] = (datetime.utcnow() - start).total_seconds()
                    print(f"DEBUG: Answer found by {engine_name}")
                    return result
            except Exception as e:
                print(f"DEBUG: Engine {engine_name} failed: {e}")
                continue
        
        # Try semantic fallback if available
        if self.semantic:
            try:
                semantic_answer = self.semantic.query(q)
                if semantic_answer:
                    result['answer'] = semantic_answer
                    result['brain_used'] = 'Brain 2'
                    result['provenance'] = 'semantic'
                    result['response_time'] = (datetime.utcnow() - start).total_seconds()
                    print("DEBUG: Answer found by semantic fallback")
                    return result
            except Exception as e:
                print(f"DEBUG: Semantic fallback failed: {e}")
        
        # Default response
        result['answer'] = "I don't have specific information about that query in my knowledge base."
        result['response_time'] = (datetime.utcnow() - start).total_seconds()
        print("DEBUG: No answer found - returning default response")
        return result

if __name__ == "__main__":
    print("Starting SkyCap AI Query Engine...")
    agent = IntelligentAgent()
    print("Agent initialized successfully!")
    
    # Test queries
    test_queries = [
        "How many financial reports are in the knowledge base?",
        "What were Jaiz Bank's total assets in Q1 2024?",
        "Who is the managing director of Skyview Capital?",
        "What is the contact phone number?"
    ]
    
    for query in test_queries:
        print(f"\nTesting: {query}")
        result = agent.ask(query)
        print(f"Answer: {result['answer']}")
        print(f"Brain: {result['brain_used']}, Time: {result['response_time']:.3f}s")