"""
Structured JSON logger for every agent run.

Each run is written as a single JSON line to logs/agent_runs.jsonl.
LangSmith auto-captures traces when LANGCHAIN_TRACING_V2=true is set
in the environment — this logger is the local backup.
"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Log directory ─────────────────────────────────────────────────────────────
_LOG_DIR = Path("logs")
_LOG_DIR.mkdir(exist_ok=True)
_LOG_FILE = _LOG_DIR / "agent_runs.jsonl"

# Write raw JSON lines (no timestamp prefix from logging formatter)
_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(message)s"))

_console = logging.StreamHandler()
_console.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

logger = logging.getLogger("recruform.agent")
logger.setLevel(logging.INFO)
logger.addHandler(_handler)
logger.addHandler(_console)
logger.propagate = False


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def log_agent_run(
    agent_name: str,
    run_id: str,
    input_preview: str,
    output_preview: str,
    step_count: int,
    token_count: int,
    match_score: Optional[int],
    guardrail_flags: List[str],
    warnings: List[str],
    success: bool,
    duration_ms: Optional[float] = None,
) -> None:
    """Write one structured JSON line per agent run."""
    # Groq pricing: ~$0.59 per 1M tokens (versatile tier, approximate)
    cost_usd = round(token_count * 0.00000059, 8)

    record: Dict[str, Any] = {
        "timestamp":           datetime.now().isoformat(),
        "run_id":              run_id,
        "agent":               agent_name,
        "success":             success,
        "match_score":         match_score,
        "step_count":          step_count,
        "token_count":         token_count,
        "cost_estimate_usd":   cost_usd,
        "duration_ms":         duration_ms,
        "guardrail_flags":     guardrail_flags,
        "guardrail_flag_count": len(guardrail_flags),
        "warnings":            warnings,
        "warning_count":       len(warnings),
        "input_preview":       input_preview[:200],
        "output_preview":      output_preview[:200],
    }

    logger.info(json.dumps(record, ensure_ascii=False))


def get_run_stats() -> Dict[str, Any]:
    """
    Parse logs/agent_runs.jsonl and return summary statistics.
    Call this to identify insights from monitoring data.
    """
    if not _LOG_FILE.exists():
        return {"error": "No log file found — run the agent first"}

    runs: List[Dict] = []
    with open(_LOG_FILE, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    runs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if not runs:
        return {"total_runs": 0}

    successful = [r for r in runs if r.get("success")]
    failed     = [r for r in runs if not r.get("success")]
    scores     = [r["match_score"] for r in successful if r.get("match_score") is not None]
    tokens_all = [r.get("token_count", 0) for r in runs]
    costs_all  = [r.get("cost_estimate_usd", 0) for r in runs]
    steps_all  = [r.get("step_count", 0) for r in runs]
    flagged    = [r for r in runs if r.get("guardrail_flag_count", 0) > 0]

    avg = lambda lst: round(sum(lst) / len(lst), 2) if lst else None

    return {
        "total_runs":          len(runs),
        "successful_runs":     len(successful),
        "failed_runs":         len(failed),
        "success_rate_pct":    round(len(successful) / len(runs) * 100, 1),
        "avg_match_score":     avg(scores),
        "min_match_score":     min(scores) if scores else None,
        "max_match_score":     max(scores) if scores else None,
        "avg_token_count":     avg(tokens_all),
        "total_tokens":        sum(tokens_all),
        "total_cost_usd":      round(sum(costs_all), 6),
        "avg_steps":           avg(steps_all),
        "runs_with_guardrail_flags": len(flagged),
        "guardrail_flag_rate_pct": round(len(flagged) / len(runs) * 100, 1),
        "monthly_cost_projection_usd": round(sum(costs_all) / len(runs) * 30 * 100, 2),
    }


def print_stats() -> None:
    """Pretty-print monitoring stats to the console."""
    stats = get_run_stats()
    print("\n" + "=" * 55)
    print("  RECRUFORM AGENT — MONITORING DASHBOARD")
    print("=" * 55)
    for key, val in stats.items():
        label = key.replace("_", " ").title()
        print(f"  {label:<38} {val}")
    print("=" * 55 + "\n")
