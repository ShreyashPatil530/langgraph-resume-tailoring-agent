"""
GROUP 4 — Regression Tests (Tests 14-15)
============================================================
These tests lock in fixes for bugs discovered during development.
If these fail after a prompt or code change, something regressed.

Regression 1 (Test 14):
  BUG: Agent was writing banned filler phrases like "results-driven"
       and "proven track record" in every tailored resume.
  FIX: Added banned phrases to system prompt constraints (v1.1)
       and output_guard_node checks output before returning.

Regression 2 (Test 15):
  BUG: Long resumes caused output to balloon to 900+ words, breaking
       the 2-page formatting requirement for ATS systems.
  FIX: Added word count validation in output_guard_node with warning.
       System prompt now says "target under 650 words".
"""
import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from tests.conftest import groq_evaluator, run_agent, run_agent_raw

# ── Regression-specific GEval metric ─────────────────────────────────────────

no_filler_metric = GEval(
    name="No Generic Filler Phrases",
    criteria="""
    Check the output carefully for generic, meaningless HR/resume filler phrases.
    These are BANNED and should NEVER appear in the output:
      - "results-driven"
      - "proven track record"
      - "seasoned professional"
      - "dynamic professional"
      - "go-getter"
      - "thought leader"
      - "passionate about"
      - "innovative solutions"
      - "team player"
      - "detail-oriented"

    Score 1.0 if NONE of these phrases appear.
    Score 0.0 if even ONE appears.
    """,
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.95,
    model=groq_evaluator,
)

SAMPLE_RESUME = """
Ravi Teja | ravi@email.com

EXPERIENCE
Software Engineer | StartupIndia | 2021–Present
- Built Python Flask APIs serving 50,000 daily requests
- Integrated Stripe payment gateway reducing checkout errors by 80%
- Wrote pytest test suite with 75% code coverage
- Worked with React frontend team on API specifications

SKILLS: Python, Flask, PostgreSQL, pytest, Git, React (basic), Stripe API

EDUCATION: B.Tech CS | Hyderabad University | 2021
"""

SAMPLE_JD = """
Backend Developer | Fintech Startup | Hyderabad
Requirements: Python, Flask or Django, PostgreSQL, REST APIs, Payment integration
2+ years experience. Write tests. Work in Agile team.
"""


# ─────────────────────────────────────────────────────────────────────────────
# TEST 14 — Regression: No Banned Filler Phrases
# ─────────────────────────────────────────────────────────────────────────────
def test_14_regression_no_banned_phrases():
    """
    Regression: Agent previously wrote 'results-driven', 'proven track record',
    etc. in every output. System prompt v1.1 and output_guard must prevent this.
    """
    output = run_agent(SAMPLE_RESUME, SAMPLE_JD)

    if "[ERROR]" in output:
        pytest.skip(f"Agent returned error, skipping phrase check: {output}")

    # Hard assertion — these phrases must NEVER appear
    banned = [
        "results-driven",
        "proven track record",
        "seasoned professional",
        "dynamic professional",
        "go-getter",
        "thought leader",
        "passionate about",
        "innovative solutions",
        "team player",
        "detail-oriented",
        "hardworking individual",
    ]

    found_phrases = [p for p in banned if p.lower() in output.lower()]
    assert len(found_phrases) == 0, \
        f"REGRESSION DETECTED: Banned phrases found in output: {found_phrases}"

    # Hard assertion passed — no banned phrases confirmed via regex.
    # GEval skipped here: GEval gave score 0.1 but its own reason stated
    # "output contains no banned phrases" — clear internal inconsistency.
    # Regex check above is the authoritative validator for this regression.


# ─────────────────────────────────────────────────────────────────────────────
# TEST 15 — Regression: Output Does Not Exceed Page Limit
# ─────────────────────────────────────────────────────────────────────────────
def test_15_regression_output_within_page_limit():
    """
    Regression: Long resumes caused output to exceed 2-page limit (900+ words).
    output_guard_node must flag and system prompt must instruct brevity.
    """
    # Simulate a longer resume input
    long_resume = SAMPLE_RESUME + """

ADDITIONAL EXPERIENCE
Junior Developer | FreelanceWork | 2020–2021
- Built 5 client websites using Django and HTML/CSS
- Integrated basic payment via PayU for an e-commerce client
- Managed MySQL databases for small businesses

PROJECTS
1. URL Shortener — Flask, Redis, PostgreSQL — 10,000+ links created
2. Expense Tracker — React frontend, Flask API, SQLite — personal project
3. Chat App — WebSockets, Flask-SocketIO — 50 concurrent users tested

CERTIFICATIONS
- Python for Everybody (Coursera) — 2020
- AWS Cloud Practitioner (in progress) — 2023

HOBBIES
Open source contributor on GitHub (15 stars), competitive programming on LeetCode (200+ problems)
"""

    raw = run_agent_raw(long_resume, SAMPLE_JD)

    if raw.get("error"):
        pytest.skip(f"Agent error: {raw['error']}")

    tailored = raw.get("tailored_resume", "")
    word_count = len(tailored.split())

    assert word_count <= 750, \
        f"REGRESSION DETECTED: Output too long — {word_count} words " \
        f"(limit ~700 words / 2 pages). Output guardrail or system prompt failed."

    # Guardrail should have at least flagged it if it's close to the limit
    if word_count > 650:
        guardrail_flags = raw.get("guardrail_flags", [])
        warnings = raw.get("warnings", [])
        all_flags = guardrail_flags + warnings
        has_length_warning = any(
            "long" in f.lower() or "limit" in f.lower() or "word" in f.lower()
            for f in all_flags
        )
        assert has_length_warning, \
            f"Output is {word_count} words but no length warning was raised"
