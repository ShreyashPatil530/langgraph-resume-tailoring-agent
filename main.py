"""
Recruform - Day 9: Production-Ready Resume Tailoring Agent
==========================================================

INPUT  (aap yahan apna data daalte ho):
  input/resume.txt           <-- apna resume yahan paste karo
  input/job_description.txt  <-- jis job ke liye apply karna hai uska JD yahan

OUTPUT (agent yahan result save karta hai):
  output/tailored_resume.txt   <-- final tailored resume
  output/result_summary.txt    <-- match score, changes, warnings
  logs/agent_runs.jsonl        <-- monitoring data (har run ka record)

Run karo:
  python main.py

Tests run karo:
  deepeval test run tests/

Monitoring stats dekho:
  python -c "from monitoring.logger import print_stats; print_stats()"
"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agent.graph import build_graph
from monitoring.logger import print_stats

# ── Folders ───────────────────────────────────────────────────────────────────
INPUT_DIR  = Path("input")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Read input files
# ─────────────────────────────────────────────────────────────────────────────

def read_inputs() -> tuple[str, str]:
    """
    Read resume and job description from input/ folder.
    Returns (resume_text, jd_text)
    """
    resume_file = INPUT_DIR / "resume.txt"
    jd_file     = INPUT_DIR / "job_description.txt"

    if not resume_file.exists():
        raise FileNotFoundError(
            f"Resume file not found: {resume_file}\n"
            "Please create input/resume.txt and paste your resume there."
        )

    if not jd_file.exists():
        raise FileNotFoundError(
            f"JD file not found: {jd_file}\n"
            "Please create input/job_description.txt and paste the job description there."
        )

    resume = resume_file.read_text(encoding="utf-8").strip()
    jd     = jd_file.read_text(encoding="utf-8").strip()

    if len(resume) < 20:
        raise ValueError("resume.txt is too short. Please add your actual resume.")

    if len(jd) < 20:
        raise ValueError("job_description.txt is too short. Please add the actual JD.")

    return resume, jd


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Run the agent
# ─────────────────────────────────────────────────────────────────────────────

def run_agent(resume: str, job_description: str) -> dict:
    """Run the full LangGraph pipeline and return final state."""
    graph = build_graph()

    initial_state = {
        "resume":           resume,
        "job_description":  job_description,
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

    return graph.invoke(initial_state)


# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Save output files
# ─────────────────────────────────────────────────────────────────────────────

def save_outputs(result: dict) -> None:
    """
    Save agent results to output/ folder.
    - output/tailored_resume.txt   <-- cleaned resume ready to send
    - output/result_summary.txt    <-- score, changes, warnings
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── File 1: Tailored Resume ───────────────────────────────────────────────
    resume_file = OUTPUT_DIR / "tailored_resume.txt"

    if result.get("error"):
        resume_file.write_text(
            f"ERROR: {result['error']}\n\nGuardrail Flags:\n" +
            "\n".join(f"  - {f}" for f in result.get("guardrail_flags", [])),
            encoding="utf-8"
        )
    else:
        resume_file.write_text(
            result.get("tailored_resume", ""),
            encoding="utf-8"
        )

    # ── File 2: Result Summary ────────────────────────────────────────────────
    summary_file = OUTPUT_DIR / "result_summary.txt"

    lines = [
        "=" * 60,
        "  RECRUFORM - RESUME TAILORING RESULT",
        "=" * 60,
        f"  Generated  : {timestamp}",
        f"  Run ID     : {result.get('run_id', 'N/A')}",
        "",
    ]

    if result.get("error"):
        lines += [
            f"  STATUS     : FAILED",
            f"  ERROR      : {result['error']}",
        ]
    else:
        lines += [
            f"  STATUS     : SUCCESS",
            f"  Match Score: {result.get('match_score', 'N/A')}/100",
            f"  Steps      : {result.get('step_count', 0)}",
            f"  Tokens used: {result.get('token_count', 0)}",
            f"  Cost (est) : ${result.get('token_count', 0) * 0.00000059:.6f}",
            "",
        ]

        if result.get("warnings"):
            lines.append(f"  WARNINGS ({len(result['warnings'])}):")
            for w in result["warnings"]:
                lines.append(f"    * {w}")
            lines.append("")

        if result.get("changes_made"):
            lines.append(f"  CHANGES MADE ({len(result['changes_made'])}):")
            for c in result["changes_made"]:
                lines.append(f"    -> {c}")
            lines.append("")

        if result.get("guardrail_flags"):
            lines.append(f"  GUARDRAIL FLAGS ({len(result['guardrail_flags'])}):")
            for f in result["guardrail_flags"]:
                lines.append(f"    [!] {f}")

    summary_file.write_text("\n".join(lines), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Print to console
# ─────────────────────────────────────────────────────────────────────────────

def print_result(result: dict) -> None:
    """Print result summary to console (ASCII safe for Windows)."""
    def safe(text: str) -> str:
        return text.encode("ascii", errors="replace").decode("ascii")

    print("\n" + "=" * 60)
    print("  RECRUFORM - RESUME TAILORING RESULT")
    print("=" * 60)

    if result.get("error"):
        print(f"\n  [BLOCKED] {result['error']}")
        for f in result.get("guardrail_flags", []):
            print(f"    [!] {f}")
        return

    print(f"\n  Match Score : {result.get('match_score', 'N/A')}/100")
    print(f"  Steps taken : {result.get('step_count', 0)}")
    print(f"  Tokens used : {result.get('token_count', 0)}")
    print(f"  Run ID      : {result.get('run_id', 'N/A')}")

    if result.get("warnings"):
        print(f"\n  Warnings ({len(result['warnings'])}):")
        for w in result["warnings"]:
            print(f"    * {safe(w)}")

    if result.get("changes_made"):
        print(f"\n  Changes Made ({len(result['changes_made'])}):")
        for c in result["changes_made"]:
            print(f"    -> {safe(c)}")

    if result.get("tailored_resume"):
        wc = len(result["tailored_resume"].split())
        print(f"\n  Tailored Resume saved to: output/tailored_resume.txt ({wc} words)")

    print("\n" + "=" * 60)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  RECRUFORM - Production Resume Tailoring Agent (Day 9)")
    print("  INPUT  : input/resume.txt + input/job_description.txt")
    print("  OUTPUT : output/tailored_resume.txt + output/result_summary.txt")
    print("=" * 60)

    # ── Read inputs ───────────────────────────────────────────────────────────
    try:
        resume, jd = read_inputs()
        print(f"\n  Resume loaded    : {len(resume)} characters")
        print(f"  JD loaded        : {len(jd)} characters")
    except (FileNotFoundError, ValueError) as e:
        print(f"\n  [INPUT ERROR] {e}")
        exit(1)

    # ── Run agent ─────────────────────────────────────────────────────────────
    print("\n  Running agent pipeline...")
    print("  Flow: input_guard -> analyze_jd -> tailor_resume -> output_guard -> cost_guard")
    print("  Please wait...\n")

    result = run_agent(resume, jd)

    # ── Save outputs ──────────────────────────────────────────────────────────
    save_outputs(result)

    # ── Print to console ──────────────────────────────────────────────────────
    print_result(result)

    # ── Monitoring stats ──────────────────────────────────────────────────────
    print("\n  Monitoring Stats:")
    print_stats()

    print("\n  Output files saved:")
    print("    output/tailored_resume.txt  <-- copy this resume")
    print("    output/result_summary.txt   <-- match score + details")
    print("    logs/agent_runs.jsonl       <-- monitoring log\n")
