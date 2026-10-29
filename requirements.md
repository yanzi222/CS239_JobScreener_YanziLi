# Requirements — Job Application Screener

## 1. What the Application Does

The Job Application Screener is a four-agent system that evaluates job applications
using parallel specialist agents, each receiving only the information it is authorized
to see. The system enforces privacy and fairness policies through Python code —
not just through prompt instructions.

### Workflow

1. An applicant submits a free-text application specifying their skills, experience,
   expected salary, and work authorization status.
2. The **Coordinator Agent** (LLM) receives the application, fetches the job
   requirements via MCP tools, and structures the application into a typed payload.
3. The Coordinator sanitizes the payload (removing PII) and delegates to three
   specialist agents sequentially via A2A:
   - **Compliance Agent** (deterministic): checks hard legal eligibility rules.
   - **Recruiter Agent** (LLM): assesses qualifications and experience.
   - **Culture Fit Agent** (LLM): assesses communication style and motivation.
4. The Coordinator synthesizes all three assessments into a final hiring recommendation.

### Application Domain

Automated pre-screening of job applications before human review. The system
produces one of three outcomes per application: Approve (advance to interview),
Hold (borderline — requires human review), or Reject (hard disqualification).

### Supported Scenarios

| Scenario | Student | Job | Key policy |
|---|---|---|---|
| Strong candidate | Jordan Kim | SWE-001 | All criteria met — approved |
| Sponsorship required | Priya Sharma | SWE-001 | Visa block — compliance hard rule |
| Career changer | Alex Rivera | DS-003 | Partial skills — borderline hold |

---

## 2. What the Application Must Never Do

The following are hard prohibitions. Violating any of them constitutes a system failure
regardless of the quality of the final recommendation.

**N1 — Never forward PII to specialist agents.**
name, email, school, university, graduation_year, GPA, gender, ethnicity,
nationality_name, photo_url, or linkedin_url must never appear in any A2A payload
sent to Compliance, Recruiter, or Culture Fit agents.

**N2 — Never allow the applicant to contact specialist agents directly.**
Compliance, Recruiter, and Culture Fit agents are internal services. They must
not be reachable by any party other than the Coordinator.

**N3 — Never produce a recommendation without consulting all three specialist agents.**
The Coordinator must call delegate_to_specialists before generating a final response.
A recommendation based solely on the Coordinator's own reasoning is prohibited.

**N4 — Never use LLM-inferred values in the delegation payload.**
All numeric values (years_experience, salary, min_experience_years) and skill lists
in the delegation payload must originate from MCP tool results, not from the LLM's
inference or memory.

**N5 — Never override a Compliance hard block with an LLM recommendation.**
If the Compliance Agent returns eligible=False, the final recommendation must
reflect ineligibility. No Recruiter or Culture Fit assessment can reverse a
Compliance rejection.

**N6 — Never persist applicant data across sessions.**
No applicant information from one screening session may influence another.
Each session starts from a clean state.

**N7 — Never loop on the same MCP tool call more than three times.**
If a tool is called more than 3 times total, or more than 2 times consecutively
with identical arguments, the system must block the call and return an error.

**N8 — Never expose internal agent decisions to the applicant.**
The Coordinator's final response must not reveal which agent said what, quote
raw agent outputs, or disclose internal scoring details beyond the final recommendation.
