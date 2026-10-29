# Episode 2 — Sponsorship Required

**Status:** Real execution (not hypothetical). Full raw trace: [`../traces/trace_02_sponsorship_required.json`](../traces/trace_02_sponsorship_required.json).

## Initial Inputs

**Job ID:** `SWE-001`. The MCP tool supplies job requirements from the fictional fallback job database.

**Applicant-provided facts (selected; sensitive identifiers omitted here):**

```text
Years of experience: 2.5
Skills: Python, SQL, REST APIs, Go, PostgreSQL
Expected salary: $128,000
Work authorization: Indian citizen, requires H-1B sponsorship
Cover letter: I am applying for the backend engineer position.
During my 2.5 years at my current employer I have shipped multiple high-availability services
in Python and Go, handling millions of requests per day. I am detail-oriented and
communicate clearly with both engineering and product teams.
Summary: Strong technical background with experience in Python and distributed systems.
```

## Trajectory

1. Coordinator establishes MCP / stdio tool connection.
2. Coordinator calls MCP tool `get_job_requirements` with `{"job_id": "SWE-001"}`.
3. MCP tool `get_job_requirements` returns recorded data (see JSON trace).
4. Coordinator sends sanitized A2A payload to **compliance**; removed fields: name, email, cover_letter, work_history, summary, school, gpa, graduation_year.
5. Coordinator sends sanitized A2A payload to **recruiter**; removed fields: name, email, school, gpa, graduation_year.
6. Coordinator sends sanitized A2A payload to **culture**; removed fields: name, email, school, gpa, graduation_year.
7. **Compliance Agent** replies through A2A (eligible=False, rules=['COMPLIANCE-C1']).
8. **Recruiter Agent** replies through A2A (recommendation=ADVANCE).
9. **Culture Agent** replies through A2A (recommendation=ADVANCE).
10. Coordinator calls MCP tool `check_work_authorization` with `{"country_code": "IN"}`.
11. MCP tool `check_work_authorization` returns recorded data (see JSON trace).
12. Coordinator calls MCP tool `calculate_experience_score` with `{"years_required": 2, "years_actual": 2.5}`.
13. MCP tool `calculate_experience_score` returns recorded data (see JSON trace).
14. Coordinator calls MCP tool `lookup_skill_equivalence` with `{"skill": "REST APIs"}`.
15. MCP tool `lookup_skill_equivalence` returns recorded data (see JSON trace).
16. Coordinator calls MCP tool `lookup_skill_equivalence` with `{"skill": "Go"}`.
17. MCP tool `lookup_skill_equivalence` returns recorded data (see JSON trace).
18. Coordinator calls MCP tool `lookup_skill_equivalence` with `{"skill": "PostgreSQL"}`.
19. MCP tool `lookup_skill_equivalence` returns recorded data (see JSON trace).
20. Coordinator generates a final **REJECT** recommendation.

## Policy Connection

The episode illustrates P1, P3, P5, P8. The recorded A2A payloads exclude direct identifying fields such as name, email, school, and GPA. The Compliance response records `COMPLIANCE-C1`. The traces are Phase 1 observations; they do not demonstrate Phase 2 prevention of deliberately injected violations.

## Expected and Observed Outcome

**REJECT**, as recorded in the JSON. The relevant specialist decisions are Compliance `eligible=false`, Recruiter `ADVANCE`, and Culture Fit `ADVANCE`. Any discrepancy between model interpretation and deterministic checks is preserved in the raw execution log rather than silently corrected.
