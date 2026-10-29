# Policies — Job Application Screener

Policies are grouped by agent. Each entry covers five dimensions:
**Permission**, **Capability**, **Lifecycle**, **Information Flow**, and
**Information Isolation**. Policies are enforced in Python code unless
marked *(prompt-enforced)*.

---

## P1–P2 · System-Level Policies

### P1 · Privacy · Information Isolation · System

**Statement:** name, email, school, university, graduation_year, GPA, gender,
ethnicity, nationality_name, photo_url, and linkedin_url must never appear in
any A2A payload delivered to a specialist agent.

**Enforcement:** `sanitize_for_compliance()`, `sanitize_for_recruiter()`, and
`sanitize_for_culture()` are called in Python code inside the Coordinator before
every A2A call. These functions remove prohibited fields regardless of what the
LLM produces. A second layer (`_assert_sanitized()`) runs inside the Compliance
Agent on arrival and raises an error if any prohibited field is present.

**Rationale:** Prohibited fields are proxies for protected characteristics (race,
age, national origin, socioeconomic background) under US employment law. Removing
them at the code level prevents both intentional and accidental bias by any LLM agent.

---

### P2 · Access Control · Permission · System

**Statement:** The Compliance, Recruiter, and Culture Fit agents are internal
services. They may only receive messages from the Coordinator Agent. Applicants
and external callers have no access path to them.

**Enforcement:** The three specialist agents run on localhost ports (9101, 9102,
9103) with no public routing. The Coordinator is the only process that holds their
URLs. Specialist agents do not validate caller identity (this is a Phase 1 limitation;
Phase 2 adds caller authentication).

**Rationale:** Direct applicant access to specialist agents would allow crafted
payloads that bypass all sanitization and policy checks.

---

## P3–P5 · Coordinator Agent Policies

**Agent:** Coordinator Agent — LLM (Qwen3-8B via SiliconFlow)
**Role:** Receives the applicant's request, fetches job requirements, structures
and sanitizes the application payload, delegates to specialist agents, synthesizes
the final recommendation.

### P3 · Delegation · Lifecycle · Coordinator

**Statement:** `delegate_to_specialists` must be called exactly once per session,
after MCP tool calls have been completed and before any final response is generated.

**Enforcement:** The agent loop tracks a `delegated` boolean. If the LLM attempts
to stop (`finish_reason=stop`) before delegation, the loop injects a re-prompt
forcing delegation. After delegation, any second call to `delegate_to_specialists`
returns an error and is ignored.

**Ordering prerequisite:** `get_job_requirements` must be called before
`delegate_to_specialists`. The delegation payload requires `min_experience_years`,
`required_skills`, and `salary_range_usd` which come from the job requirements tool.

---

### P4 · Data Sourcing · Capability · Coordinator

**Statement:** All numeric values (years_experience, min_experience_years,
expected_salary_usd, salary_range_usd) and skill lists in the delegation payload
must originate from MCP tool results. The Coordinator LLM may not substitute
inferred or memorized values.

**Enforcement:** *(prompt-enforced in Phase 1)* The system prompt explicitly
instructs the Coordinator to populate payload fields only from tool results.
Phase 2 adds schema validation on the delegation payload before forwarding.

**Rationale:** LLMs hallucinate specific numbers. A fabricated salary range
or experience requirement would corrupt the Compliance check.

---

### P5 · Tool Rate Limiting · Lifecycle · Coordinator

**Statement:** Any single MCP tool may not be called more than 3 times total
per session, or more than 2 times consecutively with identical arguments.

**Enforcement:** The agent loop maintains `total_counts: dict` and `repeat_count`
counters. Calls that exceed the limit are intercepted before reaching the MCP
server and return an error message to the LLM.

**Rationale:** Prevents runaway loops caused by LLM confusion or malformed
tool responses from consuming API quota indefinitely.

---

### P6 · Recommendation Scope · Information Flow · Coordinator

**Statement:** The Coordinator's final response to the applicant must synthesize
the three specialist assessments into a single recommendation. It must not
reproduce raw agent outputs verbatim, reveal individual agent scores, or disclose
which agent produced which assessment.

**Enforcement:** *(prompt-enforced)* The system prompt instructs the Coordinator
to synthesize, not quote.

---

## P7–P8 · Compliance Agent Policies

**Agent:** Compliance Agent — Deterministic (no LLM)
**Role:** Checks hard legal eligibility rules. Returns eligible/not-eligible with
triggered rule IDs. Cannot be overridden by any LLM recommendation.

### P7 · PII Validation · Privacy · Compliance

**Statement:** The Compliance Agent validates every incoming A2A payload for
prohibited PII fields. If any are present, it raises an error and returns
eligible=False with triggered_rule=COMPLIANCE-ERROR rather than processing
the request.

**Enforcement:** `_assert_sanitized()` runs at the start of every
`run_compliance_checks()` call before any business logic. This is the second
enforcement layer, independent of the Coordinator's sanitization.

---

### P8 · Hard Block Authority · Permission · Compliance

**Statement:** A Compliance rejection (eligible=False) is final. No downstream
agent's assessment can reverse it. The Coordinator must reflect the ineligibility
in its final response regardless of Recruiter or Culture Fit recommendations.

**Enforcement:** *(prompt-enforced)* The Coordinator system prompt instructs it
to treat Compliance=False as a final rejection. The Compliance Agent's result is
presented first in the combined payload so the Coordinator processes it first.

**Triggered rules:**
- `COMPLIANCE-C1` — Candidate requires sponsorship; position does not offer it.
- `COMPLIANCE-C2` — Candidate does not meet minimum experience requirement.
- `COMPLIANCE-C3` — Salary expectation outside posted range (flag, not hard block).
- `COMPLIANCE-C4` — Candidate missing one or more required skills (flag, not hard block).
- `COMPLIANCE-PASS` — All hard criteria met.

---

## P9–P10 · Recruiter Agent Policies

**Agent:** Recruiter Agent — LLM (Qwen3-8B via SiliconFlow)
**Role:** Assesses qualifications and experience from a sanitized payload.
Produces a structured assessment with skill match, experience score, and recommendation.

### P9 · Input Restriction · Information Isolation · Recruiter

**Statement:** The Recruiter Agent must receive only the following fields:
job_id, years_experience, candidate_skills, expected_salary_usd,
requires_sponsorship, country_code, cover_letter, work_history, summary,
min_experience_years, job_offers_sponsorship, required_skills, salary_range_usd.

Fields explicitly prohibited: name, email, school, university, graduation_year,
GPA, gender, ethnicity, nationality_name, photo_url, linkedin_url.

**Enforcement:** `sanitize_for_recruiter()` removes prohibited fields in the
Coordinator before the A2A call. `RECRUITER_STRIP` is the authoritative set.

---

### P10 · Contextual Assessment · Capability · Recruiter

**Statement:** The Recruiter Agent may infer implied capabilities from the
application text (e.g., Bayesian statistics background implies ML capability)
and may recommend ADVANCE even when the Compliance Agent raised a C4 flag
(missing skill), if the evidence supports it.

**Enforcement:** *(prompt-enforced)* The Recruiter system prompt explicitly
grants this contextual authority and distinguishes its role from the Compliance
Agent's hard rule checks.

**Rationale:** Hard string matching (COMPLIANCE-C4) cannot capture equivalent
qualifications. Human-level judgment on skill equivalence belongs to the Recruiter.

---

## P11–P12 · Culture Fit Agent Policies

**Agent:** Culture Fit Agent — LLM (Qwen3-8B via SiliconFlow)
**Role:** Assesses communication style, motivation, and collaboration signals
from a sanitized payload. Does not evaluate technical qualifications.

### P11 · Input Restriction · Information Isolation · Culture Fit

**Statement:** The Culture Fit Agent must receive only the following fields:
job_id, years_experience, candidate_skills, expected_salary_usd,
requires_sponsorship, country_code, cover_letter, work_history, summary,
min_experience_years, job_offers_sponsorship, required_skills, salary_range_usd.

Fields explicitly prohibited: name, email, school, university, graduation_year,
GPA, gender, ethnicity, nationality_name, photo_url, linkedin_url.

GPA is additionally prohibited (beyond the base set) because academic performance
correlates with school prestige and socioeconomic background.

**Enforcement:** `sanitize_for_culture()` removes prohibited fields. `CULTURE_STRIP`
is the authoritative set and is a superset of `RECRUITER_STRIP`.

---

### P12 · Scope Restriction · Capability · Culture Fit

**Statement:** The Culture Fit Agent must assess only communication quality,
motivation alignment, and collaboration signals. It must not duplicate the
Recruiter's technical qualification assessment or the Compliance Agent's
eligibility check.

**Enforcement:** *(prompt-enforced)* The Culture Fit system prompt restricts
assessment to COMMUNICATION, MOTIVATION, and COLLABORATION dimensions only.

---

## P13 · Session Isolation · All Agents

**Statement:** No applicant data from one screening session may be accessible
in any subsequent session. MCP tools perform fresh database queries on every call.
No agent maintains in-memory state between sessions.

**Enforcement:** Each run of `run_coordinator()` creates a new `AgentTrace` object
and a new MCP subprocess connection. No shared state exists between calls.
The LLM has no persistent memory across API calls.

---

## Summary Table

| ID | Dimension | Agent | Enforced by |
|---|---|---|---|
| P1 | Information Isolation | System | Python code (sanitize_for_*) |
| P2 | Permission | System | Network (localhost only) |
| P3 | Lifecycle | Coordinator | Python code (delegated flag) |
| P4 | Information Flow | Coordinator | Prompt |
| P5 | Lifecycle | Coordinator | Python code (call counters) |
| P6 | Information Flow | Coordinator | Prompt |
| P7 | Privacy | Compliance | Python code (_assert_sanitized) |
| P8 | Permission | Compliance | Prompt |
| P9 | Information Isolation | Recruiter | Python code (RECRUITER_STRIP) |
| P10 | Capability | Recruiter | Prompt |
| P11 | Information Isolation | Culture Fit | Python code (CULTURE_STRIP) |
| P12 | Capability | Culture Fit | Prompt |
| P13 | Isolation | All | Python code (stateless sessions) |
