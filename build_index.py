#!/usr/bin/env python3
"""
Build a semantic index from the local knowledge base (master_knowledge_base.json).

This script:
- Loads the KB JSON
- Extracts small, searchable facts from: financial_reports, market_data, and client_profile
- Generates sentence embeddings with sentence-transformers
- Saves embeddings + documents to a single file (pickle by default, optional JSON)

Usage (examples):
  python3 build_index.py --kb data/master_knowledge_base.json --out semantic_index.pkl
  python3 build_index.py --kb data/master_knowledge_base.json --out semantic_index.json --format json
  python3 build_index.py --model sentence-transformers/all-MiniLM-L6-v2 --batch-size 64

Notes:
- You need the sentence-transformers package installed:
    pip install sentence-transformers
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pickle
import re
import sys
from typing import Any, Dict, Iterable, List, Tuple

# Optional import guard for sentence-transformers. We capture any import-time
# exception (e.g., Torch/CUDA issues) and proceed with a graceful fallback.
SentenceTransformer = None  # type: ignore
_SENTENCE_TRANSFORMERS_IMPORT_ERROR: Exception | None = None
try:  # pragma: no cover - environment specific
    from sentence_transformers import SentenceTransformer as _ST  # type: ignore
    SentenceTransformer = _ST  # type: ignore
except Exception as e:  # pragma: no cover
    _SENTENCE_TRANSFORMERS_IMPORT_ERROR = e
    SentenceTransformer = None  # type: ignore


# ---------------------
# Helpers & Formatting
# ---------------------

def _format_currency_thousands(value: Any) -> str:
    """Format numeric value that is recorded 'in thousands' to human-friendly NGN string.
    Example: 580131058.0 -> ₦580.131 Billion
    """
    try:
        num = float(value) * 1_000.0
    except Exception:
        return str(value)
    if num >= 1_000_000_000_000:
        return f"₦{num / 1_000_000_000_000:.3f} Trillion"
    if num >= 1_000_000_000:
        return f"₦{num / 1_000_000_000:.3f} Billion"
    if num >= 1_000_000:
        return f"₦{num / 1_000_000:.3f} Million"
    return f"₦{num:,.2f}"


def _split_sentences(text: str) -> List[str]:
    """Simple sentence splitter without external dependencies."""
    if not text:
        return []
    # Split on ., ?, ! while preserving basic abbreviations
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p and not p.isspace()]


# ---------------------
# KB Fact Extraction
# ---------------------

def facts_from_financial_reports(reports: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for rep in reports or []:
        meta = rep.get("report_metadata", {})
        date = meta.get("report_date")
        metrics = meta.get("metrics", {})
        if not date or not isinstance(metrics, dict):
            continue
        for metric_name, raw_val in metrics.items():
            # EPS is not currency; keep raw representation
            is_eps = str(metric_name).strip().lower() == "earnings per share"
            value_txt = (f"{raw_val:g}" if isinstance(raw_val, (int, float)) else str(raw_val)) if is_eps else _format_currency_thousands(raw_val)
            text = f"As of {date}, the {metric_name} for Jaiz Bank was {value_txt}."
            yield {
                "text": text,
                "meta": {
                    "source": "financial_reports",
                    "date": date,
                    "metric": metric_name,
                },
            }


def facts_from_market_data(market_data: List[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
    for rec in market_data or []:
        date = rec.get("pricedate")
        symbol = rec.get("symbol")
        symbolname = rec.get("symbolname")
        closing = rec.get("closingprice")
        opening = rec.get("openingprice")
        if date and symbol and isinstance(closing, (int, float)):
            name_part = f" ({symbolname})" if symbolname else ""
            text1 = f"On {date}, {symbol}{name_part} closed at ₦{closing:,.2f}."
            yield {
                "text": text1,
                "meta": {
                    "source": "market_data",
                    "date": date,
                    "symbol": symbol,
                },
            }
        if date and symbol and isinstance(opening, (int, float)):
            name_part = f" ({symbolname})" if symbolname else ""
            text2 = f"On {date}, {symbol}{name_part} opened at ₦{opening:,.2f}."
            yield {
                "text": text2,
                "meta": {
                    "source": "market_data",
                    "date": date,
                    "symbol": symbol,
                },
            }


def _flatten(obj: Any) -> Iterable[str]:
    """Flatten nested client_profile values into lines of text."""
    if obj is None:
        return []
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, list):
        out: List[str] = []
        for item in obj:
            out.extend(_flatten(item))
        return out
    if isinstance(obj, dict):
        out: List[str] = []
        for k, v in obj.items():
            # Include keys as short headings when they look descriptive
            key_line = str(k).strip()
            if key_line and len(key_line) < 120 and not key_line.lower().startswith("_"):
                out.append(key_line)
            out.extend(_flatten(v))
        return out
    # Fallback to string
    return [str(obj)]


def facts_from_client_profile(profile: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    # The client_profile often has a 'skyview knowledge pack' dict of lists
    # We'll collect all strings and split into sentences
    for line in _flatten(profile):
        for sent in _split_sentences(line):
            if not sent:
                continue
            yield {
                "text": sent,
                "meta": {
                    "source": "client_profile",
                },
            }


# ---------------------
# Main build pipeline
# ---------------------

def build_documents(kb: Dict[str, Any]) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    try:
        docs.extend(list(facts_from_financial_reports(kb.get("financial_reports", []))))
    except Exception as e:
        logging.exception("Error extracting financial report facts: %s", e)
    try:
        docs.extend(list(facts_from_market_data(kb.get("market_data", []))))
    except Exception as e:
        logging.exception("Error extracting market data facts: %s", e)
    try:
        docs.extend(list(facts_from_client_profile(kb.get("client_profile", {}))))
    except Exception as e:
        logging.exception("Error extracting client profile facts: %s", e)
    # Deduplicate identical text entries while preserving order
    seen = set()
    unique_docs: List[Dict[str, Any]] = []
    for d in docs:
        t = d.get("text", "").strip()
        if not t or t in seen:
            continue
        seen.add(t)
        unique_docs.append(d)
    return unique_docs


def embed_documents(texts: List[str], model_name: str, batch_size: int = 64):
    """Return embeddings array or None when embeddings are unavailable.

    This function is resilient: if sentence-transformers cannot be imported or
    the model fails to load/encode (e.g., due to Torch/CUDA issues), we log a
    clear warning and return None so the caller can continue with a stub index.
    """
    if SentenceTransformer is None:
        msg = (
            "sentence-transformers unavailable. "
            f"Reason: {_SENTENCE_TRANSFORMERS_IMPORT_ERROR!r}"
        )
        logging.warning(msg)
        return None
    try:
        model = SentenceTransformer(model_name)
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings
    except Exception as e:
        logging.warning("Embedding generation failed (%s). Proceeding without embeddings.", e)
        return None


def save_index(out_path: str, docs: List[Dict[str, Any]], embeddings, fmt: str = "pkl", model_name: str = ""):
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    payload = {
        "model": model_name,
        "documents": docs,
        "embeddings": embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings,
    }
    if fmt.lower() == "json":
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    else:
        with open(out_path, "wb") as f:
            pickle.dump(payload, f)


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build semantic index from KB JSON")
    p.add_argument("--kb", default="data/master_knowledge_base.json", help="Path to KB JSON file")
    p.add_argument("--out", default="semantic_index.pkl", help="Output file path (.pkl or .json)")
    p.add_argument("--format", choices=["pkl", "json"], default="pkl", help="Output format")
    p.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2", help="SentenceTransformer model name")
    p.add_argument("--batch-size", type=int, default=64, help="Embedding batch size")
    p.add_argument("--limit", type=int, default=0, help="Optional: limit number of documents (debug)")
    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    # Load KB
    try:
        with open(args.kb, "r", encoding="utf-8") as f:
            kb = json.load(f)
    except FileNotFoundError:
        logging.error("KB file not found: %s", args.kb)
        return 1
    except json.JSONDecodeError as e:
        logging.error("Failed to parse KB JSON: %s", e)
        return 1

    # Build docs
    docs = build_documents(kb)
    if args.limit and args.limit > 0:
        docs = docs[: args.limit]
    logging.info("Prepared %d documents for embedding", len(docs))

    # Embed (resilient): if unavailable, proceed with stub index
    texts = [d["text"] for d in docs]
    embeddings = embed_documents(texts, args.model, args.batch_size)
    if embeddings is None:
        logging.warning(
            "Embeddings unavailable. Saving stub index without embeddings. Semantic search will be disabled."
        )

    # Save
    try:
        save_index(args.out, docs, embeddings, fmt=args.format, model_name=args.model)
    except Exception as e:
        logging.error("Saving index failed: %s", e)
        return 1

    logging.info("Semantic index saved: %s", args.out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
