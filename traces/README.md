# Phase 1 Execution Traces

These are actual saved executions, not hypothetical examples. Timestamps and LLM outputs are preserved as recorded; analyses below describe the execution rather than rewriting its decisions.

Each JSON trace contains applicant input, MCP tool calls/results, three A2A send/receive pairs (including field filtering), and the Coordinator final response. The job entries in these demos are **fictional fallback records**.

| Trace | Steps | Runtime | Compliance | Recruiter | Culture Fit | Final |
|---|---:|---:|---|---|---|---|
| [trace_01_strong_candidate.json](trace_01_strong_candidate.json) | 14 | 177.9s | COMPLIANCE-PASS | ADVANCE | ADVANCE | ADVANCE |

## 1. trace_01_strong_candidate.json

Strong applicant; clear match to backend requirements.

- **Job:** `SWE-001` — Software Engineer, Backend, TechCorp (fictional)
- **Execution:** 14 events; 177.9 seconds; three A2A requests and three A2A responses.
- **Compliance:** `eligible=true`; triggered `COMPLIANCE-PASS`.
- **Recruiter:** ADVANCE; **Culture Fit:** ADVANCE; **Coordinator final:** ADVANCE.
- **Policy connections:** P1, P5, P6, P7, P8.
- **Information flow:** the A2A `stripped` lists show field-level removal; see the JSON for precise payloads.

| [trace_02_sponsorship_required.json](trace_02_sponsorship_required.json) | 22 | 341.7s | COMPLIANCE-C1 | ADVANCE | ADVANCE | REJECT |

## 2. trace_02_sponsorship_required.json

Technically qualified applicant who explicitly requires sponsorship for a role that does not offer it.

- **Job:** `SWE-001` — Software Engineer, Backend, TechCorp (fictional)
- **Execution:** 22 events; 341.7 seconds; three A2A requests and three A2A responses.
- **Compliance:** `eligible=false`; triggered `COMPLIANCE-C1`.
- **Recruiter:** ADVANCE; **Culture Fit:** ADVANCE; **Coordinator final:** REJECT.
- **Policy connections:** P1, P3, P5, P8.
- **Information flow:** the A2A `stripped` lists show field-level removal; see the JSON for precise payloads.

| [trace_03_career_changer.json](trace_03_career_changer.json) | 22 | 538.9s | COMPLIANCE-C2, COMPLIANCE-C4 | ADVANCE | HOLD | HOLD |

## 3. trace_03_career_changer.json

Applicant with 1.5 years of experience against a 2-year minimum; Bayesian and PyTorch evidence supports further ML skill review.

- **Job:** `DS-003` — Data Scientist, TechCorp (fictional)
- **Execution:** 22 events; 538.9 seconds; three A2A requests and three A2A responses.
- **Compliance:** `eligible=false`; triggered `COMPLIANCE-C2, COMPLIANCE-C4`.
- **Recruiter:** ADVANCE; **Culture Fit:** HOLD; **Coordinator final:** HOLD.
- **Policy connections:** P1, P3, P5, P6, P7, P8.
- **Information flow:** the A2A `stripped` lists show field-level removal; see the JSON for precise payloads.

