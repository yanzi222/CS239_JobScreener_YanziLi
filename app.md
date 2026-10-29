# Job Application Screener

## Purpose

A four-agent system that pre-screens job applications before human review. An
applicant submits a free-text application; the system evaluates it against a real
job posting and produces one of three decisions: **Approve** (advance to interview),
**Hold** (borderline — requires human review), or **Reject** (hard disqualification).

The central privacy guarantee is that no personally identifiable information (name,
school, graduation year, GPA) ever reaches the evaluation agents. Sanitization is
enforced in Python code before every agent-to-agent call — not just in the prompt.

## Supported Tasks

- **Course petition screening:** Evaluate whether a candidate meets hard eligibility
  rules (visa sponsorship, experience minimum) and soft qualification criteria
  (skill match, communication quality).
- **Multi-criteria synthesis:** Combine independent assessments from a legal
  compliance check, a technical qualification review, and a communication/motivation
  review into a single hiring recommendation.
- **Bias-resistant evaluation:** Produce qualification-based assessments without
  access to candidate identity, school prestige, or demographic information.

## Agents

| Agent | Type | Role |
|---|---|---|
| Coordinator | LLM | Receives application, fetches job requirements, sanitizes, orchestrates, synthesises |
| Compliance | Deterministic | Hard legal rules: sponsorship, experience minimum |
| Recruiter | LLM | Technical skill and experience assessment (PII-free) |
| Culture Fit | LLM | Communication, motivation, collaboration assessment (PII-free) |

## Protocols

- **MCP / stdio** — Coordinator calls `job_db` subprocess for job requirements and scoring tools
- **A2A / JSONRPC** — Coordinator sends sanitized payloads to three specialist agents
