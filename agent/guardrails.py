"""
Three layers of guardrails:
  Input  — blocks injection, validates length, detects PII
  Output — bans filler phrases, redacts PII, validates score range / word count
  Action — URL allowlist, step/token cost limits
"""
import re
from typing import List, Tuple
from urllib.parse import urlparse

# ── Input Guard: Prompt Injection Patterns ────────────────────────────────────
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior)?\s*(instructions?|rules?|prompt)",
    r"you\s+are\s+now\s+(?!recruform)",
    r"forget\s+(everything|all|your\s+instructions?)",
    r"(reveal|show|print|output|repeat|display)\s+(your\s+)?(system\s+)?prompt",
    r"disregard\s+(all\s+)?(previous\s+)?(instructions?|rules?)",
    r"jailbreak",
    r"act\s+as\s+(if\s+)?(you\s+are\s+)?(?!a\s+resume)",
    r"new\s+(persona|identity|character|role)\s*:",
    r"bypass\s+.*?(filter|guard|rule|constraint)",
    r"DAN\s+mode",
    r"pretend\s+(you\s+(have\s+no|are\s+free|can\s+do))",
]

# ── Output Guard: Banned Filler Phrases ──────────────────────────────────────
BANNED_PHRASES = [
    "results-driven",
    "proven track record",
    "seasoned professional",
    "dynamic professional",
    "synergy",
    "team player",
    "go-getter",
    "thought leader",
    "passionate about",
    "innovative solutions",
    "leverage",
    "paradigm",
    "detail-oriented",
    "hardworking individual",
    "self-starter",
]

# ── Output Guard: PII Patterns (for redaction) ────────────────────────────────
_PII_PATTERNS = {
    "SSN":         r"\b\d{3}-\d{2}-\d{4}\b",
    "CreditCard":  r"\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b",
    "BankAccount": r"\bbank\s*account\s*[:#]?\s*\d{6,}\b",
    "Passport":    r"\b[A-Z]{1,2}\d{6,9}\b",
}

# ── Action Guard: Allowed Domains ─────────────────────────────────────────────
ALLOWED_DOMAINS = {
    "linkedin.com", "indeed.com", "glassdoor.com",
    "naukri.com", "workday.com", "lever.co",
    "greenhouse.io", "bamboohr.com", "instahyre.com",
}

# ── Action Guard: Cost Limits ─────────────────────────────────────────────────
MAX_STEPS = 50
MAX_TOKENS = 100_000
MAX_INPUT_CHARS = 12_000
MIN_INPUT_CHARS = 10
MAX_OUTPUT_WORDS = 700   # ~2 pages


# ─────────────────────────────────────────────────────────────────────────────
# INPUT GUARDS
# ─────────────────────────────────────────────────────────────────────────────

def detect_prompt_injection(text: str) -> Tuple[bool, str]:
    """Return (True, reason) if prompt injection is detected."""
    lower = text.lower()
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, lower):
            return True, f"Prompt injection pattern matched: '{pattern}'"
    return False, ""


def validate_input_length(label: str, text: str) -> Tuple[bool, str]:
    """Return (False, reason) if input length is out of bounds."""
    n = len(text)
    if n < MIN_INPUT_CHARS:
        return False, f"{label} too short: {n} chars (min {MIN_INPUT_CHARS})"
    if n > MAX_INPUT_CHARS:
        return False, f"{label} too long: {n} chars (max {MAX_INPUT_CHARS})"
    return True, ""


def detect_pii_in_input(text: str) -> Tuple[bool, str]:
    """Return (True, type) if sensitive PII is in the input."""
    for pii_type, pattern in _PII_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            return True, pii_type
    return False, ""


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT GUARDS
# ─────────────────────────────────────────────────────────────────────────────

def detect_banned_phrases(text: str) -> List[str]:
    """Return list of banned filler phrases found in output."""
    lower = text.lower()
    return [p for p in BANNED_PHRASES if p in lower]


def redact_pii_from_output(text: str) -> str:
    """Replace PII patterns in output with [TYPE REDACTED] placeholders."""
    for pii_type, pattern in _PII_PATTERNS.items():
        text = re.sub(pattern, f"[{pii_type} REDACTED]", text, flags=re.IGNORECASE)
    return text


def validate_output_word_count(text: str) -> Tuple[bool, str]:
    """Return (False, reason) if output exceeds the page limit."""
    count = len(text.split())
    if count > MAX_OUTPUT_WORDS:
        return False, f"Output too long: {count} words (max {MAX_OUTPUT_WORDS})"
    return True, ""


def validate_match_score(score) -> Tuple[bool, str]:
    """Return (False, reason) if match score is not a valid integer 0-100."""
    if not isinstance(score, int):
        return False, f"match_score must be int, got {type(score).__name__}"
    if not (0 <= score <= 100):
        return False, f"match_score out of range: {score} (must be 0-100)"
    return True, ""


# ─────────────────────────────────────────────────────────────────────────────
# ACTION GUARDS
# ─────────────────────────────────────────────────────────────────────────────

def validate_url(url: str) -> Tuple[bool, str]:
    """Return (False, reason) if URL domain is not in the allowlist."""
    try:
        domain = urlparse(url).netloc.replace("www.", "").split(":")[0]
        if domain in ALLOWED_DOMAINS:
            return True, ""
        return False, f"Domain not in allowlist: '{domain}'"
    except Exception as exc:
        return False, f"Invalid URL: {exc}"


def check_cost_limits(step_count: int, token_count: int) -> Tuple[bool, str]:
    """Return (False, reason) if agent has exceeded step or token budgets."""
    if step_count > MAX_STEPS:
        return False, f"Step limit exceeded: {step_count}/{MAX_STEPS}"
    if token_count > MAX_TOKENS:
        return False, f"Token limit exceeded: {token_count}/{MAX_TOKENS}"
    return True, ""
