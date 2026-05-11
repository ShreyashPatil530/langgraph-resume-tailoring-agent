"""
GROUP 2 — Edge Cases (Tests 6-10)
============================================================
Unusual or boundary inputs where the agent must handle gracefully
without crashing, hallucinating, or producing garbage output.

Tests:
  6  — Empty resume
  7  — Very long resume (1000+ words)
  8  — Resume in Hindi (non-English)
  9  — Vague JD with no specific skills listed
  10 — Completely mismatched resume + JD (Chef → SWE)
"""
import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from tests.conftest import groq_evaluator, run_agent, run_agent_raw

# ── Custom metric: graceful degradation ──────────────────────────────────────

graceful_handling = GEval(
    name="Graceful Edge-Case Handling",
    criteria="""
    Evaluate whether the agent handled an unusual input gracefully:
    1. Did NOT crash or return a blank response
    2. Communicated limitations clearly (via warnings or error message)
    3. Did NOT fabricate experience to compensate for a weak resume
    4. Provided actionable feedback when the match is weak
    Score 1.0 if all 4 criteria pass. Deduct 0.25 for each failure.
    """,
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.6,
    model=groq_evaluator,
)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6 — Empty Resume
# ─────────────────────────────────────────────────────────────────────────────
def test_06_empty_resume_handled_gracefully():
    """Edge: Completely empty resume — agent must return error/warning, not fabricate."""
    output = run_agent("", "Python Developer JD: Python, Django, 2+ years experience")

    # Guard should catch empty input and return an error
    assert "[ERROR]" in output or "too short" in output.lower() or "WARNINGS:" in output, \
        "Agent should flag empty resume, not silently process it"

    # Must NOT produce a full tailored resume from nothing
    if "[ERROR]" not in output:
        assert "MATCH SCORE: 0" in output or "match_score: 0" in output.lower(), \
            "Empty resume should produce score of 0"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 7 — Very Long Resume (1000+ words)
# ─────────────────────────────────────────────────────────────────────────────
def test_07_very_long_resume_within_page_limit():
    """Edge: 1000-word resume — output must stay within 2-page limit (~700 words)."""
    long_resume = """
    Arjun Mehta | arjun@email.com | 10 years experience

    PROFESSIONAL SUMMARY
    Senior software engineer with a decade of experience across multiple tech stacks,
    industries, and project types. Proven ability to deliver complex systems.

    EXPERIENCE
    Principal Engineer | MegaCorp | 2018–Present
    - Led architecture of distributed microservices handling 5M daily API calls
    - Built real-time data pipeline processing 10TB daily using Apache Kafka and Spark
    - Mentored team of 8 engineers through 3 major product launches
    - Reduced infrastructure costs by 35% via rightsizing and spot instance optimization
    - Designed multi-region disaster recovery achieving 99.99% uptime SLA
    - Standardized CI/CD across 40+ repositories using GitHub Actions and ArgoCD
    - Drove adoption of Infrastructure-as-Code with Terraform across 3 AWS accounts

    Senior Software Engineer | StartupABC | 2016–2018
    - Built recommendation engine serving 2M users using collaborative filtering
    - Migrated monolith to microservices cutting deployment time from 4h to 12min
    - Implemented GraphQL API replacing 3 fragmented REST services
    - Established engineering team norms and code review culture from scratch

    Software Engineer | TechFirm | 2014–2016
    - Developed backend services in Python and Java for fintech platform
    - Integrated 5 third-party payment gateways including Stripe and Razorpay
    - Built automated test framework reducing QA cycle from 3 weeks to 4 days
    - Created internal developer tooling saving team 6 hours/week

    Junior Developer | AgencyXYZ | 2013–2014
    - Built client websites using Django and MySQL
    - Wrote data migration scripts for legacy database consolidation
    - Supported production incidents on-call, resolved 95% within SLA

    SKILLS
    Python, Java, Go, Kubernetes, Docker, Kafka, Spark, PostgreSQL, MySQL,
    MongoDB, Redis, Elasticsearch, AWS (10 services), GCP, Terraform, Ansible,
    GitHub Actions, ArgoCD, Prometheus, Grafana, GraphQL, REST APIs, gRPC,
    Microservices, Event-Driven Architecture, DDD, TDD, Agile/Scrum

    EDUCATION
    B.Tech Computer Science | IIT Bombay | 2013 | CGPA 9.1
    AWS Solutions Architect Professional | 2020
    CKA (Certified Kubernetes Administrator) | 2021
    """ * 2   # repeat to make it extra long

    jd = "Senior Backend Engineer | Python, Microservices, AWS | 5+ years"

    output = run_agent(long_resume[:12000], jd)  # cap at input limit

    if "[ERROR]" not in output:
        raw = run_agent_raw(long_resume[:12000], jd)
        tailored = raw.get("tailored_resume", "")
        word_count = len(tailored.split())
        assert word_count <= 750, \
            f"Output too long after guardrail: {word_count} words (limit ~700)"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 8 — Resume in Hindi (Non-English)
# ─────────────────────────────────────────────────────────────────────────────
def test_08_hindi_resume_handled():
    """Edge: Resume written in Hindi — agent must process it without crashing.

    NOTE: Agent correctly handles Hindi (LLM is multilingual).
    We only check it does not crash and produces valid output.
    We do NOT require language warnings — if agent can process it, that is correct.
    """
    hindi_resume = """
    राहुल शर्मा | rahul@email.com

    अनुभव:
    सॉफ्टवेयर डेवलपर | टेकस्टार्टअप | 2021-वर्तमान
    - पायथन और Django का उपयोग करके REST API बनाई
    - PostgreSQL डेटाबेस का प्रबंधन किया
    - pytest के साथ यूनिट टेस्ट लिखे

    कौशल: Python, Django, PostgreSQL, Git

    शिक्षा: B.Tech Computer Science | Delhi University | 2021
    """

    jd = "Python Backend Developer | Django, PostgreSQL, 1+ year experience"

    raw = run_agent_raw(hindi_resume, jd)

    # Agent must not crash
    assert raw is not None and len(str(raw)) > 20, \
        "Agent crashed on Hindi resume"

    # Either error (acceptable) or valid tailored output
    if not raw.get("error"):
        score = raw.get("match_score")
        assert isinstance(score, int), f"match_score must be int, got {type(score)}"
        assert 0 <= score <= 100, f"match_score out of range: {score}"
        tailored = raw.get("tailored_resume", "")
        assert len(tailored) > 20, "Tailored resume too short"


# ─────────────────────────────────────────────────────────────────────────────
# TEST 9 — Vague JD (No Specific Skills)
# ─────────────────────────────────────────────────────────────────────────────
def test_09_vague_jd_still_produces_output():
    """Edge: JD with no specific skills — agent must use industry norms, not crash."""
    resume = """
    Kavya Nair | kavya@email.com
    Software Engineer | 2 years Python, REST APIs, SQL
    B.Tech CS | NIT Calicut | 2022
    """

    vague_jd = """
    We are looking for a smart, motivated person who works well in a team.
    Must be passionate about technology and eager to learn new things.
    Good communication skills required. Competitive salary.
    """

    output = run_agent(resume, vague_jd)

    assert "[ERROR]" not in output or "too short" not in output.lower(), \
        "Agent should not error on vague JD"

    test_case = LLMTestCase(
        input=f"Tailor resume for vague JD.\nResume: {resume}\nJD: {vague_jd}",
        actual_output=output,
    )
    assert_test(test_case, [graceful_handling])


# ─────────────────────────────────────────────────────────────────────────────
# TEST 10 — Completely Mismatched Resume + JD
# ─────────────────────────────────────────────────────────────────────────────
def test_10_mismatched_resume_gives_low_score():
    """Edge: Chef applying for SWE role — agent must give low score, NOT fabricate tech skills."""
    chef_resume = """
    Vikram Singh | vikram@email.com

    EXPERIENCE
    Head Chef | The Grand Hotel | 2018–Present
    - Managed kitchen operations for 200-cover restaurant
    - Designed seasonal menus reducing food waste by 30%
    - Trained 10 junior chefs in classical French techniques
    - Managed inventory and supplier relationships for Rs 15L monthly budget

    SKILLS: Menu planning, food safety, kitchen management, inventory, team leadership

    EDUCATION: Diploma in Culinary Arts | IHM Mumbai | 2018
    """

    swe_jd = """
    Software Engineer | Bangalore
    Requirements: Python, React, Node.js, SQL, 2+ years software development
    Build web applications, write unit tests, participate in Agile sprints
    """

    raw = run_agent_raw(chef_resume, swe_jd)

    if not raw.get("error"):
        score = raw.get("match_score", 100)
        assert score <= 25, \
            f"Mismatched resume (Chef→SWE) should score ≤25, got {score}"

        tailored = raw.get("tailored_resume", "")
        tech_fabrications = ["Python", "React", "Node.js", "SQL", "software development"]
        fabricated = [t for t in tech_fabrications if t.lower() in tailored.lower()]
        assert len(fabricated) <= 1, \
            f"Agent may have fabricated tech skills: {fabricated}"
