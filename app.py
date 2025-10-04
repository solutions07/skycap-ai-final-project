import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging
from intelligent_agent import IntelligentAgent

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

app = Flask(__name__)
# This allows the GitHub Pages frontend to communicate with the backend
CORS(app, resources={r"/ask": {"origins": "https://solutions07.github.io"}})

# Define a robust path to the knowledge base file
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_BASE_PATH = os.path.join(APP_ROOT, 'data', 'master_knowledge_base.json')

agent = None
try:
    logging.info(f"Attempting to load knowledge base from: {KNOWLEDGE_BASE_PATH}")
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

@app.route('/ask', methods=['POST'])
def ask_skycap():
    if agent is None:
        return jsonify({'answer': 'Service is not available due to an initialization error.'}), 503
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({'error': 'Invalid request. Missing "query" key.'}), 400
    ai_response = agent.ask(data['query'])
    return jsonify(ai_response)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)