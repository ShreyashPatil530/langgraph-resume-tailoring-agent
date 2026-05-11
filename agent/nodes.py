"""
LangGraph nodes for the Resume Tailoring Agent.

Flow:
  input_guard → analyze_jd → tailor_resume → output_guard → cost_guard
  Any node sets state["error"] to short-circuit to END.
"""
import json
import os
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agent.guardrails import (
    check_cost_limits,
    detect_banned_phrases,
    detect_pii_in_input,
    detect_prompt_injection,
    redact_pii_from_output,
    validate_input_length,
    validate_match_score,
    validate_output_word_count,
)
from agent.state import AgentState
from monitoring.logger import log_agent_run
from prompts.v1_1 import RESUME_TAILOR_V1_1 as SYSTEM_PROMPT


def _llm() -> ChatOpenAI:
    """OpenRouter via OpenAI-compatible endpoint — free tier, no cost."""
    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        temperature=0.1,
        max_tokens=2000,
        default_headers={"HTTP-Referer": "http://localhost"},
    )


def _parse_json(text: str) -> dict:
    """Try direct parse, then regex-extract JSON block from LLM response."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    raise ValueError(f"Cannot extract JSON from response: {text[:300]}")


def _token_estimate(*texts: str) -> int:
    """Rough token estimate: ~0.75 words per token."""
    total_words = sum(len(t.split()) for t in texts)
    return int(total_words / 0.75)


# ─────────────────────────────────────────────────────────────────────────────
# NODE 1 — Input Guard
# ─────────────────────────────────────────────────────────────────────────────
def input_guard_node(state: AgentState) -> AgentState:
    """Validate and sanitize inputs before any LLM call."""
    flags: list[str] = []

    # Cost check first
    ok, msg = check_cost_limits(state["step_count"], state["token_count"])
    if not ok:
        return {**state, "error": msg}

    resume = state["resume"]
    jd = state["job_description"]

    # Length validation — resume
    ok, msg = validate_input_length("Resume", resume)
    if not ok:
        if len(resume) < 5:  # completely empty → hard stop
            return {**state, "error": f"Input rejected: {msg}"}
        flags.append(msg)  # too long → flag but continue

    # Length validation — JD
    ok, msg = validate_input_length("JD", jd)
    if not ok:
        flags.append(msg)

    # Prompt injection — resume
    injected, msg = detect_prompt_injection(resume)
    if injected:
        return {**state, "error": f"Security: {msg}"}

    # Prompt injection — JD
    injected, msg = detect_prompt_injection(jd)
    if injected:
        return {**state, "error": f"Security: {msg}"}

    # PII in resume (flag, don't block — resume legitimately has email/phone)
    has_pii, pii_type = detect_pii_in_input(resume)
    if has_pii:
        flags.append(f"Sensitive PII found in resume input: {pii_type}")

    return {
        **state,
        "step_count": state["step_count"] + 1,
        "guardrail_flags": state.get("guardrail_flags", []) + flags,
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 2 — Analyze JD
# ─────────────────────────────────────────────────────────────────────────────
def analyze_jd_node(state: AgentState) -> AgentState:
    """Call LLM to extract structured requirements from the job description."""
    prompt = f"""Analyze this job description and return ONLY a valid JSON object.

Job Description:
{state['job_description']}

Return exactly this structure (no extra text):
{{
  "required_skills": ["skill1", "skill2"],
  "preferred_skills": ["skill1", "skill2"],
  "key_responsibilities": ["responsibility1"],
  "ats_keywords": ["keyword1", "keyword2"],
  "seniority_level": "junior|mid|senior|lead",
  "industry": "tech|finance|healthcare|other",
  "years_required": 0
}}"""

    try:
        llm = _llm()
        response = llm.invoke([HumanMessage(content=prompt)])
        analysis = _parse_json(response.content)
        tokens = _token_estimate(prompt, response.content)

        return {
            **state,
            "jd_analysis": analysis,
            "step_count": state["step_count"] + 1,
            "token_count": state["token_count"] + tokens,
        }
    except Exception as exc:
        return {**state, "error": f"JD analysis failed: {exc}"}


# ─────────────────────────────────────────────────────────────────────────────
# NODE 3 — Tailor Resume
# ─────────────────────────────────────────────────────────────────────────────
def tailor_resume_node(state: AgentState) -> AgentState:
    """Call LLM with system prompt to produce the tailored resume JSON."""
    jd_info = json.dumps(state.get("jd_analysis") or {}, indent=2)

    user_msg = f"""Tailor this resume for the job description.

ORIGINAL RESUME:
{state['resume']}

JOB DESCRIPTION:
{state['job_description']}

JD ANALYSIS (use as reference):
{jd_info}

Return ONLY valid JSON — no markdown, no extra text."""

    try:
        llm = _llm()
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])
        output = _parse_json(response.content)
        tokens = _token_estimate(SYSTEM_PROMPT, user_msg, response.content)

        return {
            **state,
            "tailored_resume": output.get("tailored_resume", ""),
            "match_score": output.get("match_score", 0),
            "changes_made": output.get("changes_made", []),
            "warnings": (state.get("warnings") or []) + (output.get("warnings") or []),
            "step_count": state["step_count"] + 1,
            "token_count": state["token_count"] + tokens,
        }
    except Exception as exc:
        return {**state, "error": f"Resume tailoring failed: {exc}"}


# ─────────────────────────────────────────────────────────────────────────────
# NODE 4 — Output Guard
# ─────────────────────────────────────────────────────────────────────────────
def output_guard_node(state: AgentState) -> AgentState:
    """Validate and sanitize the LLM's tailored resume output."""
    flags: list[str] = []
    warnings = list(state.get("warnings") or [])
    tailored = state.get("tailored_resume") or ""

    if not tailored.strip():
        return {**state, "error": "Output guard: tailored_resume is empty"}

    # Redact any PII that leaked into the output
    cleaned = redact_pii_from_output(tailored)
    if cleaned != tailored:
        flags.append("PII redacted from tailored resume output")

    # Check for banned filler phrases
    banned = detect_banned_phrases(cleaned)
    if banned:
        flags.append(f"Banned phrases detected in output: {banned}")
        warnings.append(f"Output contains banned filler phrases: {banned}")

    # Validate match score
    score = state.get("match_score", 0)
    ok, msg = validate_match_score(score)
    if not ok:
        flags.append(msg)
        score = 0

    # Word count check (~2 page limit)
    ok, msg = validate_output_word_count(cleaned)
    if not ok:
        flags.append(msg)
        warnings.append(f"Resume may exceed 2-page limit: {msg}")

    return {
        **state,
        "tailored_resume": cleaned,
        "match_score": score,
        "warnings": warnings,
        "step_count": state["step_count"] + 1,
        "guardrail_flags": (state.get("guardrail_flags") or []) + flags,
    }


# ─────────────────────────────────────────────────────────────────────────────
# NODE 5 — Cost Guard + Logger
# ─────────────────────────────────────────────────────────────────────────────
def cost_guard_node(state: AgentState) -> AgentState:
    """Final cost check and structured run logging."""
    ok, msg = check_cost_limits(state["step_count"], state["token_count"])
    if not ok:
        return {**state, "error": f"Cost limit: {msg}"}

    log_agent_run(
        agent_name="resume_tailor_v1.1",
        run_id=state.get("run_id", "unknown"),
        input_preview=(state.get("resume") or "")[:200],
        output_preview=(state.get("tailored_resume") or "")[:200],
        step_count=state["step_count"],
        token_count=state["token_count"],
        match_score=state.get("match_score"),
        guardrail_flags=state.get("guardrail_flags") or [],
        warnings=state.get("warnings") or [],
        success=not bool(state.get("error")),
    )

    return {**state, "step_count": state["step_count"] + 1}
