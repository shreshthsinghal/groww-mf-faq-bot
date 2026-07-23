"""
Fact extractor for Groww MF FAQ bot.

Extracts specific factual values from retrieved chunks using regex patterns.
This is deterministic, instant, and can't hallucinate - better than an LLM
for fact extraction from structured disclosure documents.

Each extractor returns a clean 1-2 sentence answer, or None if the fact
can't be found in the provided text.
"""
import re


def extract_expense_ratio(query, retrieved):
    """Extract expense ratio value."""
    for chunk in retrieved:
        text = chunk["text"]
        # Pattern 1: "Expense ratio: 2.42%" or "Expense ratio 2.42%"
        m = re.search(r"(?:expense\s*ratio|TER)[\s:]*(\d+\.?\d*)\s*%", text, re.I)
        if m:
            val = m.group(1)
            # Check if GST is mentioned
            gst = "inclusive of GST" in text.lower() or "incl.*GST" in text.lower()
            gst_text = " inclusive of GST" if gst else ""
            return f"The expense ratio is {val}%{gst_text}."
    return None


def extract_exit_load(query, retrieved):
    """Extract exit load value."""
    for chunk in retrieved:
        text = chunk["text"]
        text_lower = text.lower()
        # Pattern 1: "Exit load: Nil" or "Exit load Nil"
        if re.search(r"exit\s*load[\s:]*nil", text, re.I):
            return "The exit load is Nil (no exit load)."
        # Pattern 2: "Exit load of 1%, if redeemed within 7 days"
        m = re.search(r"exit\s*load\s*(?:of\s*)?(\d+\.?\d*)\s*%,?\s*(?:if\s*)?redeem(?:ed)?\s*(?:within|in)\s*(\d+)\s*days?", text, re.I)
        if m:
            pct, days = m.group(1), m.group(2)
            return f"The exit load is {pct}% if redeemed within {days} days, and Nil thereafter."
        # Pattern 3: "1% if redeemed/switched out within 7 Days"
        m = re.search(r"(\d+\.?\d*)\s*%\s*if\s*redeemed?/?\s*switched?\s*out\s*within\s*(\d+)\s*days?", text, re.I)
        if m:
            pct, days = m.group(1), m.group(2)
            return f"The exit load is {pct}% if redeemed within {days} days, and Nil thereafter."
        # Pattern 4: "Exit load: NIL" (from SID)
        if re.search(r"exit\s*load[\s:]*NIL", text):
            return "The exit load is Nil (no exit load)."
    return None


def extract_minimum_sip(query, retrieved):
    """Extract minimum SIP amount."""
    for chunk in retrieved:
        text = chunk["text"]
        # Pattern 1: "Minimum SIP Investment is set to Rs.500" or "Minimum SIP is Rs.500"
        m = re.search(r"minimum\s*SIP\s*(?:investment\s*)?(?:is\s*)?(?:set\s*to\s*)?(?:Rs\.?\s*|₹)\s*(\d+(?:,\d+)*)", text, re.I)
        if m:
            val = m.group(1).replace(",", "")
            return f"The minimum SIP amount is Rs. {val}."
        # Pattern 2: "Min. for SIP" followed by amount
        m = re.search(r"min\.?\s*for\s*SIP[\s:]*Rs\.?\s*(\d+(?:,\d+)*)", text, re.I)
        if m:
            val = m.group(1).replace(",", "")
            return f"The minimum SIP amount is Rs. {val}."
        # Pattern 3: "Minimum SIP Installment" + amount
        m = re.search(r"minimum\s*SIP\s*(?:installment|amount)[\s:]*Rs\.?\s*(\d+(?:,\d+)*)", text, re.I)
        if m:
            val = m.group(1).replace(",", "")
            return f"The minimum SIP amount is Rs. {val}."
        # Pattern 4: "Minimum SIP Amount" + "Rs. 500" (from KIM)
        m = re.search(r"minimum\s*SIP\s*amount[\s:]*Rs\.?\s*(\d+(?:,\d+)*)", text, re.I)
        if m:
            val = m.group(1).replace(",", "")
            return f"The minimum SIP amount is Rs. {val}."
    return None


def extract_lockin(query, retrieved):
    """Extract lock-in period."""
    for chunk in retrieved:
        text = chunk["text"]
        # Pattern 1: "lock-in period of three years" or "lock in period of 3 years"
        m = re.search(r"lock[\s-]?in\s*period\s*(?:of\s*)?(?:is\s*)?(three|3)\s*years?", text, re.I)
        if m:
            return "The lock-in period is 3 years from the date of allotment."
        # Pattern 2: "lock in period of three years has elapsed"
        m = re.search(r"lock[\s-]?in\s*period\s*of\s*(three|3)\s*years?\s*has\s*elapsed", text, re.I)
        if m:
            return "The lock-in period is 3 years from the date of allotment."
        # Pattern 3: "locked for 3 years"
        m = re.search(r"locked?\s*(?:for|in)\s*(three|3)\s*years?", text, re.I)
        if m:
            return "The lock-in period is 3 years from the date of allotment."
    return None


def extract_riskometer(query, retrieved):
    """Extract riskometer rating."""
    risk_levels = [
        "Very High Risk",
        "Moderately High Risk",
        "High Risk",
        "Moderate Risk",
        "Low to Moderate Risk",
        "Low Risk",
    ]
    for chunk in retrieved:
        text = chunk["text"]
        text_lower = text.lower()
        # Look for "Risk-o-meter is at Very High Risk" or similar
        for level in risk_levels:
            level_lower = level.lower()
            # Pattern: "Risk-o-meter is at Very High Risk"
            if re.search(r"risk[\s-]?o[\s-]?meter\s*(?:is\s*)?(?:at\s*)?" + re.escape(level_lower), text_lower):
                return f"The riskometer rating is {level}."
            # Pattern: "rated Very High risk"
            if re.search(r"rated\s+" + re.escape(level_lower), text_lower):
                return f"The riskometer rating is {level}."
            # Pattern: "Very High Risk" as a standalone label
            if level_lower in text_lower and "riskometer" in text_lower:
                return f"The riskometer rating is {level}."
    return None


def extract_benchmark(query, retrieved):
    """Extract benchmark index."""
    for chunk in retrieved:
        text = chunk["text"]
        # Pattern 1: "Scheme Benchmark - NIFTY100 - TRI" (capture until 'Additional' or end)
        m = re.search(r"scheme\s*benchmark\s*[-:]\s*(NIFTY[\w\s\-]+?)(?:\s+additional|\s*$)", text, re.I)
        if m:
            val = m.group(1).strip().rstrip(" -")
            return f"The benchmark is {val}."
        # Pattern 2: "Benchmark: Nifty 50 Index - TRI"
        m = re.search(r"benchmark\s*[:\s]+(Nifty\s*[\d]+\s*Index\s*-\s*TRI|NIFTY\s*\d+\s*-?\s*TRI|NIFTY\s*500\s*TRI|Nifty\s*Smallcap\s*\d+\s*Index)", text, re.I)
        if m:
            val = m.group(1).strip()
            return f"The benchmark is {val}."
        # Pattern 3: "Fund Name Benchmark ... NIFTY 100-TRI" (from factsheet table)
        m = re.search(r"benchmark\s+([A-Z][A-Z0-9\s\-]+?TRI)", text)
        if m:
            val = m.group(1).strip().rstrip(" -")
            if 5 < len(val) < 60:
                return f"The benchmark is {val}."
        # Pattern 4: "Benchmark: NIFTY 500 TRI" (from Groww Value Fund)
        m = re.search(r"benchmark[:\s]+(NIFTY\s+\d+\s*TRI)", text, re.I)
        if m:
            val = m.group(1).strip()
            return f"The benchmark is {val}."
    return None


def extract_statement_steps(query, retrieved):
    """Extract statement download steps."""
    # For statement queries, return the most relevant help article content
    for chunk in retrieved:
        text = chunk["text"]
        # Look for step-by-step instructions
        if "capital gains" in text.lower() and ("download" in text.lower() or "report" in text.lower()):
            # Extract the relevant portion
            sents = re.split(r"(?<=[.!?])\s+", text.strip())
            # Take up to 3 sentences that mention key steps
            relevant = [s for s in sents if any(kw in s.lower() for kw in
                        ["download", "report", "statement", "tax", "capital gains", "reports", "profile"])]
            if relevant:
                return " ".join(relevant[:3])
        if "CAS" in text and ("generate" in text.lower() or "download" in text.lower()):
            sents = re.split(r"(?<=[.!?])\s+", text.strip())
            relevant = [s for s in sents if any(kw in s.lower() for kw in
                        ["cas", "statement", "cams", "email", "download"])]
            if relevant:
                return " ".join(relevant[:3])
    return None


# ---------------------------------------------------------------------------
# Main extraction dispatcher
# ---------------------------------------------------------------------------
EXTRACTORS = {
    "factual_expense_ratio": extract_expense_ratio,
    "factual_exit_load": extract_exit_load,
    "factual_min_sip": extract_minimum_sip,
    "factual_lockin": extract_lockin,
    "factual_riskometer": extract_riskometer,
    "factual_benchmark": extract_benchmark,
    "factual_statement": extract_statement_steps,
}


def extract_fact(intent, query, retrieved):
    """Main entry point. Returns extracted answer string, or None if no fact found."""
    extractor = EXTRACTORS.get(intent)
    if not extractor:
        return None
    try:
        return extractor(query, retrieved)
    except Exception:
        return None
