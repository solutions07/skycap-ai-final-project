#!/usr/bin/env python3
"""
Offline builder to generate semantic_index.(pkl|json) with embeddings and upload to GCS.

Usage examples:
  python3 tools/offline_build_and_upload_index.py \
    --kb data/master_knowledge_base.json \
    --out semantic_index.pkl \
    --format pkl \
    --model sentence-transformers/all-MiniLM-L6-v2 \
    --gcs gs://your-bucket/skycap/semantic_index.pkl

Notes:
- Requires sentence-transformers (and its deps) installed in this environment.
- Requires google-cloud-storage installed and GOOGLE_APPLICATION_CREDENTIALS or
  default application credentials available.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

# Reuse our existing builder for doc extraction + saving
import build_index as builder  # type: ignore

try:
    from google.cloud import storage  # type: ignore
except Exception:
    storage = None  # type: ignore


def _parse_args(argv):
    p = argparse.ArgumentParser(description="Build semantic index with embeddings and upload to GCS")
    p.add_argument("--kb", default="data/master_knowledge_base.json", help="Path to KB JSON file")
    p.add_argument("--out", default="semantic_index.pkl", help="Local output file path (.pkl or .json)")
    p.add_argument("--format", choices=["pkl", "json"], default="pkl", help="Output format")
    p.add_argument("--model", default="sentence-transformers/all-MiniLM-L6-v2", help="SentenceTransformer model name")
    p.add_argument("--batch-size", type=int, default=64, help="Embedding batch size")
    p.add_argument("--limit", type=int, default=0, help="Optional: limit number of documents")
    p.add_argument("--gcs", required=True, help="Destination GCS URI (gs://bucket/path/semantic_index.pkl)")
    return p.parse_args(argv)


def _parse_gcs_uri(uri: str):
    if not uri.startswith("gs://"):
        raise ValueError("GCS URI must start with gs://")
    rest = uri[len("gs://"):]
    parts = rest.split("/", 1)
    if len(parts) != 2:
        raise ValueError("Invalid GCS URI; expected gs://<bucket>/<object>")
    return parts[0], parts[1]


def upload_to_gcs(local_path: str, gcs_uri: str) -> None:
    if storage is None:
        raise RuntimeError("google-cloud-storage not installed in this environment")
    bucket, obj = _parse_gcs_uri(gcs_uri)
    logging.info("Uploading %s to gs://%s/%s", local_path, bucket, obj)
    client = storage.Client()
    b = client.bucket(bucket)
    blob = b.blob(obj)
    blob.upload_from_filename(local_path)
    logging.info("Upload complete: %s", gcs_uri)


def main(argv=None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    # Build documents
    try:
        import json
        with open(args.kb, "r", encoding="utf-8") as f:
            kb = json.load(f)
    except Exception as e:
        logging.error("Failed to load KB: %s", e)
        return 1

    docs = builder.build_documents(kb)
    if args.limit and args.limit > 0:
        docs = docs[: args.limit]
    logging.info("Prepared %d documents", len(docs))

    # Embed with strict requirement (we are in the offline env with deps)
    embeddings = builder.embed_documents([d["text"] for d in docs], args.model, args.batch_size)
    if embeddings is None:
        logging.error("Embeddings could not be generated in the offline environment; aborting.")
        return 1

    # Save locally
    try:
        builder.save_index(args.out, docs, embeddings, fmt=args.format, model_name=args.model)
    except Exception as e:
        logging.error("Failed to save local index: %s", e)
        return 1

    # Upload to GCS
    try:
        upload_to_gcs(args.out, args.gcs)
    except Exception as e:
        logging.error("Failed to upload to GCS: %s", e)
        return 1

    logging.info("All done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
