# CS239 JobScreener — Source and Reproduction

Run the commands below **from the repository root** (the folder containing `src/` and `requirements.txt`).

## Prerequisites

- Python 3.12+ recommended (use a version compatible with pinned dependencies).
- Network access to SiliconFlow for the Coordinator and two LLM specialist agents.
- A SiliconFlow account/API key, billed to your own token budget (BYOTC).
- Optional: `RAPIDAPI_KEY` for live JSearch retrieval. No live job API is needed for the three fictional demonstration postings.

## Install

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:SILICONFLOW_API_KEY="YOUR_KEY_HERE"
$env:SILICONFLOW_BASE_URL="https://api.siliconflow.com/v1"
```

macOS/Linux (use activation script for your shell):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export SILICONFLOW_API_KEY="YOUR_KEY_HERE"
export SILICONFLOW_BASE_URL="https://api.siliconflow.com/v1"
```

Never commit your real API key or `.env` to GitHub.

## Example invocation — CLI

```bash
python -m src.run_demo
```

The CLI starts the three A2A specialist services for its own run and records three scenarios in `traces/`. These are slower live LLM requests, not a quick replay.

## Example invocation — Web interface

Start each command in a separate terminal, with the required environment variables available to the Coordinator and LLM specialist processes:

```bash
python -m src.agents.compliance_agent --port 9101
python -m src.agents.specialist_agents --agent recruiter --port 9102
python -m src.agents.specialist_agents --agent culture --port 9103
python -m src.web_demo
```

Visit `http://127.0.0.1:8000`. The demo provides three sample scenarios and custom **candidate application text**. Custom structured job creation is not supported by the web form; the default job IDs are SWE-001, PM-002 and DS-003.

## Configuration

- `SILICONFLOW_API_KEY` (required for live LLM calls)
- `SILICONFLOW_BASE_URL` (optional, default `https://api.siliconflow.com/v1`)
- `SILICONFLOW_MODEL` (optional, default `Qwen/Qwen3-8B`)
- `RAPIDAPI_KEY` (optional, enables JSearch; demo falls back to fictional postings without it)
- `COMPLIANCE_URL`, `RECRUITER_URL`, `CULTURE_URL` (optional, default localhost ports 9101–9103)
- `WEB_PORT` (optional, default 8000)
- `A2A_TIMEOUT_SECONDS` (optional, default 180)

## Notes and limitations

Compliance is scripted/rule-based. Coordinator, Recruiter, and Culture Fit are LLM-based. MCP is used for job tools and A2A/JSONRPC for specialist interactions. The recorded traces are in `traces/` and their descriptions in `traces/README.md`. The job database is fictional by default. Screening recommendations are demonstration outputs, not verified legal or employment advice. Do not infer US work authorization from citizenship or country codes alone in real deployments.
