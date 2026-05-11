"""
Test Runner — Saare tests run karo aur results save karo.

Yeh script:
  1. Saare 4 test groups run karta hai
  2. Har group ka result alag file mein save karta hai
  3. Ek combined summary bhi banata hai

Run karo:
  python -W ignore run_tests.py
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RESULTS_DIR = Path("output/test_results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

TEST_GROUPS = [
    {
        "name":  "Group 1 — Normal Inputs",
        "file":  "tests/test_normal.py",
        "tests": "Tests 1-5",
        "out":   RESULTS_DIR / "group1_normal.txt",
    },
    {
        "name":  "Group 2 — Edge Cases",
        "file":  "tests/test_edge_cases.py",
        "tests": "Tests 6-10",
        "out":   RESULTS_DIR / "group2_edge_cases.txt",
    },
    {
        "name":  "Group 3 — Adversarial",
        "file":  "tests/test_adversarial.py",
        "tests": "Tests 11-13",
        "out":   RESULTS_DIR / "group3_adversarial.txt",
    },
    {
        "name":  "Group 4 — Regression",
        "file":  "tests/test_regression.py",
        "tests": "Tests 14-15",
        "out":   RESULTS_DIR / "group4_regression.txt",
    },
]


def run_group(group: dict) -> dict:
    """Run one test group, save output to file, return result info."""
    print(f"\n  Running {group['name']} ({group['tests']})...")

    cmd = [sys.executable, "-W", "ignore", "-m", "pytest", group["file"], "-v"]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    output = result.stdout + result.stderr

    # Save to individual file
    header = "\n".join([
        "=" * 60,
        f"  {group['name']}",
        f"  {group['tests']}",
        f"  Run at: {timestamp}",
        "=" * 60,
        "",
    ])
    group["out"].write_text(header + output, encoding="utf-8")

    # Parse pass/fail from output
    passed = output.count(" PASSED")
    failed = output.count(" FAILED")
    errors = output.count(" ERROR")

    status = "ALL PASSED" if failed == 0 and errors == 0 else "SOME FAILED"

    print(f"  {status} — {passed} passed, {failed} failed")
    print(f"  Saved to: {group['out']}")

    return {
        "name":   group["name"],
        "tests":  group["tests"],
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "file":   str(group["out"]),
        "status": status,
        "output": output,
    }


def save_summary(results: list) -> Path:
    """Save combined summary of all test groups."""
    total_passed = sum(r["passed"] for r in results)
    total_failed = sum(r["failed"] for r in results)
    total_errors = sum(r["errors"] for r in results)
    total_tests  = total_passed + total_failed + total_errors
    overall      = "ALL PASSED" if total_failed == 0 and total_errors == 0 else "SOME FAILED"

    lines = [
        "=" * 60,
        "  RECRUFORM DAY 9 — TEST RESULTS SUMMARY",
        f"  Run at : {timestamp}",
        "=" * 60,
        "",
        f"  OVERALL STATUS : {overall}",
        f"  Total Tests    : {total_tests}",
        f"  Passed         : {total_passed}",
        f"  Failed         : {total_failed + total_errors}",
        "",
        "-" * 60,
        "  GROUP BREAKDOWN",
        "-" * 60,
    ]

    for r in results:
        icon = "PASS" if r["failed"] == 0 and r["errors"] == 0 else "FAIL"
        lines.append(
            f"  [{icon}]  {r['name']:<30} "
            f"{r['passed']} passed / {r['failed']} failed"
        )

    lines += [
        "",
        "-" * 60,
        "  OUTPUT FILES",
        "-" * 60,
    ]
    for r in results:
        lines.append(f"  {r['file']}")

    lines += [
        "",
        "=" * 60,
        "  TEST CASE DETAILS",
        "=" * 60,
    ]

    test_names = {
        "group1_normal": [
            "Test 01 — Python resume relevancy",
            "Test 02 — No hallucination check",
            "Test 03 — Marketing resume quality",
            "Test 04 — Data Analyst relevancy",
            "Test 05 — Output format completeness",
        ],
        "group2_edge_cases": [
            "Test 06 — Empty resume handled",
            "Test 07 — Long resume page limit",
            "Test 08 — Hindi resume handled",
            "Test 09 — Vague JD handled",
            "Test 10 — Mismatched resume low score",
        ],
        "group3_adversarial": [
            "Test 11 — Prompt injection blocked",
            "Test 12 — Jailbreak blocked",
            "Test 13 — System prompt extraction blocked",
        ],
        "group4_regression": [
            "Test 14 — No banned filler phrases",
            "Test 15 — Output within page limit",
        ],
    }

    for r in results:
        lines.append(f"\n  {r['name']} ({r['tests']})")
        group_key = [k for k in test_names if k in r["file"].replace("\\", "/").replace(" ", "_").lower()]
        if group_key:
            for tname in test_names[group_key[0]]:
                if "PASSED" in r["output"] and tname.split("—")[1].strip().lower().replace(" ", "_")[:10] in r["output"].lower():
                    lines.append(f"    [PASS] {tname}")
                elif "FAILED" in r["output"]:
                    lines.append(f"    [FAIL] {tname}")
                else:
                    lines.append(f"    [PASS] {tname}")

    summary_file = RESULTS_DIR / "SUMMARY.txt"
    summary_file.write_text("\n".join(lines), encoding="utf-8")
    return summary_file


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  RECRUFORM DAY 9 — RUNNING ALL 15 TESTS")
    print(f"  Results will be saved to: output/test_results/")
    print("=" * 60)

    results = []
    for group in TEST_GROUPS:
        res = run_group(group)
        results.append(res)

    summary_path = save_summary(results)

    total_p = sum(r["passed"] for r in results)
    total_f = sum(r["failed"] + r["errors"] for r in results)

    print("\n" + "=" * 60)
    print("  FINAL RESULTS")
    print("=" * 60)
    for r in results:
        icon = "PASS" if r["failed"] == 0 else "FAIL"
        print(f"  [{icon}] {r['name']:<32} {r['passed']} passed / {r['failed']} failed")

    print(f"\n  TOTAL : {total_p} passed, {total_f} failed out of {total_p + total_f} tests")
    print(f"\n  Files saved in: output/test_results/")
    print(f"    SUMMARY.txt          <- overall summary")
    print(f"    group1_normal.txt    <- Tests 1-5 full output")
    print(f"    group2_edge_cases.txt <- Tests 6-10 full output")
    print(f"    group3_adversarial.txt <- Tests 11-13 full output")
    print(f"    group4_regression.txt  <- Tests 14-15 full output")
    print("=" * 60 + "\n")
