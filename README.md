# CS239_JobScreener_YanziLi

**Course:** CS239 — Agentic Software Engineering, UCLA  
**Author:** Yanzi Li  
**License:** MIT ([LICENSE](LICENSE))

A four-agent job application screening system. An applicant submits a free-text
application; the system evaluates it against a job posting and produces a hiring
recommendation. No personally identifiable information (name, school, GPA) ever
reaches the evaluation agents — PII isolation is enforced in Python code before
every agent-to-agent call.

## Architecture

```
Applicant (user)
    │  HTTP / SSE
    ▼
Coordinator Agent (LLM · Qwen3-8B via SiliconFlow)
    ├─ MCP / stdio ──► job_db subprocess (5 tools)
    ├─ A2A / JSONRPC ──► Compliance Agent  (port 9101, deterministic)
    ├─ A2A / JSONRPC ──► Recruiter Agent   (port 9102, LLM, PII stripped)
    └─ A2A / JSONRPC ──► Culture Fit Agent (port 9103, LLM, PII stripped)
```

## Four Agents

| Agent | Type | Role |
|---|---|---|
| **Coordinator** | LLM | Orchestrates, calls MCP tools, sanitizes payloads, synthesises recommendation |
| **Compliance** | Deterministic | Hard legal rules: sponsorship, experience minimum |
| **Recruiter** | LLM | Technical skill and experience assessment (PII-free payload) |
| **Culture Fit** | LLM | Communication, motivation, collaboration assessment (PII-free payload) |

## Quick Start

See [`src/README.md`](src/README.md) for Windows PowerShell instructions, environment variables, and reproduction notes.


```bash
pip install -r requirements.txt

# Set environment variables
export SILICONFLOW_API_KEY=your_key
export SILICONFLOW_BASE_URL=https://api.siliconflow.com/v1

# Run CLI demo (starts all 3 A2A services automatically)
python -m src.run_demo

# Or run web demo (start agents first in separate terminals)
python -m src.agents.compliance_agent --port 9101
python -m src.agents.specialist_agents --agent recruiter --port 9102
python -m src.agents.specialist_agents --agent culture --port 9103
python -m src.web_demo
# Open http://127.0.0.1:8000
```

## Documents

- [`app.md`](app.md) — Application purpose and supported tasks
- [`policy.md`](policy.md) — 8 policies (P1–P8)
- [`tools.md`](tools.md) — MCP tool descriptions
- [`agents/`](agents/) — One Markdown file per agent including system prompts
- [`episodes/`](episodes/) — Three example episodes with policy connections
- [`traces/`](traces/) — Three real execution traces + README

## Phase 1 vs Phase 2

**Phase 1** (this branch): Coordinator sanitizes PII before delegation.
Traces show three distinct outcomes: advance, sponsorship rejection, borderline hold.
The Phase 1 policy document describes intended safeguards; not every intended rule is fully enforced.

**Phase 2**: Adds an independent interception layer that validates sanitization
before every A2A call regardless of Coordinator behaviour, plus an immutable audit log.

## Privacy Design

Three different sanitized views per application:

| Field | Compliance | Recruiter | Culture Fit |
|---|---|---|---|
| name / email | ❌ | ❌ | ❌ |
| school / university | ❌ | ❌ | ❌ |
| graduation year | ❌ | ❌ | ❌ |
| GPA | ❌ | ❌ | ❌ |
| years experience | ✅ | ✅ | ✅ |
| candidate skills | ✅ | ✅ | ✅ |
| cover letter | ❌ | ✅ | ✅ |
| work history | ❌ | ✅ | ✅ |
