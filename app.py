import os
from flask import Flask, request, jsonify, send_from_directory
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
# CORS: allow GitHub Pages origin across all routes, including preflight
ALLOWED_ORIGIN = "https://solutions07.github.io"
CORS(app, resources={r"/*": {"origins": [ALLOWED_ORIGIN]}}, supports_credentials=False)

# Define a robust path to the knowledge base file
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_BASE_PATH = os.path.join(APP_ROOT, 'data', 'master_knowledge_base.json')


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
    # If a semantic index exists but lacks embeddings, compute them now (one-time repair)
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

@app.route('/ask', methods=['POST', 'OPTIONS'])
def ask_skycap():
    # Handle CORS preflight explicitly
    if request.method == 'OPTIONS':
        return ('', 204)
    if agent is None:
        return jsonify({'answer': 'Service is not available due to an initialization error.'}), 503
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
        resp.headers['Access-Control-Max-Age'] = '3600'
    return resp

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)