"""
run_demo.py — Job Application Screener demo runner.

Starts all three A2A services, runs three scenarios, saves traces.

Usage:
    python -m src.run_demo

Requires: SILICONFLOW_API_KEY environment variable.
"""
from __future__ import annotations
import asyncio
import json
import multiprocessing
import os
import sys
import time
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).parent.parent))

COMPLIANCE_PORT = int(os.environ.get("COMPLIANCE_PORT", "9101"))
RECRUITER_PORT  = int(os.environ.get("RECRUITER_PORT",  "9102"))
CULTURE_PORT    = int(os.environ.get("CULTURE_PORT",    "9103"))

TRACES_DIR = Path(__file__).parent.parent / "traces"
TRACES_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Three sample applications — deliberately varied for interesting traces
# ---------------------------------------------------------------------------

APPLICATIONS = [
    {
        "name": "trace_01_strong_candidate",
        "description": "S001 — Strong SWE candidate, all requirements met, US citizen.",
        "job_id": "SWE-001",
        "request": """
Name: Jordan Kim
Email: jordan.kim@email.com
School: UC Berkeley, BS Computer Science, graduated 2021
GPA: 3.7
Years of experience: 3
Skills: Python, SQL, REST APIs, PostgreSQL, Kubernetes
Expected salary: $135,000
Work authorization: US citizen (no sponsorship needed)
Cover letter: I am excited to apply for this backend engineering role.
I have 3 years of experience building scalable Python microservices at my current company,
where I led the migration of our monolith to a Kubernetes-based architecture.
I thrive in collaborative environments and enjoy mentoring junior engineers.
Summary: Experienced backend engineer with strong Python and cloud infrastructure skills.
        """.strip(),
    },
    {
        "name": "trace_02_sponsorship_required",
        "description": "S002 — Qualified candidate but requires visa sponsorship for a role that doesn't offer it.",
        "job_id": "SWE-001",
        "request": """
Name: Priya Sharma
Email: priya.sharma@email.com
School: IIT Bombay, BTech Computer Science, graduated 2022
GPA: 3.9
Years of experience: 2.5
Skills: Python, SQL, REST APIs, Go, PostgreSQL
Expected salary: $128,000
Work authorization: Indian citizen, requires H-1B sponsorship
Cover letter: I am applying for the backend engineer position.
During my 2.5 years at my current employer I have shipped multiple high-availability services
in Python and Go, handling millions of requests per day. I am detail-oriented and
communicate clearly with both engineering and product teams.
Summary: Strong technical background with experience in Python and distributed systems.
        """.strip(),
    },
    {
        "name": "trace_03_career_changer",
        "description": "S003 — Career changer, partial skill match, interesting culture fit.",
        "job_id": "DS-003",
        "request": """
Name: Alex Rivera
Email: alex.rivera@email.com
School: UCLA, MS Statistics, graduated 2023
GPA: 3.5
Years of experience: 1.5
Skills: Python, statistics, R, data visualization, SQL
Expected salary: $118,000
Work authorization: US citizen
Cover letter: I am transitioning from academic research into industry data science.
My MS thesis applied Bayesian methods to epidemiological data, and I am eager to apply
similar techniques to product recommendation problems. I learn quickly and adapt well to
fast-paced environments. While I have not yet worked with PyTorch in a production setting,
I have completed several personal projects using it.
Summary: Quantitative researcher transitioning to industry, strong stats background.
        """.strip(),
    },
]


# ---------------------------------------------------------------------------
# Service launchers
# ---------------------------------------------------------------------------

def _run(make_fn, port):
    app = make_fn(port)
    uvicorn.run(app, host="127.0.0.1", port=port,
                log_level="error", timeout_keep_alive=300)


def start_services() -> list[multiprocessing.Process]:
    from src.agents.compliance_agent import make_app as make_compliance
    from src.agents.specialist_agents import make_recruiter_app, make_culture_app

    procs = []
    for make_fn, port in [
        (make_compliance,    COMPLIANCE_PORT),
        (make_recruiter_app, RECRUITER_PORT),
        (make_culture_app,   CULTURE_PORT),
    ]:
        p = multiprocessing.Process(target=_run, args=(make_fn, port), daemon=True)
        p.start()
        procs.append(p)

    import httpx
    urls = [
        f"http://127.0.0.1:{COMPLIANCE_PORT}/.well-known/agent-card.json",
        f"http://127.0.0.1:{RECRUITER_PORT}/.well-known/agent-card.json",
        f"http://127.0.0.1:{CULTURE_PORT}/.well-known/agent-card.json",
    ]
    names = ["Compliance", "Recruiter", "Culture Fit"]
    for url, name in zip(urls, names):
        for _ in range(25):
            try:
                httpx.get(url, timeout=1.0)
                print(f"✓ {name} Agent up")
                break
            except:
                time.sleep(0.5)
    return procs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_all() -> None:
    print("\n" + "="*65)
    print("CS239 Job Application Screener — Phase 1 Demo")
    print("="*65)

    os.environ["COMPLIANCE_URL"] = f"http://127.0.0.1:{COMPLIANCE_PORT}"
    os.environ["RECRUITER_URL"]  = f"http://127.0.0.1:{RECRUITER_PORT}"
    os.environ["CULTURE_URL"]    = f"http://127.0.0.1:{CULTURE_PORT}"

    if not os.environ.get("SILICONFLOW_API_KEY"):
        print("\n⚠  SILICONFLOW_API_KEY not set — cannot run live LLM traces.")
        print("   Set the key and re-run.")
        return

    procs = start_services()

    from src.agents.coordinator_agent import run_coordinator

    try:
        for sc in APPLICATIONS:
            print(f"\n{'─'*55}")
            print(f"Scenario: {sc['name']}")
            print(f"Description: {sc['description']}")
            print('─'*55)

            trace = await run_coordinator(
                job_id=sc["job_id"],
                applicant_request=sc["request"],
                verbose=True,
            )

            out = TRACES_DIR / f"{sc['name']}.json"
            d = trace.to_dict()
            d["scenario"] = {"name": sc["name"], "description": sc["description"]}
            out.write_text(json.dumps(d, indent=2))
            print(f"\n✓ Trace saved: {out}")

    finally:
        for p in procs:
            p.terminate()

    print("\n✓ All scenarios complete.")


if __name__ == "__main__":
    asyncio.run(run_all())
