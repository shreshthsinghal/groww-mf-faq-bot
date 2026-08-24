# Groww MF Facts

Fact-only FAQ assistant for Groww Mutual Fund schemes. Answers questions about expense ratio, exit load, minimum SIP, lock-in, riskometer, benchmark, and statement downloads. Every answer cites one official public source. No advice, no performance figures, no PII accepted.

Live at: https://web-production-a5d7a.up.railway.app

## What this is

A reference tool, not an advisor. The UI is closer to a docs search than a fintech app. Every answer comes from official public sources (AMC website, SEBI, AMFI) and cites that source. The citation card appears with the same shape after every answer, so the repetition itself becomes the trust signal.

## Scope

7 schemes from Groww Asset Management Ltd:

- Groww Large Cap Fund
- Groww Value Fund
- Groww Small Cap Fund
- Groww ELSS Tax Saver Fund
- Groww Nifty 50 Index Fund
- Groww Liquid Fund
- Groww Overnight Fund

7 fact types: expense ratio, exit load, minimum SIP, ELSS lock-in, riskometer, benchmark, statement download.

10 definitional intents: What is expense ratio? What is SIP? What is NAV? What is ELSS? What is a mutual fund? What is lock-in? What is riskometer? What is benchmark? What is exit load? What is direct vs regular plan?

## What it refuses

- Buy / sell / hold advice (Should I buy? Which is best?)
- Performance figures, returns, CAGR, XIRR, NAV history
- PII in queries (PAN, Aadhaar, OTP, email, phone, account numbers)

Refusals are polite, brief, and include one educational link.

## Architecture

```
User query
    |
    v
[1] PII regex gate (PAN / Aadhaar / OTP / Email / Phone / Acct / CVV)
    |
    v
[2] Performance regex gate (CAGR / XIRR / returns / NAV / etc.)
    |
    v
[3] LinearSVC intent classifier (21 classes, 94% accuracy)
    |
    +-- factual_*      --> [4] Retrieval --> [5] LLM answer with citation
    +-- define_*       --> pre-written answer (instant, no LLM)
    +-- refusal_*      --> canned message + educational link
    +-- out_of_scope   --> polite redirect
```

Retrieval is TF-IDF cosine similarity with a literal-phrase injection pass so chunks containing the fact term + scheme name (in chunk text or page metadata) are never missed. A value-boost re-ranker prioritizes chunks that contain actual values (percentages, rupee amounts, NIL, year counts).

The LLM is called via OpenRouter using Google Gemma 4-26B (free tier). A strict system prompt enforces 2-3 sentence answers, one citation, "Last updated from sources:" footer, no advice, no performance claims. If the LLM fails, fallback providers (OpenAI, Z.AI, Groq) are tried in sequence.

## Response times

- Definitional questions (What is X?): 1-3ms (pre-written, no LLM)
- Refusals (advice, PII, performance): under 1ms (no LLM)
- First-time scheme queries: 5-10s (LLM generation)
- Repeat queries: under 1ms (in-memory cache)

## Project structure

```
.
+- api/
|  +- answer.py          # Vercel serverless function (legacy)
+- chatbot_engine.py     # Engine: hard rules + classifier + retrieval + LLM
+- server.py             # Flask server for Railway
+- models/               # Trained LinearSVC + TF-IDF vectorizer + label encoder
+- index/                # TF-IDF chunk index (~7.5 MB)
+- templates/
|  +- index.html         # Chat UI (B&W interactive theme)
+- static/
|  +- styles.css         # Token system + all components
|  +- app.js             # Front-end interaction (no framework)
|  +- logo.svg           # Closure-based mark
|  +- favicon.svg
+- requirements.txt
+- pyproject.toml
```

## Corpus

30 public pages scraped from:

- growwmf.in (AMC primary docs: SID, KIM, factsheets)
- groww.in (scheme pages, topic explainers, help articles)
- investor.sebi.gov.in (regulator explainers)
- sebi.gov.in (regulatory FAQ PDF)

Total: 1.48M characters of clean text, chunked into 3,699 passages of about 600 characters each.

## Model training

The intent classifier was trained on 525 labeled queries across 21 classes:

- 7 scheme-specific factual intents (expense ratio, exit load, min SIP, lock-in, riskometer, benchmark, statement)
- 10 definitional intents (What is X?)
- 4 refusal / out-of-scope intents

LinearSVC won with 94.29% test accuracy and 0.942 macro F1. Trained on the full dataset and saved as a pickle artifact.

## Product guidelines

These are enforced at the architecture level, not as an afterthought:

1. Facts-only, no investment advice. SEBI regulates investment advice in India. The chatbot refuses all advice-shaped questions and redirects to SEBI educational resources.

2. No performance figures. Returns, CAGR, XIRR, and NAV history change daily and can mislead investors. The chatbot links to the official factsheet instead.

3. No PII accepted or stored. The chatbot does not need personal data to answer factual questions. PAN, Aadhaar, OTP, email, phone, and account numbers are rejected at the regex gate before any processing.

4. Public sources only. Approved citation domains: growwmf.in, groww.in, investor.sebi.gov.in, sebi.gov.in, amfiindia.com. Third-party blogs are in the corpus for retrieval context but never cited in answers.

5. Every answer has exactly one citation link. The user can verify any answer against the original document. The citation card appears identically after every answer.

6. Maximum 3 sentences per answer. Forces precision. The chatbot is a reference tool, not a chatbot that rambles.

7. "Last updated from sources: [date]" footer on every answer. Transparency about data freshness. Mutual fund facts change; the user knows when the source was last checked.

## Design

Pure black and white. No color accents. Trust and emphasis come from weight, contrast, and motion instead of color.

- Logo: Gestalt Closure principle. An unfinished document stroke that the eye completes into a chat bubble. Meaning: "a document is speaking."
- Typography: Inter for headlines and body, JetBrains Mono for data and labels.
- Interactive text effects: word-by-word headline reveal, magnetic buttons, fill-up hover inversions on chips, cursor-following spotlight, scroll-triggered animations.
- Custom cursor with mix-blend-mode: difference.
- prefers-reduced-motion fully respected.

## Deployment

The app is deployed on Railway. The GitHub repo is connected and auto-deploys on push.

The /api/answer endpoint is a Flask route. The server loads the 7.5 MB index and classifier at startup. Cold start takes about 2-3 seconds; subsequent calls within a warm instance are fast.

Environment variables:

- OPENROUTER_API_KEY (primary LLM provider)
- OPENAI_API_KEY (fallback)
- GROQ_API_KEY (fallback)
- ZAI_BASE_URL, ZAI_API_KEY, ZAI_TOKEN, ZAI_CHAT_ID, ZAI_USER_ID (local dev fallback)

## Local development

```bash
pip install -r requirements.txt
python server.py
```

The server runs on port 5050 by default, or the PORT environment variable on Railway.

## Limitations

- Only 7 Groww MF schemes covered. Cannot answer about other AMCs.
- Cannot give investment advice. This is by design.
- Cannot provide returns or performance. Links to factsheet instead.
- Cannot accept personal information. PAN, Aadhaar, OTP, email, phone are rejected.
- First-time scheme queries take 5-10 seconds for LLM generation. Definitional and repeat queries are instant.
- Data freshness depends on source pages. The corpus was scraped as of July 2026.
- Free-tier LLM (OpenRouter / Google Gemma). May hit rate limits under heavy usage.
- English only.

## Tech stack

- Python 3.12, Flask
- scikit-learn (LinearSVC, TF-IDF)
- OpenRouter (Google Gemma 4-26B, free tier)
- Vanilla HTML / CSS / JS (no framework)
- Railway (deployment)
- GitHub (version control)

## Disclaimer

This is a research and reference tool. Not affiliated with Groww, SEBI, or AMFI. All facts come from publicly available official documents. Always verify against the official source before making any investment decision.
