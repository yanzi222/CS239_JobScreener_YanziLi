# Compliance Agent

**Type:** Rule-based / deterministic (no LLM)

**Available tools:** None. The Compliance Agent receives a JSON payload via A2A
and applies hard-coded rules directly. It does not call any external tools or APIs.

## Implementation and Decision Logic

The Compliance Agent runs `run_compliance_checks(payload)` on the incoming A2A
payload. It is intentionally deterministic: the same input always produces the
same output, making compliance decisions fully auditable.

**Step 1 — PII validation (Policy P2):**
`_assert_sanitized(payload)` checks whether any of the following fields are
present: name, email, phone, address, gender, ethnicity, nationality_name,
school, university, graduation_year, gpa, photo_url, linkedin_url. If any are
found, the function raises a ValueError and returns eligible=False with
triggered_rule=COMPLIANCE-ERROR. This runs before any business logic.

**Step 2 — Hard eligibility rules:**

Rule C1 (sponsorship): If `requires_sponsorship=True` and
`job_offers_sponsorship=False`, set eligible=False and append COMPLIANCE-C1.
This rule cannot be waived.

Rule C2 (experience minimum): If `years_experience < min_experience_years`,
set eligible=False and append COMPLIANCE-C2. This rule cannot be waived.

Rule C3 (salary range): If `expected_salary_usd` falls outside the posted
salary range by more than 10%, append flag COMPLIANCE-C3. This is advisory only
and does not set eligible=False.

Rule C4 (required skills): For each skill in `required_skills`, check whether
it appears (case-insensitive) in `candidate_skills`. Missing skills append flag
COMPLIANCE-C4. This is advisory only and does not set eligible=False.

**Step 3 — Output:**
Returns a JSON object: `{eligible, reasons, flags, triggered_rules, reviewed_by}`.
If eligible=True and no flags, returns COMPLIANCE-PASS.

## Policies Enforced

P2 — validates incoming payload for prohibited PII fields before processing.
P3 — eligible=False decisions (C1, C2) are final and cannot be overridden.
P4 — runs on localhost:9101, not publicly accessible.
