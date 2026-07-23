"""
Step 6b — Groww MF FAQ Chatbot Engine.

Pipeline:
  1. HARD RULE GATES (defense in depth)
     a. PII detection (PAN / Aadhaar / OTP / email / phone / account#)  -> refuse + warn
     b. Performance keywords (CAGR / XIRR / returns / NAV / alpha)      -> refuse + factsheet link
  2. INTENT CLASSIFIER (LinearSVC, trained in Step 5)
     routes to one of 11 intents
  3. ROUTING
     - factual_*       -> retrieve top-k chunks -> LLM answer with citation
     - refusal_advice  -> canned refusal + educational link
     - refusal_perf    -> canned refusal + factsheet link (also caught by 1b)
     - refusal_pii     -> PII refusal (also caught by 1a)
     - out_of_scope    -> polite redirect
  4. LLM ANSWER (via z-ai chat CLI)
     System prompt enforces:
       - ≤3 sentences
       - cite ONE source URL
       - end with "Last updated from sources: <date>"
       - no advice, no performance claims
       - if context lacks answer, say so honestly

Output (dict):
  {
    "query": str,
    "intent": str,
    "answer": str,
    "citation_url": str | None,
    "citation_title": str | None,
    "last_updated": str,
    "retrieved_chunk_ids": list[str],
    "route": "factual" | "refusal" | "out_of_scope",
    "rule_triggered": str | None,
  }
"""
import os, re, json, pickle, subprocess, tempfile, time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = Path(__file__).parent
MODELS_DIR = BASE / "models"
INDEX_DIR = BASE / "index"

# Fallback for local dev
if not MODELS_DIR.exists():
    MODELS_DIR = Path("/home/z/my-project/download/models")
if not INDEX_DIR.exists():
    INDEX_DIR = Path("/home/z/my-project/download/index")

INTENT_MODEL_PATH = MODELS_DIR / "intent_classifier_LinearSVC.pkl"
TFIDF_INTENT_PATH = MODELS_DIR / "tfidf_vectorizer.pkl"
LABEL_ENCODER_PATH = MODELS_DIR / "label_encoder.pkl"
CHUNK_INDEX_PATH = INDEX_DIR / "tfidf_chunks.pkl"

# ---------------------------------------------------------------------------
# Hard-rule patterns
# ---------------------------------------------------------------------------
# PAN: 5 letters + 4 digits + 1 letter (e.g. ABCDE1234F)
PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
# Aadhaar: 12 digits, optionally with spaces/dashes (XXXX XXXX XXXX)
AADHAAR_RE = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")
# OTP: 4-6 digit standalone number, with otp context
OTP_RE = re.compile(r"\b(?:otp|one[\s-]?time[\s-]?password|verification[\s-]?code)[\s:=-]*\d{4,6}\b", re.I)
OTP_BARE_RE = re.compile(r"\b\d{6}\b")  # careful: only triggers if other context
# Email
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# Indian phone: 10 digits starting 6-9
PHONE_RE = re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)")
# Account number: "account no", "account number", "acct" + digits
ACCT_RE = re.compile(r"\b(?:account|acct|folio|client)[\s-]?(?:no|number|#|id)?[\s:=-]*\d{6,}\b", re.I)
# CVV / Card number
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")
CVV_RE = re.compile(r"\bcvv[\s:=-]*\d{3,4}\b", re.I)

PII_PATTERNS = [
    ("PAN", PAN_RE),
    ("Aadhaar", AADHAAR_RE),
    ("OTP", OTP_RE),
    ("Email", EMAIL_RE),
    ("Phone", PHONE_RE),
    ("Account_number", ACCT_RE),
    ("CVV", CVV_RE),
]

# Performance keywords that should trigger refusal
PERF_KEYWORDS = [
    "cagr", "xirr", "irr", "absolute return", "trailing return",
    "1 year return", "1-year return", "3 year return", "3-year return",
    "5 year return", "5-year return", "10 year return",
    "ytd return", "yearly return", "monthly return",
    "alpha", "sharpe", "sortino", "treynor", "beta of",
    "outperform", "underperform", "beating benchmark",
    "best performing", "top performing", "highest return",
    "nav history", "past returns", "fund performance",
    "compare returns", "return comparison",
]
# Note: "returns" alone is too broad — needs context. "CAGR", "XIRR" are clear.
PERF_RE = re.compile(
    r"\b(?:cagr|xirr|irr|alpha|sharpe|sortino|treynor|"
    r"outperform\w*|underperform\w*|"
    r"best[\s-]?performing|top[\s-]?performing|highest[\s-]?return|"
    r"nav[\s-]?history|past[\s-]?returns|fund[\s-]?performance|"
    r"return[\s-]?comparison|compare[\s-]?returns|"
    r"1[\s-]?year[\s-]?return|3[\s-]?year[\s-]?return|5[\s-]?year[\s-]?return|"
    r"10[\s-]?year[\s-]?return|ytd[\s-]?return|"
    r"yearly[\s-]?return|monthly[\s-]?return|trailing[\s-]?return|absolute[\s-]?return"
    r")\b",
    re.I,
)
# Standalone "return(s)" or "performance" or "nav" — check more carefully
PERF_SOFT_RE = re.compile(r"\b(?:returns?|performance|nav)\b", re.I)

# ---------------------------------------------------------------------------
# Canned refusal messages
# ---------------------------------------------------------------------------
EDU_LINKS = {
    "expense_ratio": "https://groww.in/p/expense-ratio",
    "exit_load": "https://groww.in/p/exit-load-in-mutual-funds",
    "riskometer": "https://groww.in/p/riskometer",
    "sip": "https://groww.in/p/sip-systematic-investment-plan",
    "sid": "https://groww.in/p/scheme-information-document",
    "sebi_investor": "https://investor.sebi.gov.in/",
    "sebi_riskometer": "https://investor.sebi.gov.in/riskometer.html",
    "sebi_exit_load": "https://investor.sebi.gov.in/exit_load.html",
    "sebi_mf_faq": "https://www.sebi.gov.in/sebi_data/faqfiles/sep-2024/1727242783639.pdf",
}

FACTSHEET_NOTE = "For scheme performance, please refer to the official factsheet PDF on the AMC website: https://www.growwmf.in/downloads/sid"

PII_REFUSAL = (
    "I can't process queries containing personal information (PAN, Aadhaar, OTP, "
    "email, phone, account numbers, etc.). For your security, please redact such "
    "details and rephrase your question."
)

ADVICE_REFUSAL = (
    "I can only share factual information about mutual fund schemes (e.g., expense "
    "ratio, exit load, lock-in, riskometer, benchmark, statements). I can't offer "
    "buy/sell/hold advice or recommend specific funds. Learn more: "
)
ADVICE_LINK = EDU_LINKS["sebi_mf_faq"]

PERFORMANCE_REFUSAL = (
    "I can't provide performance figures, returns, CAGR, or NAV history — those "
    "change daily and require official factsheets. " + FACTSHEET_NOTE
)

OUT_OF_SCOPE_MSG = (
    "I'm a facts-only assistant for Groww Mutual Fund schemes. I can answer "
    "questions like expense ratio, exit load, minimum SIP, ELSS lock-in, "
    "riskometer, benchmark, and how to download statements."
)

WELCOME_MSG = (
    "Hi! I'm a facts-only assistant for Groww Mutual Fund schemes. "
    "Ask me about expense ratio, exit load, minimum SIP, ELSS lock-in, "
    "riskometer, benchmark, or how to download statements."
)

EXAMPLE_QUESTIONS = [
    "What is the expense ratio of Groww Large Cap Fund?",
    "What is the lock-in period of Groww ELSS Tax Saver Fund?",
    "How do I download my capital gains statement?",
]

FACTS_ONLY_NOTE = "Facts-only. No investment advice."


# ---------------------------------------------------------------------------
# Z.AI API client (direct HTTP, no subprocess)
# ---------------------------------------------------------------------------
def _load_zai_config():
    """Load Z.AI config from .z-ai-config file or env vars."""
    config_paths = [
        Path.cwd() / ".z-ai-config",
        Path.home() / ".z-ai-config",
        Path("/etc/.z-ai-config"),
    ]
    for p in config_paths:
        try:
            with open(p) as f:
                cfg = json.load(f)
                if cfg.get("baseUrl") and cfg.get("apiKey"):
                    return cfg
        except (OSError, json.JSONDecodeError):
            continue
    return {
        "baseUrl": os.environ.get("ZAI_BASE_URL", "https://internal-api.z.ai/v1"),
        "apiKey": os.environ.get("ZAI_API_KEY", "Z.ai"),
        "token": os.environ.get("ZAI_TOKEN", ""),
        "chatId": os.environ.get("ZAI_CHAT_ID", ""),
        "userId": os.environ.get("ZAI_USER_ID", ""),
    }


def _call_zai_chat(system_prompt: str, user_prompt: str, timeout: int = 30) -> str:
    """Call LLM API. Tries OpenRouter first (free, no IP restrictions),
    then OpenAI, then Z.AI, then Groq as fallbacks.
    """
    # Provider 1: OpenRouter (free, works from any IP, no credits needed)
    openrouter_result = _try_openrouter(system_prompt, user_prompt, timeout)
    if openrouter_result:
        return openrouter_result

    # Provider 2: OpenAI (if key set and has credits)
    openai_result = _try_openai(system_prompt, user_prompt, timeout)
    if openai_result:
        return openai_result

    # Provider 3: Z.AI (fallback for local dev)
    zai_result = _try_zai(system_prompt, user_prompt, timeout)
    if zai_result:
        return zai_result

    # Provider 4: Groq (if key set)
    groq_result = _try_groq(system_prompt, user_prompt, timeout)
    if groq_result:
        return groq_result

    return ""


def _try_openrouter(system_prompt, user_prompt, timeout):
    """Try OpenRouter API. Free models, works from any IP."""
    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not openrouter_key:
        return ""
    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openrouter_key}",
            "HTTP-Referer": "https://groww-mf-faq-bot.vercel.app",
            "X-Title": "Groww MF Facts Bot",
        }
        body = json.dumps({
            "model": "google/gemma-4-26b-a4b-it:free",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 200,
            "temperature": 0.3,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = (data.get("choices", [{}])[0]
                       .get("message", {})
                       .get("content", "")
                       .strip())
            return content if content else ""
    except Exception:
        return ""


def _try_openai(system_prompt, user_prompt, timeout):
    """Try OpenAI API. Primary provider - works from Railway's US/EU servers."""
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        return ""
    try:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_key}",
        }
        body = json.dumps({
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 200,
            "temperature": 0.3,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return (data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip())
    except Exception:
        return ""


def _try_zai(system_prompt, user_prompt, timeout):
    """Try Z.AI API."""
    try:
        cfg = _load_zai_config()
        url = f"{cfg['baseUrl']}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['apiKey']}",
            "X-Z-AI-From": "Z",
        }
        if cfg.get("chatId"):
            headers["X-Chat-Id"] = cfg["chatId"]
        if cfg.get("userId"):
            headers["X-User-Id"] = cfg["userId"]
        if cfg.get("token"):
            headers["X-Token"] = cfg["token"]
        body = json.dumps({
            "model": "glm-4-plus",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return (data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip())
    except Exception:
        return ""


def _try_groq(system_prompt, user_prompt, timeout):
    """Try Groq API."""
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        return ""
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {groq_key}",
        }
        body = json.dumps({
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 200,
        }).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return (data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip())
    except Exception:
        return ""


def _try_pollinations(system_prompt, user_prompt, timeout):
    """Try Pollinations API (free, no key needed)."""
    try:
        # Combine system + user prompt into a single text prompt
        combined = f"{system_prompt}\n\n{user_prompt}"
        # URL-encode the prompt
        encoded = urllib.parse.quote(combined)
        url = f"https://text.pollinations.ai/{encoded}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "GrowwMFBot/1.0",
            "Referer": "https://groww-mf-faq-bot.vercel.app",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8").strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class GrowwMFChatbot:
    def __init__(self, verbose=False):
        self.verbose = verbose
        # Load intent classifier artifacts
        with open(INTENT_MODEL_PATH, "rb") as f:
            self.clf = pickle.load(f)
        with open(TFIDF_INTENT_PATH, "rb") as f:
            self.tfidf_intent = pickle.load(f)
        with open(LABEL_ENCODER_PATH, "rb") as f:
            self.le = pickle.load(f)
        # Load chunk retrieval index
        with open(CHUNK_INDEX_PATH, "rb") as f:
            idx = pickle.load(f)
        self.tfidf_chunks = idx["vectorizer"]
        self.chunk_matrix = idx["matrix"]
        self.chunks = idx["chunks"]
        if verbose:
            print(f"[engine] loaded: clf={type(self.clf).__name__}, "
                  f"chunks={len(self.chunks)}, features={idx['n_features']}")
        from sklearn.metrics.pairwise import cosine_similarity
        self._cosine = cosine_similarity

    # ------------------- Hard rules -------------------
    def detect_pii(self, query: str):
        for name, pat in PII_PATTERNS:
            m = pat.search(query)
            if m:
                return name, m.group(0)
        return None, None

    def detect_performance(self, query: str):
        """Return True if query asks about performance/returns/NAV/CAGR."""
        # Strong signal: explicit terms
        if PERF_RE.search(query):
            return True
        # Soft signal: "returns" / "performance" / "NAV" with scheme context
        if PERF_SOFT_RE.search(query):
            # Check if also mentions a scheme or "fund"
            if re.search(r"groww|fund|scheme|elss|large cap|small cap|mid cap|"
                         r"liquid|overnight|index|value", query, re.I):
                return True
        return False

    # ------------------- Intent classifier -------------------
    def classify_intent(self, query: str) -> str:
        vec = self.tfidf_intent.transform([query])
        idx = self.clf.predict(vec)[0]
        return self.le.inverse_transform([idx])[0]

    # ------------------- Retrieval -------------------
    def retrieve(self, query: str, top_k: int = 8):
        """Retrieve top-k chunks via TF-IDF cosine similarity, then re-rank
        by query-term density (chunks containing more query terms rank higher).

        Two-pass design:
          1. TF-IDF pool: take top (top_k * 8) chunks by cosine similarity.
          2. Literal-phrase injection: scan ALL chunks for ones that contain
             BOTH a fact term from the query AND a scheme/fund name. These are
             guaranteed relevant even if TF-IDF underrates them (TF-IDF favors
             chunks that repeat the scheme name many times, like fund-manager
             bios, missing the chunk that actually has the fact).
          3. Re-rank combined pool by TF-IDF + query-term-density + fact-term bonus.
        """
        qv = self.tfidf_chunks.transform([query])
        scores = self._cosine(qv, self.chunk_matrix).flatten()
        # Pass 1: TF-IDF candidate pool
        pool = set(sorted(range(len(scores)), key=lambda i: -scores[i])[:top_k * 8])

        # Pass 2: literal-phrase injection
        # Match fact-term in chunk TEXT, and scheme-name in EITHER chunk text
        # OR the chunk's page title/URL (because SID/KIM sections often state
        # "Exit load: NIL" without repeating the scheme name in the same chunk).
        q_lower = query.lower()
        fact_terms_in_query = [t for t in ["expense ratio", "exit load",
                                            "minimum sip", "min sip",
                                            "lock-in", "lock in", "lockin",
                                            "riskometer", "risk-o-meter",
                                            "benchmark", "capital gains",
                                            "statement", "section 80c",
                                            "tax proof", "tax statement",
                                            "consolidated account", "cas"]
                               if t in q_lower]
        scheme_names_in_query = [s for s in
                                 ["groww large cap", "groww value fund",
                                  "groww small cap", "groww elss",
                                  "groww nifty 50", "groww liquid",
                                  "groww overnight", "groww multicap",
                                  "large cap fund", "value fund",
                                  "small cap fund", "elss tax saver",
                                  "nifty 50 index", "liquid fund",
                                  "overnight fund"]
                                 if s in q_lower]
        if fact_terms_in_query and scheme_names_in_query:
            for i, c in enumerate(self.chunks):
                if i in pool:
                    continue
                t = c["text"].lower()
                # Scheme can be in chunk text OR page title OR url
                page_meta = (c.get("title", "") + " " + c.get("url", "")).lower()
                fact_in_chunk = any(ft in t for ft in fact_terms_in_query)
                scheme_in_chunk = any(sn in t for sn in scheme_names_in_query)
                scheme_in_meta = any(sn in page_meta for sn in scheme_names_in_query)
                if fact_in_chunk and (scheme_in_chunk or scheme_in_meta):
                    pool.add(i)
                    if len(pool) >= top_k * 16:
                        break

        # Re-rank pool
        stop = set("the of and or to in for is what how a an with from on by "
                   "do you your my me i are was were be been being this that "
                   "these those it its as at vs versus please tell show get "
                   "find about which what's".split())
        qtokens = [t.lower().strip(".,?!:;()[]") for t in re.split(r"\W+", query)
                   if t.lower().strip(".,?!:;()[]") and t.lower() not in stop and len(t) >= 3]

        reranked = []
        for ix in pool:
            if scores[ix] <= 0 and ix not in pool:
                continue
            c = self.chunks[ix]
            text_lower = c["text"].lower()
            page_meta = (c.get("title", "") + " " + c.get("url", "")).lower()
            overlap = sum(1 for t in qtokens if t in text_lower)
            fact_bonus = sum(2 for t in fact_terms_in_query if t in text_lower)
            scheme_bonus = sum(1 for s in scheme_names_in_query
                               if s in text_lower or s in page_meta)
            # Combined: TF-IDF base + density + fact-term + scheme-name boost
            combined = (scores[ix]
                        + 0.02 * overlap
                        + 0.08 * fact_bonus
                        + 0.04 * scheme_bonus)
            reranked.append((combined, ix))
        reranked.sort(key=lambda x: -x[0])

        results = []
        for combined, ix in reranked[:top_k]:
            c = self.chunks[ix]
            results.append({
                "chunk_id": c["chunk_id"],
                "page_id": c["page_id"],
                "title": c["title"],
                "url": c["url"],
                "group": c["group"],
                "source": c["source"],
                "type": c["type"],
                "score": float(scores[ix]),
                "rerank_score": float(combined),
                "text": c["text"],
            })
        return results

    # ------------------- LLM call -------------------
    def llm_answer(self, query: str, retrieved: list, intent: str = ""):
        """Generate answer using LLM. Pure LLM-based, no regex fallback."""
        today = datetime.now(IST).strftime("%d %b %Y")

        def _clean(s):
            return (s or "").replace("\x00", " ").replace("\r", " ").strip()

        # Use only top 3 chunks to keep context focused
        top_chunks = retrieved[:3]

        # Build concise context
        context_parts = []
        for i, r in enumerate(top_chunks, 1):
            # Truncate each chunk to ~800 chars to keep prompt focused
            chunk_text = _clean(r["text"])[:800]
            context_parts.append(f"[Source {i}] {r['title']}\n{chunk_text}")
        context = "\n\n".join(context_parts)
        query_clean = _clean(query)

        system_prompt = (
            "Answer the question directly. Do NOT show your reasoning or thought process. "
            "Do NOT mention 'according to context' or 'source says'. "
            "Just state the fact in 1-3 sentences. "
            f"End with: Last updated from sources: {today}"
        )
        user_prompt = (
            f"Question: {query_clean}\n\n"
            f"Context:\n{context}\n\n"
            f"Give the direct answer (no reasoning):"
        )

        answer = _call_zai_chat(system_prompt, user_prompt, timeout=10)

        # If LLM succeeded, use it
        if answer:
            # Ensure it has the Last updated line
            if "Last updated from sources:" not in answer:
                answer = answer.rstrip(".") + f".\n\nLast updated from sources: {today}"
            cit_url = retrieved[0]["url"] if retrieved else None
            cit_title = retrieved[0]["title"] if retrieved else None
            return answer, cit_url, cit_title

        # Fallback only if LLM completely fails (network error etc)
        answer = self._fallback_answer(query, retrieved)
        answer = answer + f"\n\nLast updated from sources: {today}"
        cit_url = retrieved[0]["url"] if retrieved else None
        cit_title = retrieved[0]["title"] if retrieved else None
        return answer, cit_url, cit_title

    def _fallback_answer(self, query: str, retrieved: list) -> str:
        """If LLM fails, return the top retrieved chunk's first 2 sentences as the answer."""
        if not retrieved:
            return "I couldn't find this in the available public sources."
        top = retrieved[0]
        text = top["text"].replace("\n", " ").strip()
        # Take first ~2 sentences
        sents = re.split(r"(?<=[.!?])\s+", text)
        ans = " ".join(sents[:2])
        return ans

    # ------------------- Main entry point -------------------
    def answer(self, query: str) -> dict:
        query = (query or "").strip()
        if not query:
            return {
                "query": query, "intent": "empty", "answer": "Please ask a question.",
                "citation_url": None, "citation_title": None,
                "last_updated": None, "retrieved_chunk_ids": [],
                "route": "out_of_scope", "rule_triggered": "empty_input",
            }

        # 1a. PII hard rule
        pii_type, pii_match = self.detect_pii(query)
        if pii_type:
            return {
                "query": query, "intent": "refusal_pii",
                "answer": PII_REFUSAL,
                "citation_url": None, "citation_title": None,
                "last_updated": None, "retrieved_chunk_ids": [],
                "route": "refusal", "rule_triggered": f"pii:{pii_type}",
            }

        # 1b. Performance hard rule
        if self.detect_performance(query):
            return {
                "query": query, "intent": "refusal_performance",
                "answer": PERFORMANCE_REFUSAL,
                "citation_url": "https://www.growwmf.in/downloads/sid",
                "citation_title": "Groww MF — Official SID/Factsheet Downloads",
                "last_updated": datetime.now(IST).strftime("%d %b %Y"),
                "retrieved_chunk_ids": [],
                "route": "refusal", "rule_triggered": "performance_keywords",
            }

        # 2. Intent classifier
        intent = self.classify_intent(query)

        # 3. Route based on intent
        if intent == "refusal_advice":
            return {
                "query": query, "intent": intent,
                "answer": ADVICE_REFUSAL + ADVICE_LINK,
                "citation_url": ADVICE_LINK,
                "citation_title": "SEBI — FAQs for Mutual Fund Investors",
                "last_updated": datetime.now(IST).strftime("%d %b %Y"),
                "retrieved_chunk_ids": [],
                "route": "refusal", "rule_triggered": None,
            }
        if intent == "refusal_pii":
            return {
                "query": query, "intent": intent,
                "answer": PII_REFUSAL,
                "citation_url": None, "citation_title": None,
                "last_updated": None, "retrieved_chunk_ids": [],
                "route": "refusal", "rule_triggered": "classifier_refusal_pii",
            }
        if intent == "refusal_performance":
            return {
                "query": query, "intent": intent,
                "answer": PERFORMANCE_REFUSAL,
                "citation_url": "https://www.growwmf.in/downloads/sid",
                "citation_title": "Groww MF — Official SID/Factsheet Downloads",
                "last_updated": datetime.now(IST).strftime("%d %b %Y"),
                "retrieved_chunk_ids": [],
                "route": "refusal", "rule_triggered": "classifier_refusal_perf",
            }
        if intent == "out_of_scope":
            return {
                "query": query, "intent": intent,
                "answer": OUT_OF_SCOPE_MSG,
                "citation_url": None, "citation_title": None,
                "last_updated": None, "retrieved_chunk_ids": [],
                "route": "out_of_scope", "rule_triggered": "classifier_oos",
            }

        # 4. Factual intent — retrieve + LLM
        retrieved = self.retrieve(query, top_k=8)
        if not retrieved:
            return {
                "query": query, "intent": intent,
                "answer": "I couldn't find relevant information in the available public sources.",
                "citation_url": None, "citation_title": None,
                "last_updated": datetime.now(IST).strftime("%d %b %Y"),
                "retrieved_chunk_ids": [],
                "route": "factual", "rule_triggered": "no_retrieval",
            }

        answer, cit_url, cit_title = self.llm_answer(query, retrieved, intent)
        return {
            "query": query, "intent": intent,
            "answer": answer,
            "citation_url": cit_url,
            "citation_title": cit_title,
            "last_updated": datetime.now(IST).strftime("%d %b %Y"),
            "retrieved_chunk_ids": [r["chunk_id"] for r in retrieved],
            "route": "factual", "rule_triggered": None,
        }


# CLI smoke test
if __name__ == "__main__":
    bot = GrowwMFChatbot(verbose=True)
    test_queries = [
        # Factual
        "What is the expense ratio of Groww Large Cap Fund?",
        "What is the exit load of Groww ELSS Tax Saver Fund?",
        "What is the minimum SIP for Groww Liquid Fund?",
        "What is the lock-in period of Groww ELSS?",
        "What is the riskometer of Groww Small Cap Fund?",
        "What is the benchmark of Groww Nifty 50 Index Fund?",
        "How do I download my capital gains statement?",
        # Refusal — advice
        "Should I buy Groww Large Cap?",
        "Which is better Groww ELSS or Groww Value Fund?",
        # Refusal — performance
        "What is the CAGR of Groww ELSS?",
        "What are the 5 year returns of Groww Small Cap?",
        # Refusal — PII
        "My PAN is ABCDE1234F, what is the expense ratio?",
        "Send the statement to john@example.com",
        # Out of scope
        "What is the weather today?",
        "How to cook pasta?",
    ]
    for q in test_queries:
        print("\n" + "=" * 80)
        print(f"Q: {q}")
        r = bot.answer(q)
        print(f"Intent: {r['intent']}  | Route: {r['route']}  | Rule: {r['rule_triggered']}")
        print(f"Answer:\n{r['answer']}")
        if r['citation_url']:
            print(f"Citation: {r['citation_url']}")
            print(f"  Title: {r['citation_title']}")
        if r['retrieved_chunk_ids']:
            print(f"Chunks: {r['retrieved_chunk_ids'][:3]}...")
