from typing import Optional, List
from typing_extensions import TypedDict


class AgentState(TypedDict):
    # ── Inputs ────────────────────────────────────────────────────────────────
    resume: str
    job_description: str

    # ── Intermediate processing ───────────────────────────────────────────────
    jd_analysis: Optional[dict]

    # ── Outputs ───────────────────────────────────────────────────────────────
    tailored_resume: Optional[str]
    match_score: Optional[int]
    changes_made: Optional[List[str]]
    warnings: List[str]

    # ── Control flow ──────────────────────────────────────────────────────────
    error: Optional[str]
    step_count: int
    token_count: int
    guardrail_flags: List[str]
    run_id: str
