
# Final production-ready version of app.py with enhanced startup error handling
import os
import sys
import traceback
from datetime import datetime

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Enhanced startup logging
logger.info("=== SkyCap AI Container Starting ===")
logger.info(f"Python version: {sys.version}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Environment PORT: {os.environ.get('PORT', 'NOT SET')}")

try:
    from dotenv import load_dotenv
    load_dotenv()  # Load environment variables from .env at the very top
    logger.info("✓ Environment variables loaded")
except Exception as e:
    logger.warning(f"Could not load .env file: {e}")

try:
    from flask import Flask, request, jsonify, send_from_directory
    from flask_cors import CORS
    logger.info("✓ Flask imported successfully")
except ImportError as e:
    logger.error(f"CRITICAL ERROR: Failed to import Flask: {e}")
    sys.exit(1)

try:
    from intelligent_agent import IntelligentAgent
    logger.info("✓ IntelligentAgent imported successfully")
except ImportError as e:
    logger.error(f"CRITICAL ERROR: Failed to import IntelligentAgent: {e}")
    logger.error(f"Full traceback: {traceback.format_exc()}")
    sys.exit(1)

KNOWLEDGE_BASE_FILE = 'master_knowledge_base.json'
app = Flask(__name__, static_folder='.', static_url_path='')

# Configure CORS for GitHub Pages professional frontend
CORS(app, resources={r"/ask": {"origins": "https://solutions07.github.io"}})

# Lazy loading for Cloud Run startup optimization
logger.info("=== SkyCap AI Server Starting (Lazy Loading Mode) ===")
logger.info(f"Knowledge base file: {KNOWLEDGE_BASE_FILE}")
logger.info(f"Current working directory: {os.getcwd()}")

try:
    files_in_dir = os.listdir('.')
    logger.info(f"Files in current directory: {files_in_dir}")
    
    # Check for critical files
    if KNOWLEDGE_BASE_FILE not in files_in_dir:
        logger.error(f"CRITICAL: Knowledge base file {KNOWLEDGE_BASE_FILE} not found!")
        logger.error("Available files: " + ", ".join(files_in_dir))
    else:
        logger.info(f"✓ Knowledge base file {KNOWLEDGE_BASE_FILE} found")
        
except Exception as e:
    logger.error(f"Error listing directory contents: {e}")

logger.info("✓ Server ready - agent will load on first request")

# Initialize agent lazily to allow fast startup for Cloud Run health checks
agent = None

def get_agent():
    """Lazy load the agent on first use with enhanced error handling"""
    global agent
    if agent is None:
        try:
            logger.info("=== Lazy Loading IntelligentAgent ===")
            
            # Pre-flight checks
            if not os.path.exists(KNOWLEDGE_BASE_FILE):
                raise FileNotFoundError(f"Knowledge base file not found: {KNOWLEDGE_BASE_FILE}")
                
            # Check file is readable
            with open(KNOWLEDGE_BASE_FILE, 'r') as f:
                import json
                kb_data = json.load(f)
                logger.info(f"✓ Knowledge base loaded: {len(kb_data)} entries")
            
            agent = IntelligentAgent(KNOWLEDGE_BASE_FILE)
            logger.info("=== IntelligentAgent Loaded Successfully ===")
            
        except FileNotFoundError as e:
            logger.error(f"=== Knowledge Base File Error ===")
            logger.error(f"Error: {e}")
            agent = "ERROR"
        except json.JSONDecodeError as e:
            logger.error(f"=== Knowledge Base JSON Error ===")
            logger.error(f"Error: {e}")
            agent = "ERROR"
        except ImportError as e:
            logger.error(f"=== Import Error Loading Agent ===")
            logger.error(f"Error: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            agent = "ERROR"
        except Exception as e:
            logger.error("=== IntelligentAgent Loading Failed ===")
            logger.error(f"Error: {e}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            agent = "ERROR"
    return agent

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

    logger.debug(f"Processing query: {user_query}")
    
    # Get agent (lazy loading)
    current_agent = get_agent()
    if current_agent is None or current_agent == "ERROR":
        logger.error("Agent failed to load - knowledge base error")
        return jsonify({
            'answer': 'Service initialization error - knowledge base not loaded',
            'brain_used': 'Error',
            'response_time': 0.0,
            'provenance': 'initialization_error'
        }), 500
    
    start = datetime.now()
    ai_response = current_agent.ask(user_query)
    end = datetime.now()
    elapsed = (end - start).total_seconds()
    logger.debug(f"AI response: {ai_response}")

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
        configured_model = getattr(current_agent, 'configured_model', None)
        env_model = os.getenv('SKYCAP_GENERATIVE_MODEL')
        if env_model and isinstance(env_model, str) and env_model.startswith('http'):
            brain_used = 'Brain 2'
        elif configured_model and isinstance(configured_model, str) and configured_model.startswith('http'):
            brain_used = 'Brain 2'
        else:
            brain_used = 'Brain 2' if getattr(current_agent, '_vertex_model_available', False) else 'Brain 1'

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

# Health check endpoint - responds immediately without loading agent
@app.route('/health', methods=['GET'])
def health():
    try:
        health_data = {
            'status': 'ok',
            'service': 'SkyCap AI',
            'agent_loaded': agent is not None and agent != "ERROR",
            'knowledge_base_exists': os.path.exists(KNOWLEDGE_BASE_FILE),
            'working_directory': os.getcwd(),
            'port': os.environ.get('PORT', 'NOT SET')
        }
        logger.info(f"Health check: {health_data}")
        return jsonify(health_data), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# Lightweight version / build info endpoint for deployment verification
def _get_build_version():
    """Derive build/version info from environment or an optional VERSION file.
    Priority:
      1. APP_VERSION env (explicit)
      2. COMMIT_SHA env (shortened to 12 chars)
      3. VERSION file contents
      4. Fallback 'unknown'
    """
    env_version = os.getenv('APP_VERSION')
    if env_version:
        return env_version
    commit = os.getenv('COMMIT_SHA')
    if commit:
        return commit[:12]
    try:
        if os.path.exists('VERSION'):
            with open('VERSION', 'r', encoding='utf-8') as vf:
                content = vf.read().strip()
                if content:
                    return content
    except Exception:
        pass
    return 'unknown'

@app.route('/version', methods=['GET'])
def version():
    try:
        return jsonify({
            'service': 'SkyCap AI',
            'version': _get_build_version(),
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }), 200
    except Exception as e:
        logger.error(f"Version endpoint failed: {e}")
        return jsonify({'error': 'version_unavailable'}), 500

# Startup probe endpoint - for Cloud Run startup checks
@app.route('/startup', methods=['GET'])
def startup():
    try:
        return jsonify({
            'status': 'ready',
            'timestamp': datetime.now().isoformat(),
            'service': 'SkyCap AI'
        }), 200
    except Exception as e:
        logger.error(f"Startup check failed: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

# Readiness probe - checks if service can handle requests
@app.route('/ready', methods=['GET'])
def ready():
    try:
        # Check if critical files exist
        if not os.path.exists(KNOWLEDGE_BASE_FILE):
            return jsonify({
                'status': 'not_ready',
                'reason': f'Knowledge base file missing: {KNOWLEDGE_BASE_FILE}'
            }), 503
            
        return jsonify({
            'status': 'ready',
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return jsonify({
            'status': 'not_ready',
            'error': str(e)
        }), 503

# Development server launcher
if __name__ == '__main__':
    try:
        # Check if running in production (Cloud Run) or development
        port = int(os.environ.get('PORT', 5001))  # Default to 5001 for local development
        host = '0.0.0.0' if os.environ.get('PORT') else '127.0.0.1'  # Use localhost for dev
        debug = not bool(os.environ.get('PORT'))  # Enable debug mode for local development
        
        logger.info(f"=== Starting Flask Server ===")
        logger.info(f"Host: {host}")
        logger.info(f"Port: {port}")
        logger.info(f"Debug Mode: {debug}")
        logger.info(f"Access the UI at: http://{host}:{port}")
        
        # Final pre-flight check
        logger.info("=== Pre-flight Checks ===")
        logger.info(f"✓ Flask app created successfully")
        logger.info(f"✓ CORS configured")
        logger.info(f"✓ Routes registered: {[rule.rule for rule in app.url_map.iter_rules()]}")
        
        app.run(host=host, port=port, debug=debug)
        
    except Exception as e:
        logger.error(f"CRITICAL: Failed to start Flask server: {e}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        sys.exit(1)

