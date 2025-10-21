import json
import os
import threading
import time
from typing import Optional
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import logging
from intelligent_agent import IntelligentAgent

# Optional: GCS client for downloading precomputed semantic index
try:  # pragma: no cover - env dependent
    from google.cloud import storage  # type: ignore
except Exception:  # pragma: no cover
    storage = None  # type: ignore

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

app = Flask(__name__)
env_secret = os.environ.get('FLASK_SECRET_KEY')
if not env_secret:
    raise RuntimeError("FLASK_SECRET_KEY environment variable must be set for session security.")
app.config['SECRET_KEY'] = env_secret
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True

# Unified CORS configuration: apply to all routes for GitHub Pages frontend
CORS(app, resources={r"/*": {"origins": "https://solutions07.github.io"}}, supports_credentials=True)
# CORS: allow GitHub Pages origin across all routes, including preflight
ALLOWED_ORIGIN = "https://solutions07.github.io"

# Define a robust path to the knowledge base file
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_BASE_PATH = os.path.join(APP_ROOT, 'data', 'master_knowledge_base.json')
TOKENS_FILE_PATH = os.path.join(APP_ROOT, 'tokens.json')

_TOKEN_STORE = {}
_TOKEN_LOCK = threading.Lock()
_TOKENS_MTIME = None


def _compute_expiration(record: dict) -> Optional[float]:
    try:
        duration = float(record.get('duration_minutes'))
        first_used = float(record.get('first_used_timestamp'))
    except (TypeError, ValueError):
        return None
    if duration <= 0:
        return None
    return first_used + (duration * 60.0)


def _refresh_token_store(force: bool = False):
    """Refresh the in-memory token cache from disk when the file changes."""
    global _TOKENS_MTIME
    try:
        mtime = os.path.getmtime(TOKENS_FILE_PATH)
    except FileNotFoundError:
        return
    if not force and _TOKENS_MTIME is not None and mtime <= _TOKENS_MTIME:
        return
    try:
        with open(TOKENS_FILE_PATH, 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            logging.warning("Token file malformed; expected object at root")
            return
        with _TOKEN_LOCK:
            fresh_tokens = set()
            for token, meta in data.items():
                if not isinstance(meta, dict):
                    continue
                fresh_tokens.add(token)
                try:
                    duration_val = float(meta.get('duration_minutes'))
                except (TypeError, ValueError):
                    duration_val = None
                try:
                    first_used_val = float(meta.get('first_used_timestamp')) if meta.get('first_used_timestamp') is not None else None
                except (TypeError, ValueError):
                    first_used_val = None
                record = {
                    'duration_minutes': duration_val,
                    'first_used_timestamp': first_used_val,
                    'bound_ip_address': meta.get('bound_ip_address'),
                    'bound_user_agent': meta.get('bound_user_agent'),
                }
                _TOKEN_STORE[token] = record
            stale_tokens = set(_TOKEN_STORE.keys()) - fresh_tokens
            for stale in stale_tokens:
                _TOKEN_STORE.pop(stale, None)
        _TOKENS_MTIME = mtime
    except Exception as exc:
        logging.warning("Failed to refresh tokens: %s", exc)


def _persist_token(token: str):
    """Persist the current token cache state back to disk."""
    try:
        with _TOKEN_LOCK:
            try:
                with open(TOKENS_FILE_PATH, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                if not isinstance(data, dict):
                    data = {}
            except FileNotFoundError:
                data = {}
            record = _TOKEN_STORE.get(token)
            if record:
                data[token] = {
                    'duration_minutes': record.get('duration_minutes'),
                    'first_used_timestamp': record.get('first_used_timestamp'),
                    'bound_ip_address': record.get('bound_ip_address'),
                    'bound_user_agent': record.get('bound_user_agent'),
                }
            else:
                data.pop(token, None)
            with open(TOKENS_FILE_PATH, 'w', encoding='utf-8') as fh:
                json.dump(data, fh, indent=2, sort_keys=True)
            global _TOKENS_MTIME
            _TOKENS_MTIME = os.path.getmtime(TOKENS_FILE_PATH)
    except Exception as exc:
        logging.warning("Failed to persist token state: %s", exc)


def _get_request_fingerprint():
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    if forwarded_for:
        ip_address = forwarded_for.split(',')[0].strip()
    else:
        ip_address = request.remote_addr or 'unknown'
    user_agent = request.headers.get('User-Agent', 'unknown')
    return ip_address, user_agent


@app.before_request
def handle_cors_preflight():
    # Globally handle CORS preflight to avoid route/method edge cases
    if request.method == 'OPTIONS':
        resp = app.make_response("")
        resp.status_code = 204
        origin = request.headers.get('Origin', '')
        if origin and origin.startswith(ALLOWED_ORIGIN):
            req_headers = request.headers.get('Access-Control-Request-Headers', '')
            resp.headers['Access-Control-Allow-Origin'] = origin
            resp.headers['Vary'] = 'Origin'
            resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = req_headers or 'Content-Type, Authorization'
            resp.headers['Access-Control-Allow-Credentials'] = 'true'
            resp.headers['Access-Control-Max-Age'] = '3600'
        return resp

def _parse_gcs_uri(uri: str):
    if not uri.startswith("gs://"):
        raise ValueError("GCS URI must start with gs://")
    without_scheme = uri[len("gs://"):]
    parts = without_scheme.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("Invalid GCS URI; expected gs://<bucket>/<object>")
    return parts[0], parts[1]

def maybe_download_semantic_index():
    """If SEMANTIC_INDEX_GCS_URI is set, download the index file to app root.

    - Supports .pkl and .json indices.
    - Saves to semantic_index.pkl or semantic_index.json in APP_ROOT, matching the source extension.
    - If download fails, logs a warning and continues (stub fallback remains available).
    """
    uri = os.environ.get("SEMANTIC_INDEX_GCS_URI", "").strip()
    if not uri:
        logging.info("No SEMANTIC_INDEX_GCS_URI set; skipping semantic index download.")
        return None
    ext = ".pkl" if uri.endswith(".pkl") else ".json"
    local_override = os.environ.get("SEMANTIC_INDEX_LOCAL_PATH", "").strip()
    dest_name = os.path.basename(local_override) if local_override else f"semantic_index{ext}"
    dest_path = os.path.join(APP_ROOT, dest_name)

    if os.path.exists(dest_path):
        logging.info("Semantic index already present at %s; skipping download.", dest_path)
        return dest_path

    if storage is None:
        logging.warning("google-cloud-storage not available; cannot download semantic index from GCS.")
        return None
    try:
        bucket_name, object_name = _parse_gcs_uri(uri)
        logging.info("Downloading semantic index from gs://%s/%s to %s", bucket_name, object_name, dest_path)
        client = storage.Client()  # uses default credentials in Cloud Run
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        os.makedirs(os.path.dirname(dest_path) or APP_ROOT, exist_ok=True)
        blob.download_to_filename(dest_path)
        logging.info("Semantic index downloaded to %s", dest_path)
        return dest_path
    except Exception as e:  # pragma: no cover - network/perm dependent
        logging.warning("Failed to download semantic index from GCS (%s). Proceeding without.", e)
        return None

agent = None
try:
    logging.info(f"Attempting to load knowledge base from: {KNOWLEDGE_BASE_PATH}")
    # Optionally download precomputed semantic index from GCS (Option B)
    maybe_download_semantic_index()
    # If a semantic index exists but lacks embeddings, compute them now (one-time repair).
    # Disabled by default in Cloud Run to ensure fast, reliable startup. Enable by setting
    # ENABLE_SEMANTIC_REPAIR=1 if you explicitly want this at runtime.
    if os.environ.get("ENABLE_SEMANTIC_REPAIR", "0") == "1":
        try:
            from search_index import SemanticSearcher  # local import
            import json as _json  # avoid clobber
            import pickle as _pickle
            searcher = SemanticSearcher()
            if searcher.documents and searcher.embeddings is None and searcher.model is not None:
                logging.info("Semantic index found without embeddings; computing embeddings now (one-time repair)...")
                texts = [d.get("text", "") for d in searcher.documents]
                vecs = searcher.model.encode(
                    texts,
                    batch_size=64,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                    normalize_embeddings=True,
                )
                payload = {
                    "model": searcher.model_name,
                    "documents": searcher.documents,
                    "embeddings": vecs.tolist(),
                }
                idx_path = os.path.join("/tmp", "semantic_index.pkl")
                try:
                    if str(idx_path).endswith(".json"):
                        with open(idx_path, "w", encoding="utf-8") as f:
                            _json.dump(payload, f, ensure_ascii=False)
                    else:
                        with open(idx_path, "wb") as f:
                            _pickle.dump(payload, f)
                    logging.info("Semantic index repaired successfully at %s", idx_path)
                except Exception as _e:
                    logging.warning("Failed to save repaired semantic index (%s). Continuing without persisting.", _e)
                # Even if saving failed, keep an in-memory embeddings for this process
                try:
                    searcher.embeddings = vecs  # type: ignore[attr-defined]
                except Exception:
                    pass
        except Exception as _e:  # pragma: no cover - best-effort repair
            logging.warning("Semantic index repair skipped (%s)", _e)
    agent = IntelligentAgent(kb_path=KNOWLEDGE_BASE_PATH) 
    logging.info("=== SkyCap AI Server Initialization Successful ===")
    _refresh_token_store(force=True)
except Exception as e:
    logging.error("=== CRITICAL: SkyCap AI Server Initialization FAILED ===", exc_info=True)

@app.route('/')
def health_check():
    if agent:
        return jsonify({"status": "ok", "message": "SkyCap AI Backend is running."}), 200
    else:
        return jsonify({"status": "error", "message": "Backend initialization failed."}), 503

@app.route('/status')
def status():
    """Detailed status, including semantic search availability."""
    try:
        sem = {
            "available": False,
            "has_documents": False,
            "has_embeddings": False,
            "model_loaded": False,
        }
        if agent is not None:
            # Initialize searcher lazily if not yet created
            if getattr(agent, "_semantic_searcher", None) is None and hasattr(agent, "SemanticSearcher"):
                pass  # Defensive; actual init occurs in IntelligentAgent.ask
            # Access internal searcher if exists or create one ad-hoc for status
            try:
                from search_index import SemanticSearcher  # local import
                searcher = getattr(agent, "_semantic_searcher", None) or SemanticSearcher()
                sem["has_documents"] = bool(getattr(searcher, "documents", []))
                embs = getattr(searcher, "embeddings", None)
                sem["has_embeddings"] = embs is not None
                sem["model_loaded"] = getattr(searcher, "model", None) is not None
                if hasattr(searcher, 'available'):
                    sem["available"] = bool(searcher.available())  # type: ignore

                # On-demand repair: if docs exist, model is loaded, but embeddings are missing, compute now
                if sem["has_documents"] and not sem["has_embeddings"] and sem["model_loaded"]:
                    try:
                        import json as _json
                        import pickle as _pickle
                        texts = [d.get("text", "") for d in searcher.documents]
                        vecs = searcher.model.encode(
                            texts,
                            batch_size=64,
                            show_progress_bar=False,
                            convert_to_numpy=True,
                            normalize_embeddings=True,
                        )
                        payload = {
                            "model": searcher.model_name,
                            "documents": searcher.documents,
                            "embeddings": vecs.tolist(),
                        }
                        idx_path = os.path.join("/tmp", "semantic_index.pkl")
                        if str(idx_path).endswith(".json"):
                            with open(idx_path, "w", encoding="utf-8") as f:
                                _json.dump(payload, f, ensure_ascii=False)
                        else:
                            with open(idx_path, "wb") as f:
                                _pickle.dump(payload, f)
                        # Reload to update status from persisted /tmp index
                        searcher = SemanticSearcher()
                        sem["has_documents"] = bool(getattr(searcher, "documents", []))
                        sem["has_embeddings"] = getattr(searcher, "embeddings", None) is not None
                        sem["model_loaded"] = getattr(searcher, "model", None) is not None
                        sem["available"] = bool(searcher.available())
                    except Exception as _e:  # pragma: no cover
                        logging.warning("On-demand semantic index repair failed: %s", _e)
                        # Optimistically set availability for this response if we computed vecs
                        try:
                            if 'vecs' in locals():
                                sem["has_embeddings"] = True
                                sem["available"] = True
                        except Exception:
                            pass
            except Exception:
                pass
        return jsonify({
            "status": "ok" if agent else "error",
            "semantic": sem,
        }), 200 if agent else 503
    except Exception:
        return jsonify({"status": "error"}), 500

@app.route('/verify-token', methods=['POST', 'OPTIONS'])
def verify_token():
    if request.method == 'OPTIONS':
        return ('', 204)

    _refresh_token_store()
    payload = request.get_json(silent=True) or {}
    token = str(payload.get('token', '')).strip()
    if not token:
        return jsonify({'status': 'error', 'message': 'Token missing.'}), 400

    with _TOKEN_LOCK:
        token_record = _TOKEN_STORE.get(token)

    if not token_record:
        return jsonify({'status': 'error', 'message': 'Invalid or expired token.'}), 401

    duration = token_record.get('duration_minutes')
    if not isinstance(duration, (int, float)) or float(duration) <= 0:
        with _TOKEN_LOCK:
            _TOKEN_STORE.pop(token, None)
        _persist_token(token)
        return jsonify({'status': 'error', 'message': 'Token invalid.'}), 401

    ip_address, user_agent = _get_request_fingerprint()
    bound_ip = token_record.get('bound_ip_address')
    bound_ua = token_record.get('bound_user_agent')
    first_used = token_record.get('first_used_timestamp')

    now = time.time()
    expiration = _compute_expiration(token_record) if first_used is not None else None

    if first_used is None:
        with _TOKEN_LOCK:
            token_record['first_used_timestamp'] = now
            token_record['bound_ip_address'] = ip_address
            token_record['bound_user_agent'] = user_agent
            _TOKEN_STORE[token] = token_record
        expiration = _compute_expiration(token_record)
        _persist_token(token)
    else:
        if (bound_ip and bound_ip != ip_address) or (bound_ua and bound_ua != user_agent):
            return jsonify({'status': 'error', 'message': 'Token already bound to another device.'}), 403
        if expiration is None or now > expiration:
            with _TOKEN_LOCK:
                _TOKEN_STORE.pop(token, None)
            _persist_token(token)
            return jsonify({'status': 'error', 'message': 'Token expired.'}), 401

    session['authenticated'] = True
    session['token'] = token
    session.permanent = False

    return jsonify({
        'status': 'ok',
        'message': 'Token verified.',
        'expires_at': expiration
    }), 200


def _validate_session_and_token():
    if not session.get('authenticated'):
        return False, jsonify({'error': 'Authentication required.'}), 401

    token = session.get('token')
    if not token:
        session.clear()
        return False, jsonify({'error': 'Authentication required.'}), 401

    _refresh_token_store()
    with _TOKEN_LOCK:
        token_record = _TOKEN_STORE.get(token)

    if not token_record:
        session.clear()
        return False, jsonify({'error': 'Token invalid.'}), 401

    duration = token_record.get('duration_minutes')
    first_used = token_record.get('first_used_timestamp')
    if not isinstance(duration, (int, float)) or float(duration) <= 0 or first_used is None:
        with _TOKEN_LOCK:
            _TOKEN_STORE.pop(token, None)
        _persist_token(token)
        session.clear()
        return False, jsonify({'error': 'Token invalid.'}), 401

    expiration = _compute_expiration(token_record)
    now = time.time()
    if expiration is None or now > expiration:
        with _TOKEN_LOCK:
            _TOKEN_STORE.pop(token, None)
        _persist_token(token)
        session.clear()
        return False, jsonify({'error': 'Token expired.'}), 401

    ip_address, user_agent = _get_request_fingerprint()
    bound_ip = token_record.get('bound_ip_address')
    bound_ua = token_record.get('bound_user_agent')

    if bound_ip != ip_address or bound_ua != user_agent:
        return False, jsonify({'error': 'Device mismatch.'}), 403

    return True, token_record, None


@app.route('/ask', methods=['POST', 'OPTIONS'])
def ask_skycap():
    # Handle CORS preflight explicitly
    if request.method == 'OPTIONS':
        return ('', 204)
    if agent is None:
        return jsonify({'answer': 'Service is not available due to an initialization error.'}), 503

    is_valid, payload, status_code = _validate_session_and_token()
    if not is_valid:
        return payload, status_code
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({'error': 'Invalid request. Missing "query" key.'}), 400
    ai_response = agent.ask(data['query'])
    return jsonify(ai_response)


@app.after_request
def add_cors_headers(resp):  # Fallback to guarantee CORS headers for preflight/POST
    try:
        origin = request.headers.get('Origin')
        if origin and origin.startswith(ALLOWED_ORIGIN):
            resp.headers['Access-Control-Allow-Origin'] = origin
            resp.headers['Vary'] = 'Origin'
            resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
            resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            resp.headers['Access-Control-Allow-Credentials'] = 'true'
            resp.headers['Access-Control-Max-Age'] = '3600'
    except Exception:
        pass
    return resp


@app.route('/<path:any_path>', methods=['OPTIONS'])
def cors_preflight_any(any_path):
    origin = request.headers.get('Origin', '')
    resp = app.make_response("")
    resp.status_code = 204
    if origin and origin.startswith(ALLOWED_ORIGIN):
        req_headers = request.headers.get('Access-Control-Request-Headers', '')
        resp.headers['Access-Control-Allow-Origin'] = origin
        resp.headers['Vary'] = 'Origin'
        resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = req_headers or 'Content-Type, Authorization'
        resp.headers['Access-Control-Allow-Credentials'] = 'true'
        resp.headers['Access-Control-Max-Age'] = '3600'
    return resp

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)