"""
Job Application Screener — MCP tool server (stdio subprocess).

get_job_requirements: calls JSearch (RapidAPI) for real job postings.
  Falls back to fictional DB if RAPIDAPI_KEY is not set or API fails.

Other tools are local/deterministic and need no external API.
"""
from __future__ import annotations
import os
import httpx
from mcp.server.mcpserver import MCPServer

server = MCPServer("JobScreener-DB")

RAPIDAPI_KEY  = os.environ.get("RAPIDAPI_KEY", "")
RAPIDAPI_HOST = "jsearch.p.rapidapi.com"

# ---------------------------------------------------------------------------
# Fallback fictional job postings (used when no API key or API fails)
# ---------------------------------------------------------------------------

FALLBACK_JOBS = {
    "SWE-001": {
        "title": "Software Engineer, Backend",
        "company": "TechCorp (fictional)",
        "team": "Platform",
        "required_skills": ["Python", "SQL", "REST APIs"],
        "preferred_skills": ["Kubernetes", "Go", "PostgreSQL"],
        "min_experience_years": 2,
        "salary_range_usd": [120000, 160000],
        "job_offers_sponsorship": False,
        "description": "Build and maintain scalable backend services.",
        "source": "fallback",
    },
    "PM-002": {
        "title": "Product Manager",
        "company": "TechCorp (fictional)",
        "team": "Growth",
        "required_skills": ["product strategy", "stakeholder management", "data analysis"],
        "preferred_skills": ["SQL", "A/B testing", "Figma"],
        "min_experience_years": 3,
        "salary_range_usd": [130000, 175000],
        "job_offers_sponsorship": False,
        "description": "Define and drive the product roadmap.",
        "source": "fallback",
    },
    "DS-003": {
        "title": "Data Scientist",
        "company": "TechCorp (fictional)",
        "team": "Analytics",
        "required_skills": ["Python", "machine learning", "statistics"],
        "preferred_skills": ["PyTorch", "Spark", "causal inference"],
        "min_experience_years": 2,
        "salary_range_usd": [125000, 165000],
        "job_offers_sponsorship": True,
        "description": "Build ML models to improve recommendations.",
        "source": "fallback",
    },
}

SKILL_ALIASES = {
    "ml": "machine learning",
    "deep learning": "machine learning",
    "neural networks": "machine learning",
    "pytorch": "PyTorch",
    "tensorflow": "machine learning",
    "postgres": "PostgreSQL",
    "k8s": "Kubernetes",
    "restful": "REST APIs",
    "rest": "REST APIs",
    "apis": "REST APIs",
    "stats": "statistics",
    "ab testing": "A/B testing",
}

SPONSORSHIP_RULES = {
    "US": False, "CA": False, "GB": False, "AU": False, "NZ": False,
    "DE": False, "FR": False,
    "IN": True, "CN": True, "BR": True, "MX": True, "NG": True,
    "KR": True, "JP": True,
}

# ---------------------------------------------------------------------------
# JSearch API helper
# ---------------------------------------------------------------------------

def _jsearch_query(query: str, num_pages: int = 1) -> list[dict]:
    """Call JSearch and return raw job list. Returns [] on any failure."""
    if not RAPIDAPI_KEY:
        return []
    try:
        resp = httpx.get(
            "https://jsearch.p.rapidapi.com/search",
            headers={
                "X-RapidAPI-Key": RAPIDAPI_KEY,
                "X-RapidAPI-Host": RAPIDAPI_HOST,
            },
            params={"query": query, "num_pages": str(num_pages), "page": "1"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception:
        return []


def _parse_jsearch_job(job: dict) -> dict:
    """Convert a JSearch job record into our standard format."""
    # Extract salary
    sal_min = job.get("job_min_salary") or 0
    sal_max = job.get("job_max_salary") or 0
    if sal_min and sal_max:
        salary = [int(sal_min), int(sal_max)]
    elif sal_min:
        salary = [int(sal_min), int(sal_min * 1.3)]
    else:
        salary = [100000, 160000]  # typical range if not listed

    # Extract skills from highlights / description
    desc = job.get("job_description", "")
    highlights = job.get("job_highlights", {})
    qual_list = highlights.get("Qualifications", [])
    skills_raw = " ".join(qual_list) + " " + desc[:500]

    # Heuristic skill extraction
    common_skills = [
        "Python", "Java", "SQL", "JavaScript", "TypeScript", "Go", "Rust",
        "React", "Node.js", "REST APIs", "AWS", "GCP", "Azure", "Docker",
        "Kubernetes", "PostgreSQL", "MongoDB", "machine learning", "PyTorch",
        "TensorFlow", "statistics", "Spark", "Scala", "product strategy",
        "data analysis", "stakeholder management", "A/B testing", "Figma",
    ]
    found_skills = [s for s in common_skills if s.lower() in skills_raw.lower()]
    required = found_skills[:4] if found_skills else ["communication", "teamwork"]
    preferred = found_skills[4:7] if len(found_skills) > 4 else []

    # Experience
    exp = 0
    for phrase in ["years of experience", "years experience"]:
        idx = desc.lower().find(phrase)
        if idx > 2:
            try:
                exp = int(desc[idx-2:idx].strip().split()[-1])
                break
            except:
                pass

    return {
        "title": job.get("job_title", "Unknown Role"),
        "company": job.get("employer_name", "Unknown Company"),
        "location": job.get("job_city", "") + ", " + job.get("job_state", ""),
        "required_skills": required,
        "preferred_skills": preferred,
        "min_experience_years": exp or 2,
        "salary_range_usd": salary,
        "job_offers_sponsorship": bool(job.get("job_is_remote")),
        "description": desc[:400] + "..." if len(desc) > 400 else desc,
        "apply_url": job.get("job_apply_link", ""),
        "source": "JSearch / RapidAPI (live)",
    }


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@server.tool()
def get_job_requirements(job_id: str) -> dict:
    """
    Fetch job requirements for screening.

    If RAPIDAPI_KEY is set: searches JSearch (LinkedIn/Indeed/Glassdoor aggregator)
    for a real live job posting matching the query in job_id.
    Use natural language like "Software Engineer Python backend" or "Data Scientist ML".

    Falls back to fictional job DB (SWE-001, PM-002, DS-003) if no API key
    or if the query returns no results.

    Returns: title, company, required_skills, preferred_skills,
    min_experience_years, salary_range_usd, job_offers_sponsorship,
    description, source (live or fallback).
    """
    # Try live API first
    if RAPIDAPI_KEY:
        jobs = _jsearch_query(job_id, num_pages=1)
        if jobs:
            parsed = _parse_jsearch_job(jobs[0])
            return {"job_id": job_id, **parsed}

    # Fallback to fictional DB
    key = job_id.upper()
    job = FALLBACK_JOBS.get(key)
    if job:
        return {"job_id": key, **job}

    # If neither works, return available options
    return {
        "error": (
            f"Job '{job_id}' not found. "
            f"With RAPIDAPI_KEY set, use natural language like 'Python backend engineer'. "
            f"Without key, use: {list(FALLBACK_JOBS.keys())}"
        )
    }


@server.tool()
def search_jobs(query: str, max_results: int = 3) -> dict:
    """
    Search for live job postings matching a query (requires RAPIDAPI_KEY).
    Returns up to max_results jobs with title, company, location, and key requirements.
    Use this to find relevant job IDs before calling get_job_requirements.

    Example queries: "machine learning engineer San Francisco",
    "product manager fintech", "backend engineer Python remote"
    """
    if not RAPIDAPI_KEY:
        return {
            "error": "RAPIDAPI_KEY not set. Set it to enable live job search.",
            "fallback_jobs": list(FALLBACK_JOBS.keys()),
        }
    jobs = _jsearch_query(query, num_pages=1)
    if not jobs:
        return {"results": [], "message": "No jobs found for this query."}

    results = []
    for j in jobs[:max_results]:
        results.append({
            "title": j.get("job_title"),
            "company": j.get("employer_name"),
            "location": f"{j.get('job_city','')}, {j.get('job_state','')}".strip(", "),
            "posted": j.get("job_posted_at_datetime_utc", "")[:10],
            "use_as_job_id": j.get("job_title", ""),  # pass this to get_job_requirements
        })
    return {"query": query, "results": results, "source": "JSearch / RapidAPI"}


@server.tool()
def lookup_skill_equivalence(skill: str) -> dict:
    """
    Map an informal or abbreviated skill name to its standard category.
    Returns the canonical name and whether it matched an alias.
    """
    normalized = skill.lower().strip()
    canonical = SKILL_ALIASES.get(normalized, skill)
    return {
        "input": skill,
        "canonical": canonical,
        "alias_matched": normalized in SKILL_ALIASES,
    }


@server.tool()
def check_work_authorization(country_code: str) -> dict:
    """
    Return whether candidates from this country typically require US visa
    sponsorship. country_code is a 2-letter ISO code (e.g. US, IN, GB).
    Does NOT return any candidate-identifying information.
    """
    code = country_code.upper().strip()
    requires = SPONSORSHIP_RULES.get(code)
    if requires is None:
        return {
            "country_code": code,
            "requires_sponsorship": True,
            "note": "Unknown country — assuming sponsorship required.",
        }
    return {
        "country_code": code,
        "requires_sponsorship": requires,
        "note": "Based on standard US work authorization rules.",
    }


@server.tool()
def calculate_experience_score(years_required: int, years_actual: float) -> dict:
    """
    Compute a 0–100 experience score.
    Returns: score, meets_minimum, ratio.
    """
    if years_required <= 0:
        return {"error": "years_required must be positive"}
    ratio = round(years_actual / years_required, 2)
    score = min(100, int(ratio * 70 + (20 if ratio >= 1.0 else 0)))
    return {
        "years_required": years_required,
        "years_actual": years_actual,
        "ratio": ratio,
        "score": score,
        "meets_minimum": years_actual >= years_required,
    }


if __name__ == "__main__":
    server.run()
