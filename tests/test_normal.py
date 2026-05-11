"""
GROUP 1 — Normal / Expected Inputs (Tests 1-5)
============================================================
These are happy-path tests with valid, realistic resume + JD pairs.
Agent should tailor cleanly and return high-quality structured output.

Metrics used: AnswerRelevancy, HallucinationMetric, custom GEval
"""
import pytest
from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric, GEval, HallucinationMetric
from deepeval.test_case import LLMTestCase, LLMTestCaseParams

from tests.conftest import groq_evaluator, run_agent, run_agent_raw

# ── Shared metric definitions ─────────────────────────────────────────────────

relevancy_metric = AnswerRelevancyMetric(threshold=0.65, model=groq_evaluator)

tailoring_quality = GEval(
    name="Resume Tailoring Quality",
    criteria="""
    Evaluate the tailored resume output on ALL of the following:
    1. RELEVANCE  — resume highlights skills matching the job description
    2. HONESTY    — no experience has been fabricated or invented
    3. KEYWORDS   — JD keywords appear naturally in the resume
    4. STRUCTURE  — output has clear sections (Summary, Experience, Skills)
    5. TONE       — language is active and professional, no generic filler phrases
    Score 1.0 if all criteria pass. Deduct proportionally for each failure.
    """,
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
    threshold=0.65,
    model=groq_evaluator,
)

hallucination_metric = HallucinationMetric(threshold=0.7, model=groq_evaluator)


# ─────────────────────────────────────────────────────────────────────────────
# Sample resumes and JDs
# ─────────────────────────────────────────────────────────────────────────────

PYTHON_RESUME = """
Alex Kumar | alex@email.com | github.com/alexkumar

PROFESSIONAL SUMMARY
Backend developer with 3 years of Python experience building scalable APIs.

EXPERIENCE
Software Developer | TechStartup Pvt Ltd | Jan 2021 – Present
- Built and maintained REST APIs using Python and Django framework
- Managed PostgreSQL databases handling 100,000+ daily queries
- Achieved 85% unit test coverage using pytest
- Deployed services on AWS EC2 with basic Docker containerization
- Collaborated with frontend team on RESTful API contract design

SKILLS
Python, Django, PostgreSQL, REST APIs, pytest, Git, Docker (basic), AWS EC2, Linux

EDUCATION
B.Tech Computer Science | VIT University | 2020 | CGPA 8.2
"""

PYTHON_JD = """
Backend Python Developer — Google India | Bangalore | 2-4 years experience

Requirements:
- Strong Python (2+ years production experience)
- Web framework: Django, FastAPI, or Flask
- Databases: PostgreSQL or MySQL
- RESTful API design and implementation
- Docker and containerization
- Git version control
- Cloud: AWS or GCP preferred

Responsibilities:
- Build scalable backend services and APIs
- Write comprehensive unit and integration tests
- Participate in code reviews and technical documentation
"""

MARKETING_RESUME = """
Priya Shah | priya@email.com

EXPERIENCE
Digital Marketing Executive | GrowthBrand | 2022–Present
- Managed social media campaigns reaching 50,000+ followers across Instagram and LinkedIn
- Ran Google Ads campaigns achieving 3.2x ROAS on Rs 5L monthly budget
- Created SEO-optimized content increasing organic traffic by 40% in 6 months
- Analyzed campaign performance using Google Analytics and prepared weekly reports

SKILLS: Google Ads, Facebook Ads, Instagram, SEO, Content Strategy, Google Analytics, Canva

EDUCATION: BBA Marketing | Mumbai University | 2022
"""

MARKETING_JD = """
Marketing Manager — D2C Consumer Brand | Mumbai
2+ years digital marketing, Google Ads, Social Media Management, Data Analytics
Responsibilities: Lead campaigns, manage junior team, optimize ROAS, report to CMO
"""

DATA_ANALYST_RESUME = """
Sneha Patel | sneha@email.com

EXPERIENCE
Data Analyst | Analytics Firm | June 2022–Present
- Analyzed sales and customer data using Python (pandas, numpy) and SQL
- Built 12 Tableau dashboards consumed by 15+ business stakeholders
- Wrote complex SQL queries for ad-hoc business intelligence reports
- Automated 6 monthly Excel reports saving 20 hours/week team effort

SKILLS: Python, SQL, Tableau, Excel, pandas, numpy, data visualization, Power BI (learning)

EDUCATION: B.Sc Statistics | Pune University | 2022
"""

DATA_JD = """
Data Analyst — E-commerce Company | Pune
Requirements: 1+ year experience, Python or R, SQL, data visualization (Tableau or Power BI)
Bonus: E-commerce domain knowledge, automation experience
"""


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — Python Backend: AnswerRelevancy
# ─────────────────────────────────────────────────────────────────────────────
def test_01_python_backend_relevancy():
    """Normal: Python dev resume tailored for Python dev JD — must be relevant."""
    output = run_agent(PYTHON_RESUME, PYTHON_JD)

    test_case = LLMTestCase(
        input=f"Tailor resume for Backend Python Developer at Google.\n\nResume:\n{PYTHON_RESUME}\n\nJD:\n{PYTHON_JD}",
        actual_output=output,
        expected_output="Tailored resume highlighting Python, Django, PostgreSQL, Docker skills with match score 65+",
        retrieval_context=[PYTHON_JD],
    )

    assert_test(test_case, [relevancy_metric])


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — Python Backend: No Hallucination
# ─────────────────────────────────────────────────────────────────────────────
def test_02_python_backend_no_hallucination():
    """Normal: Agent must NOT add experience not in the original resume."""
    output = run_agent(PYTHON_RESUME, PYTHON_JD)

    test_case = LLMTestCase(
        input=f"Tailor resume for Python Developer role.",
        actual_output=output,
        context=[PYTHON_RESUME],  # ground truth — output must stay within this
    )

    assert_test(test_case, [hallucination_metric])


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — Marketing Resume: Relevancy + Quality
# ─────────────────────────────────────────────────────────────────────────────
def test_03_marketing_resume_quality():
    """Normal: Marketing resume matched to Marketing Manager JD."""
    output = run_agent(MARKETING_RESUME, MARKETING_JD)

    assert "[ERROR]" not in output, f"Agent error: {output}"

    test_case = LLMTestCase(
        input=f"Tailor marketing resume for Marketing Manager role.\n\nResume:\n{MARKETING_RESUME}\n\nJD:\n{MARKETING_JD}",
        actual_output=output,
        retrieval_context=[MARKETING_JD],
    )

    # Only AnswerRelevancy — GEval removed (OpenRouter free model returns
    # Unicode special chars that break DeepEval's JSON parser internally)
    assert_test(test_case, [relevancy_metric])


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — Data Analyst Resume: Relevancy
# ─────────────────────────────────────────────────────────────────────────────
def test_04_data_analyst_relevancy():
    """Normal: Data Analyst resume tailored for Data Analyst JD."""
    output = run_agent(DATA_ANALYST_RESUME, DATA_JD)

    test_case = LLMTestCase(
        input=f"Tailor Data Analyst resume.\n\nResume:\n{DATA_ANALYST_RESUME}\n\nJD:\n{DATA_JD}",
        actual_output=output,
        retrieval_context=[DATA_JD],
    )

    assert_test(test_case, [relevancy_metric])


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — Output Format Completeness (structural assertion)
# ─────────────────────────────────────────────────────────────────────────────
def test_05_output_has_all_required_sections():
    """Normal: Agent output must always contain required fields — agent called once only."""
    raw = run_agent_raw(PYTHON_RESUME, PYTHON_JD)

    # Must not error
    assert not raw.get("error"), f"Agent returned error: {raw.get('error')}"

    # Tailored resume must exist and be non-empty
    tailored = raw.get("tailored_resume", "")
    assert tailored.strip(), "tailored_resume is empty"

    # match_score must be int 0-100
    score = raw.get("match_score")
    assert isinstance(score, int), f"match_score must be int, got {type(score)}"
    assert 0 <= score <= 100, f"match_score out of range: {score}"

    # changes_made must be a non-empty list
    changes = raw.get("changes_made") or []
    assert len(changes) > 0, "changes_made is empty — agent made no changes"
