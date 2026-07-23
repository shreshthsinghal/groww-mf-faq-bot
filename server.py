"""
Flask server for Groww MF FAQ bot.
"""
import os
from pathlib import Path

from flask import Flask, request, jsonify, render_template
from chatbot_engine import GrowwMFChatbot

BASE_DIR = Path(__file__).parent
app = Flask(__name__,
            template_folder=str(BASE_DIR / "templates"),
            static_folder=str(BASE_DIR / "static"))

print("Loading GrowwMFChatbot engine...", flush=True)
bot = GrowwMFChatbot(verbose=False)
print(f"Engine ready. {len(bot.chunks)} chunks indexed.", flush=True)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/answer", methods=["POST"])
def api_answer():
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    if not query:
        return jsonify({
            "query": "",
            "intent": "empty",
            "answer": "Please ask a question.",
            "citation_url": None,
            "citation_title": None,
            "last_updated": None,
            "retrieved_chunk_ids": [],
            "route": "out_of_scope",
            "rule_triggered": "empty_input",
        }), 200
    try:
        result = bot.answer(query)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({
            "query": query,
            "intent": "error",
            "answer": f"Lookup error: {e}",
            "citation_url": None,
            "citation_title": None,
            "last_updated": None,
            "retrieved_chunk_ids": [],
            "route": "error",
            "rule_triggered": "exception",
        }), 500


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "chunks_indexed": len(bot.chunks),
        "intent_classifier": type(bot.clf).__name__,
    }), 200


@app.route("/api/llm-test")
def llm_test():
    """Test LLM connectivity from the server."""
    try:
        from chatbot_engine import _call_zai_chat, _load_zai_config
        cfg = _load_zai_config()
        resp = _call_zai_chat("You are a test bot.", "Say OK", timeout=15)
        return jsonify({
            "config_loaded": True,
            "base_url": cfg.get("baseUrl"),
            "has_token": bool(cfg.get("token")),
            "llm_response": resp[:200] if resp else "(empty)",
            "llm_works": bool(resp),
        })
    except Exception as e:
        return jsonify({"error": str(e), "error_type": type(e).__name__}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)

