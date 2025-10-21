#!/usr/bin/env python3
"""Utility script for generating device-locked access tokens."""

import argparse
import json
import os
import secrets
import sys
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
TOKENS_FILE = APP_ROOT / "tokens.json"


def _load_tokens() -> dict:
    if not TOKENS_FILE.exists():
        return {}
    try:
        with TOKENS_FILE.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError as exc:
        print(f"[error] Failed to parse {TOKENS_FILE}: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # pragma: no cover - unexpected IO failure
        print(f"[error] Unable to read {TOKENS_FILE}: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"[error] Unexpected data format in {TOKENS_FILE}. Expected JSON object.", file=sys.stderr)
    sys.exit(1)


def _save_tokens(tokens: dict) -> None:
    try:
        with TOKENS_FILE.open("w", encoding="utf-8") as handle:
            json.dump(tokens, handle, indent=2, sort_keys=True)
    except Exception as exc:  # pragma: no cover - unexpected IO failure
        print(f"[error] Unable to write {TOKENS_FILE}: {exc}", file=sys.stderr)
        sys.exit(1)


def _generate_token() -> str:
    # 43-char URL-safe token (~256 bits entropy)
    return secrets.token_urlsafe(32)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a new device-locked access token.")
    parser.add_argument(
        "--minutes",
        type=int,
        default=60,
        help="Token lifespan in minutes (default: 60).",
    )
    args = parser.parse_args()

    if args.minutes <= 0:
        print("[error] Token lifespan must be a positive integer.", file=sys.stderr)
        sys.exit(1)

    expires_at = time.time() + (args.minutes * 60)
    token = _generate_token()

    tokens = _load_tokens()
    tokens[token] = {
        "expiration_timestamp": expires_at,
        "bound_ip_address": None,
        "bound_user_agent": None,
    }
    _save_tokens(tokens)

    local_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expires_at))
    print("=== SkyCap Access Token Generated ===")
    print(f"Token: {token}")
    print(f"Expires At (local time): {local_time}")
    print(f"Tokens file: {TOKENS_FILE}")


if __name__ == "__main__":
    main()
