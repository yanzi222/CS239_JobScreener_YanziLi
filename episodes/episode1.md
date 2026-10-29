# Episode 1 — Strong Candidate

**Status:** Real execution (not hypothetical). Full raw trace: [`../traces/trace_01_strong_candidate.json`](../traces/trace_01_strong_candidate.json).

## Initial Inputs

**Job ID:** `SWE-001`. The MCP tool supplies job requirements from the fictional fallback job database.

**Applicant-provided facts (selected; sensitive identifiers omitted here):**

```text
Years of experience: 3
Skills: Python, SQL, REST APIs, PostgreSQL, Kubernetes
Expected salary: $135,000
Work authorization: US citizen (no sponsorship needed)
Cover letter: I am excited to apply for this backend engineering role.
I have 3 years of experience building scalable Python microservices at my current company,
where I led the migration of our monolith to a Kubernetes-based architecture.
I thrive in collaborative environments and enjoy mentoring junior engineers.
Summary: Experienced backend engineer with strong Python and cloud infrastructure skills.
```

## Trajectory

1. Coordinator establishes MCP / stdio tool connection.
2. Coordinator calls MCP tool `get_job_requirements` with `{"job_id": "SWE-001"}`.
3. MCP tool `get_job_requirements` returns recorded data (see JSON trace).
4. Coordinator sends sanitized A2A payload to **compliance**; removed fields: name, email, cover_letter, work_history, summary, school, gpa, graduation_year.
5. Coordinator sends sanitized A2A payload to **recruiter**; removed fields: name, email, school, gpa, graduation_year.
6. Coordinator sends sanitized A2A payload to **culture**; removed fields: name, email, school, gpa, graduation_year.
7. **Compliance Agent** replies through A2A (eligible=True, rules=['COMPLIANCE-PASS']).
8. **Recruiter Agent** replies through A2A (recommendation=ADVANCE).
9. **Culture Agent** replies through A2A (recommendation=ADVANCE).
10. Coordinator calls MCP tool `calculate_experience_score` with `{"years_required": 2, "years_actual": 3}`.
11. MCP tool `calculate_experience_score` returns recorded data (see JSON trace).
12. Coordinator generates a final **ADVANCE** recommendation.

## Policy Connection

The episode illustrates P1, P5, P6, P7, P8. The recorded A2A payloads exclude direct identifying fields such as name, email, school, and GPA. The Compliance response records `COMPLIANCE-PASS`. The traces are Phase 1 observations; they do not demonstrate Phase 2 prevention of deliberately injected violations.

## Expected and Observed Outcome

**ADVANCE**, as recorded in the JSON. The relevant specialist decisions are Compliance `eligible=true`, Recruiter `ADVANCE`, and Culture Fit `ADVANCE`. Any discrepancy between model interpretation and deterministic checks is preserved in the raw execution log rather than silently corrected.
