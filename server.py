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
    """Test LLM connectivity from the server - tests each provider."""
    import urllib.request, urllib.error, json as _json, os
    results = {}

    # Test OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    results["openai_key_set"] = bool(openai_key)
    if openai_key:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {openai_key}"}
            body = _json.dumps({"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Say OK"}], "max_tokens": 5}).encode()
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = _json.loads(resp.read().decode())
                results["openai"] = "OK: " + data["choices"][0]["message"]["content"][:50]
        except urllib.error.HTTPError as e:
            results["openai"] = f"HTTPError {e.code}: {e.read().decode()[:100]}"
        except Exception as e:
            results["openai"] = f"Error: {type(e).__name__}: {e}"

    # Test Z.AI
    try:
        from chatbot_engine import _try_zai
        resp = _try_zai("test", "Say OK", timeout=15)
        results["zai"] = "OK: " + resp[:50] if resp else "Empty response"
    except Exception as e:
        results["zai"] = f"Error: {type(e).__name__}: {e}"

    # Test Groq
    groq_key = os.environ.get("GROQ_API_KEY", "")
    results["groq_key_set"] = bool(groq_key)
    if groq_key:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {groq_key}"}
            body = _json.dumps({"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "Say OK"}], "max_tokens": 5}).encode()
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = _json.loads(resp.read().decode())
                results["groq"] = "OK: " + data["choices"][0]["message"]["content"][:50]
        except urllib.error.HTTPError as e:
            results["groq"] = f"HTTPError {e.code}: {e.read().decode()[:100]}"
        except Exception as e:
            results["groq"] = f"Error: {type(e).__name__}: {e}"

    return jsonify(results)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)

