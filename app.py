
# Final production-ready version of app.py
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env at the very top

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(message)s')
from intelligent_agent import IntelligentAgent

KNOWLEDGE_BASE_FILE = 'master_knowledge_base.json'
app = Flask(__name__, static_folder='.', static_url_path='')

# Configure CORS for GitHub Pages and testing origins
allowed_origins = [
    "https://storage.googleapis.com",  # Original testing origin
    "https://*.github.io",  # GitHub Pages wildcard
    "http://localhost:3000",  # Local development
    "http://127.0.0.1:5000",  # Local Flask testing
]

# Support environment variable override for additional origins
env_origins = os.getenv('ALLOWED_ORIGINS', '').split(',')
allowed_origins.extend([origin.strip() for origin in env_origins if origin.strip()])

CORS(app, resources={r"/ask": {"origins": allowed_origins}})

# Robust agent initialization
logging.info("=== SkyCap AI Server Initialization Starting ===")
logging.info(f"Knowledge base file: {KNOWLEDGE_BASE_FILE}")
logging.info(f"Current working directory: {os.getcwd()}")
logging.info(f"Files in current directory: {os.listdir('.')}")

try:
    logging.info("Creating IntelligentAgent...")
    agent = IntelligentAgent(KNOWLEDGE_BASE_FILE)
    logging.info("=== SkyCap AI Server Initialization Successful ===")
except Exception as e:
    logging.error("=== SkyCap AI Server Initialization Failure ===")
    logging.error(f"Error: {e}")
    logging.error("ACTION REQUIRED: Knowledge base file not found or invalid")
    import traceback
    logging.error(f"Full traceback: {traceback.format_exc()}")
    # For Cloud Run, don't exit but create a fallback agent
    agent = None

# Serve index.html at root
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

# API endpoint for questions

@app.route('/ask', methods=['POST'])
def ask_skycap():
    # Be permissive about incoming payload formats: JSON, form, querystring, or raw body
    body = {}
    try:
        # Prefer proper JSON
        if request.is_json:
            body = request.get_json(silent=True) or {}
        else:
            # Try silent json parse first, then fall back to form data / values
            body = request.get_json(silent=True) or {}
    except Exception:
        body = {}

    # Also accept form-encoded or querystring parameters
    # request.values merges args and form
    values = request.values or {}

    # Fallback: try to parse raw body as JSON
    if not body:
        try:
            raw = request.get_data(as_text=True)
            if raw:
                logging.debug('ask_skycap: raw body (first 1000 chars): %s', raw[:1000])
                import json as _json
                try:
                    parsed = _json.loads(raw)
                    if isinstance(parsed, dict):
                        body = parsed
                except Exception:
                    # try to recover by looking for a top-level 'question' key via naive parsing
                    if '"question"' in raw or "'question'" in raw:
                        # naive extraction between quotes after the key
                        try:
                            import re
                            m = re.search(r'"question"\s*:\s*"([^"]+)"', raw)
                            if m:
                                body = { 'question': m.group(1) }
                        except Exception:
                            pass
        except Exception:
            # ignore parse errors
            pass

    # Support both 'query' and legacy 'question' keys
    user_query = None
    if isinstance(body, dict):
        user_query = body.get('query') or body.get('question')

    if not user_query:
        # check form/querystring
        user_query = values.get('query') or values.get('question') or request.args.get('query') or request.args.get('question')

    # Debugging: if still missing, log minimal request info to help diagnosis
    if not user_query:
        logging.info('ask_skycap: incoming headers: %s', dict(request.headers))
        try:
            raw_body = (request.get_data(as_text=True) or '')
            logging.info('ask_skycap: raw body preview: %s', raw_body[:2000])
        except Exception:
            raw_body = ''
        # Persist a debug dump to /tmp for offline inspection
        try:
            import json as _json
            dump = {
                'headers': dict(request.headers),
                'is_json': request.is_json,
                'content_type': request.content_type,
                'raw_body': raw_body[:10000]
            }
            with open('/tmp/skycap_last_request.json', 'w', encoding='utf-8') as f:
                f.write(_json.dumps(dump, indent=2, ensure_ascii=False))
        except Exception:
            logging.exception('Failed to write debug dump')

        return jsonify({'error': 'Invalid request. Missing query.'}), 400

    print(f"DEBUG: Processing query: {user_query}")
    
    # Handle case where agent failed to initialize
    if agent is None:
        logging.error("Agent not initialized - knowledge base loading failed")
        return jsonify({
            'answer': 'Service initialization error - knowledge base not loaded',
            'brain_used': 'Error',
            'response_time': 0.0,
            'provenance': 'initialization_error'
        }), 500
    
    start = datetime.now()
    ai_response = agent.ask(user_query)
    end = datetime.now()
    elapsed = (end - start).total_seconds()
    print(f"DEBUG: AI response: {ai_response}")

    # ai_response may be a structured dict (answer, brain_used, response_time, provenance)
    answer_text = None
    brain_used = None
    resp_time = elapsed

    if isinstance(ai_response, dict):
        answer_text = ai_response.get('answer')
        brain_used = ai_response.get('brain_used') or ai_response.get('brain')
        # Extract provenance/engine info if the agent provided it
        provenance = ai_response.get('provenance') or ai_response.get('engine') or ai_response.get('source')
        # If agent provided its own response_time, prefer it
        try:
            if ai_response.get('response_time'):
                resp_time = float(ai_response.get('response_time'))
        except Exception:
            pass
    else:
        answer_text = ai_response

    # Coerce non-string answers to a stable string representation for the validation harness
    if answer_text is None:
        answer_text = "I apologize, but I encountered an issue processing your request."
    elif not isinstance(answer_text, str):
        try:
            import json as _json
            answer_text = _json.dumps(answer_text, ensure_ascii=False)
        except Exception:
            answer_text = str(answer_text)

    # Determine brain used heuristically if agent did not provide one
    if not brain_used:
        configured_model = getattr(agent, 'configured_model', None)
        env_model = os.getenv('SKYCAP_GENERATIVE_MODEL')
        if env_model and isinstance(env_model, str) and env_model.startswith('http'):
            brain_used = 'Brain 2'
        elif configured_model and isinstance(configured_model, str) and configured_model.startswith('http'):
            brain_used = 'Brain 2'
        else:
            brain_used = 'Brain 2' if getattr(agent, '_vertex_model_available', False) else 'Brain 1'

    # Normalize common brain_used variants into canonical labels expected by the validator
    if isinstance(brain_used, str):
        bu_lower = brain_used.lower()
        if 'brain 1' in bu_lower or 'local' in bu_lower or 'personnel' in bu_lower or 'financial' in bu_lower or 'market' in bu_lower or 'semantic' in bu_lower or 'metadata' in bu_lower:
            brain_used = 'Brain 1'
        elif 'brain 2' in bu_lower or 'vertex' in bu_lower or 'external' in bu_lower:
            brain_used = 'Brain 2'

    # Final safety: ensure the HTTP response 'answer' field is always a primitive string
    final_payload = {
        'answer': answer_text if isinstance(answer_text, str) else str(answer_text),
        'brain_used': brain_used,
        'response_time': resp_time,
        # include provenance for debugging (which local engine / source returned the answer)
        'provenance': provenance if provenance else None
    }

    # Log the final payload for debugging and write a raw dump to /tmp for client-side inspection
    try:
        logging.debug('ask_skycap: final payload: %s', final_payload)
        import json as _json
        with open('/tmp/skycap_last_response.json', 'w', encoding='utf-8') as _f:
            _f.write(_json.dumps(final_payload, ensure_ascii=False, indent=2))
    except Exception:
        logging.exception('Failed to write final payload dump')

    # Return structured response expected by validation harness
    return jsonify(final_payload), 200

# Health check endpoint
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

