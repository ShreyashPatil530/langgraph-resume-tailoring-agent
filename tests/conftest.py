"""
Shared fixtures and helpers for the DeepEval test suite.

OpenRouterEvaluator — uses OpenRouter (openai/gpt-oss-20b:free) as the
                      LLM-judge. No OpenAI key needed, uses OPENROUTER_API_KEY.

run_agent()         — runs the full LangGraph pipeline and returns a
                      single string for DeepEval's actual_output field.
"""
import os
import uuid
from typing import Optional, Tuple

import pytest
from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# Custom OpenRouter evaluator for DeepEval (replaces OpenAI default)
# ─────────────────────────────────────────────────────────────────────────────

from deepeval.models.base_model import DeepEvalBaseLLM


class OpenRouterEvaluator(DeepEvalBaseLLM):
    """LLM-judge for DeepEval powered by OpenRouter — no OpenAI key needed."""

    def __init__(self):
        self._client = None

    def load_model(self):
        if self._client is None:
            from langchain_openai import ChatOpenAI
            self._client = ChatOpenAI(
                model=os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free"),
                api_key=os.getenv("OPENROUTER_API_KEY"),
                base_url="https://openrouter.ai/api/v1",
                temperature=0,
                default_headers={"HTTP-Referer": "http://localhost"},
            )
        return self._client

    def generate(self, prompt: str, schema=None) -> Tuple[str, float]:
        model = self.load_model()
        response = model.invoke(prompt)
        return response.content, 0.0

    async def a_generate(self, prompt: str, schema=None) -> Tuple[str, float]:
        model = self.load_model()
        response = await model.ainvoke(prompt)
        return response.content, 0.0

    def get_model_name(self) -> str:
        return f"openrouter/{os.getenv('OPENROUTER_MODEL', 'openai/gpt-oss-20b:free')}"


# Singleton — import this in every test file
groq_evaluator = OpenRouterEvaluator()   # kept name for backward compat


# ─────────────────────────────────────────────────────────────────────────────
# Agent runner helper
# ─────────────────────────────────────────────────────────────────────────────

def _initial_state(resume: str, jd: str) -> dict:
    return {
        "resume":           resume,
        "job_description":  jd,
        "jd_analysis":      None,
        "tailored_resume":  None,
        "match_score":      None,
        "changes_made":     [],
        "warnings":         [],
        "error":            None,
        "step_count":       0,
        "token_count":      0,
        "guardrail_flags":  [],
        "run_id":           str(uuid.uuid4()),
    }


def run_agent(resume: str, job_description: str) -> str:
    """
    Run the full LangGraph pipeline and return a single string for DeepEval.
    Returns '[ERROR] <reason>' string if the agent hits an error/guard.
    """
    from agent.graph import build_graph

    graph = build_graph()
    state = _initial_state(resume, job_description)
    result = graph.invoke(state)

    if result.get("error"):
        return f"[ERROR] {result['error']}"

    lines = [
        f"TAILORED RESUME:\n{result.get('tailored_resume', '')}",
        f"MATCH SCORE: {result.get('match_score', 0)}/100",
        f"CHANGES: {'; '.join(result.get('changes_made') or [])}",
        f"WARNINGS: {'; '.join(result.get('warnings') or [])}",
    ]
    return "\n\n".join(lines)


def run_agent_raw(resume: str, job_description: str) -> dict:
    """Return the raw final state dict (for assertions on specific fields)."""
    from agent.graph import build_graph

    graph = build_graph()
    return graph.invoke(_initial_state(resume, job_description))
