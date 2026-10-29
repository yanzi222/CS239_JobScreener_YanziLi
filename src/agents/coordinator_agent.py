"""
Coordinator Agent — LLM orchestrator (Qwen3-8B via SiliconFlow).

The only agent that communicates directly with the applicant. It:
1. Receives the job application in natural language.
2. Calls MCP tools to get job requirements and scores.
3. Sanitizes the application before sending to specialist agents.
4. Calls Recruiter Agent and Culture Fit Agent via A2A (parallel).
5. Calls Compliance Agent via A2A for hard eligibility rules.
6. Synthesizes all assessments into a final hiring recommendation.

PHASE 1 (this file, no safety framework):
  sanitize_for_recruiter() and sanitize_for_culture() remove PII.
  The sanitization is enforced in Python code, not just the prompt.

PHASE 2 would add: an interception layer that verifies sanitization
  happened before any A2A call, and logs all payloads for audit.
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from a2a.client import ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import SendMessageRequest
import a2a.types.a2a_pb2 as _pb

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SILICONFLOW_MODEL  = os.environ.get("SILICONFLOW_MODEL", "Qwen/Qwen3-8B")
SILICONFLOW_BASE   = os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.com/v1")
COMPLIANCE_URL     = os.environ.get("COMPLIANCE_URL",  "http://127.0.0.1:9101")
RECRUITER_URL      = os.environ.get("RECRUITER_URL",   "http://127.0.0.1:9102")
CULTURE_URL        = os.environ.get("CULTURE_URL",     "http://127.0.0.1:9103")
A2A_TIMEOUT_SECONDS = float(os.environ.get("A2A_TIMEOUT_SECONDS", "180"))

_HERE = Path(__file__).parent.parent
MCP_SERVER_MODULE  = "src.tools.job_db"
MCP_SERVER_CWD     = str(_HERE.parent)

# Fields that must NEVER reach specialist LLM agents
# Phase 1: stripped in Python code
# Phase 2 demo: you can comment out sanitize calls to show what breaks
RECRUITER_STRIP = {
    "name", "email", "phone", "address",
    "gender", "ethnicity", "nationality_name",
    "school", "university", "graduation_year",
    "gpa",                                      # GPA is school-prestige proxy → bias risk
    "photo_url", "linkedin_url", "cover_letter_name_mentions",
}
CULTURE_STRIP = {
    "name", "email", "phone", "address",
    "gender", "ethnicity", "nationality_name",
    "school", "university", "graduation_year",
    "gpa", "photo_url", "linkedin_url",
}
COMPLIANCE_STRIP = {
    "name", "email", "phone", "address",
    "gender", "ethnicity", "nationality_name",
    "school", "university", "graduation_year",
    "gpa",                                      # Legal rules don't need academic grades
    "photo_url", "linkedin_url", "cover_letter",
    "summary", "work_history",
}

# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------

def sanitize_for_recruiter(app: dict) -> dict:
    stripped = {k: v for k, v in app.items() if k not in RECRUITER_STRIP}
    removed = RECRUITER_STRIP & set(app.keys())
    if removed:
        print(f"  [SANITIZE → Recruiter] Stripped: {removed}")
    return stripped

def sanitize_for_culture(app: dict) -> dict:
    stripped = {k: v for k, v in app.items() if k not in CULTURE_STRIP}
    removed = CULTURE_STRIP & set(app.keys())
    if removed:
        print(f"  [SANITIZE → Culture]   Stripped: {removed}")
    return stripped

def sanitize_for_compliance(app: dict) -> dict:
    stripped = {k: v for k, v in app.items() if k not in COMPLIANCE_STRIP}
    removed = COMPLIANCE_STRIP & set(app.keys())
    if removed:
        print(f"  [SANITIZE → Compliance] Stripped: {removed}")
    return stripped

# ---------------------------------------------------------------------------
# MCP session
# ---------------------------------------------------------------------------

@asynccontextmanager
async def mcp_session():
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", MCP_SERVER_MODULE],
        cwd=MCP_SERVER_CWD,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session

async def discover_tools(session: ClientSession) -> list[dict]:
    listed = (await session.list_tools()).tools
    return [
        {"type": "function", "function": {
            "name": t.name,
            "description": t.description or "",
            "parameters": t.input_schema or {"type": "object", "properties": {}},
        }}
        for t in listed
    ]

async def call_mcp_tool(session: ClientSession, name: str, args: dict) -> dict:
    result = await session.call_tool(name, args)
    if result.is_error:
        return {"error": str(result.content)}
    if result.structured_content:
        return result.structured_content
    return json.loads(result.content[0].text)

# ---------------------------------------------------------------------------
# A2A calls
# ---------------------------------------------------------------------------

async def _a2a_call(url: str, payload: dict) -> dict:
    req = SendMessageRequest(
        message=new_text_message(json.dumps(payload), role=_pb.Role.ROLE_USER)
    )
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(A2A_TIMEOUT_SECONDS, connect=10.0)
        ) as http:
            # Configure the transport itself; resolver kwargs only affect card discovery.
            client = await create_client(
                url,
                client_config=ClientConfig(httpx_client=http),
                resolver_http_kwargs={"timeout": 30.0},
            )
            result_text = None
            async for event in client.send_message(req):
                which = event.WhichOneof("payload")
                if which == "task":
                    for artifact in event.task.artifacts:
                        for part in artifact.parts:
                            if part.WhichOneof("content") == "text":
                                result_text = part.text
                                break
                        if result_text:
                            break
                elif which == "artifact_update":
                    for part in event.artifact_update.artifact.parts:
                        if part.WhichOneof("content") == "text":
                            result_text = part.text
                            break
                if result_text:
                    break
        return json.loads(result_text) if result_text else {"error": "No response"}
    except Exception as e:
        return {"error": str(e)}

async def call_compliance(payload: dict) -> dict:
    return await _a2a_call(COMPLIANCE_URL, sanitize_for_compliance(payload))

async def call_recruiter(payload: dict) -> dict:
    return await _a2a_call(RECRUITER_URL, sanitize_for_recruiter(payload))

async def call_culture(payload: dict) -> dict:
    return await _a2a_call(CULTURE_URL, sanitize_for_culture(payload))

# ---------------------------------------------------------------------------
# JSON repair (for Qwen3 truncation)
# ---------------------------------------------------------------------------

def _repair_json(s: str) -> str:
    s = s.strip()
    def _close(t):
        valid = {'"','}',']','e','l','n','0','1','2','3','4','5','6','7','8','9'}
        while t and t[-1] not in valid: t = t[:-1]
        opens, in_str, esc = [], False, False
        for ch in t:
            if esc: esc=False; continue
            if ch=='\\' and in_str: esc=True; continue
            if ch=='"': in_str=not in_str; continue
            if not in_str:
                if ch in('{','['): opens.append(ch)
                elif ch=='}' and opens and opens[-1]=='{': opens.pop()
                elif ch==']' and opens and opens[-1]=='[': opens.pop()
        for ch in reversed(opens): t += '}' if ch=='{' else ']'
        return t
    candidate = _close(s)
    try: json.loads(candidate); return candidate
    except: pass
    depth,in_str,esc,last=0,False,False,-1
    for i,ch in enumerate(s):
        if esc: esc=False; continue
        if ch=='\\' and in_str: esc=True; continue
        if ch=='"': in_str=not in_str; continue
        if not in_str:
            if ch in('{','['): depth+=1
            elif ch in('}',']'): depth-=1
            elif ch==',' and depth==1: last=i
    if last>0:
        c2=s[:last]+'}'
        try: json.loads(c2); return c2
        except: pass
    return candidate

# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------

@dataclass
class AgentTrace:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    job_id: str = ""
    applicant_request: str = ""
    steps: list[dict] = field(default_factory=list)
    final_response: str = ""
    started_at: float = field(default_factory=time.time)

    def log(self, role: str, content: Any, step_type: str = "message") -> None:
        self.steps.append({
            "step": len(self.steps)+1, "type": step_type,
            "role": role, "content": content,
            "t": round(time.time()-self.started_at, 3),
        })

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "job_id": self.job_id,
            "applicant_request": self.applicant_request,
            "agent": "CoordinatorAgent",
            "model": SILICONFLOW_MODEL,
            "mcp_server": MCP_SERVER_MODULE,
            "compliance_agent": COMPLIANCE_URL,
            "recruiter_agent": RECRUITER_URL,
            "culture_fit_agent": CULTURE_URL,
            "started_at": self.started_at,
            "steps": self.steps,
            "final_response": self.final_response,
        }

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the Coordinator Agent for a job application screening system.

You receive job applications and orchestrate three specialist agents to evaluate them:
- Recruiter Agent: assesses qualifications and experience
- Culture Fit Agent: assesses communication style and motivation
- Compliance Agent: checks hard legal eligibility rules

## Workflow
1. Call get_job_requirements(job_id) to retrieve the job posting.
2. Call calculate_experience_score to score the candidate's experience.
3. Call lookup_skill_equivalence for any informal skill names if needed.
4. Call delegate_to_specialists ONCE with the full structured application payload.
5. Write a final hiring recommendation based on all three assessments.

## Application payload format (for delegate_to_specialists)
{
  "job_id": "string",
  "name": "string",
  "email": "string",
  "school": "string",
  "graduation_year": int,
  "gpa": float,
  "years_experience": float,
  "candidate_skills": ["string"],
  "expected_salary_usd": int,
  "requires_sponsorship": bool,
  "country_code": "string",
  "cover_letter": "string",
  "work_history": "string",
  "summary": "string",
  "min_experience_years": int,
  "job_offers_sponsorship": bool,
  "required_skills": ["string"],
  "salary_range_usd": [int, int]
}

## Rules
- Call delegate_to_specialists EXACTLY ONCE.
- Never fabricate application data — use what the applicant provided.
- Do not call the same MCP tool with identical arguments more than twice.
- job_offers_sponsorship in the payload MUST come from get_job_requirements() result field "job_offers_sponsorship". Never set it to true unless the job result explicitly says so. Default is false if not present.
- Do not include the candidate's name in the final response. The response is an internal hiring recommendation — refer to "the candidate" only.
- min_experience_years and required_skills MUST come from get_job_requirements() result. Never invent them."""

# ---------------------------------------------------------------------------
# Delegate tool definition
# ---------------------------------------------------------------------------

DELEGATE_TOOL = {
    "type": "function",
    "function": {
        "name": "delegate_to_specialists",
        "description": (
            "Send the structured application to all three specialist agents "
            "(Recruiter, Culture Fit, Compliance) for parallel assessment. "
            "Call ONCE after gathering job requirements. "
            "Returns combined assessments from all three agents."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "job_id":               {"type": "string"},
                "name":                 {"type": "string"},
                "email":                {"type": "string"},
                "school":               {"type": "string"},
                "graduation_year":      {"type": "integer"},
                "gpa":                  {"type": "number"},
                "years_experience":     {"type": "number"},
                "candidate_skills":     {"type": "array", "items": {"type": "string"}},
                "expected_salary_usd":  {"type": "integer"},
                "requires_sponsorship": {"type": "boolean"},
                "country_code":         {"type": "string"},
                "cover_letter":         {"type": "string"},
                "work_history":         {"type": "string"},
                "summary":              {"type": "string"},
                "min_experience_years": {"type": "integer"},
                "job_offers_sponsorship": {"type": "boolean"},
                "required_skills":      {"type": "array", "items": {"type": "string"}},
                "salary_range_usd":     {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["job_id", "name", "years_experience", "candidate_skills"],
        },
    },
}

# ---------------------------------------------------------------------------
# Main agent loop
# ---------------------------------------------------------------------------

async def run_coordinator(
    job_id: str,
    applicant_request: str,
    verbose: bool = True,
) -> AgentTrace:
    trace = AgentTrace(job_id=job_id, applicant_request=applicant_request)
    trace.log("applicant", applicant_request, "user_request")

    llm = OpenAI(api_key=os.environ.get("SILICONFLOW_API_KEY",""), base_url=SILICONFLOW_BASE)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Job ID: {job_id}\n\nApplication:\n{applicant_request}"},
    ]

    if verbose:
        print(f"\n{'='*62}")
        print(f"Coordinator Agent — session {trace.session_id}")
        print(f"Job: {job_id}  |  {applicant_request[:80]}...")
        print('='*62)

    async with mcp_session() as mcp:
        mcp_tools = await discover_tools(mcp)
        mcp_tool_names = {t["function"]["name"] for t in mcp_tools}
        all_tools = mcp_tools + [DELEGATE_TOOL]

        trace.log("mcp_connect", {
            "server": MCP_SERVER_MODULE, "transport": "MCP / stdio",
            "tools_discovered": sorted(mcp_tool_names),
            "delegate_tool": "delegate_to_specialists (OpenAI tool_use)",
        }, "mcp_connect")

        if verbose:
            print(f"[MCP] Tools: {sorted(mcp_tool_names)}")

        delegated = False
        last_call: tuple | None = None
        repeat_count = 0
        total_counts: dict = {}

        for _turn in range(20):
            response = llm.chat.completions.create(
                model=SILICONFLOW_MODEL,
                max_tokens=2048,
                tools=all_tools,
                messages=messages,
            )
            msg = response.choices[0].message
            text = msg.content or ""
            tool_calls = msg.tool_calls or []

            if text and not tool_calls:
                trace.log("coordinator", text, "thought")
                if verbose:
                    print(f"\n[Coordinator]\n{text}")

            if tool_calls:
                messages.append(msg.model_dump(exclude_none=True))
                for tc in tool_calls:
                    name = tc.function.name
                    raw = tc.function.arguments or "{}"
                    try:
                        inp = json.loads(raw)
                    except json.JSONDecodeError:
                        try:
                            inp = json.loads(_repair_json(raw))
                            if verbose: print(f"[JSON REPAIR] Fixed {name}")
                        except:
                            inp = {}
                    if not isinstance(inp, dict):
                        inp = {}

                    ck = (name, json.dumps(inp, sort_keys=True))
                    total_counts[name] = total_counts.get(name, 0) + 1
                    repeat_count = repeat_count+1 if ck==last_call else 1
                    last_call = ck

                    if repeat_count > 2 or total_counts[name] > 3:
                        result = {"error": f"{name} called too many times. Use existing data."}
                        if verbose: print(f"[GUARD] Blocked: {name}")

                    elif name == "delegate_to_specialists":
                        if delegated:
                            result = {"error": "Already delegated. Do not call again."}
                        else:
                            # Call all three agents (compliance is async-safe to parallelize)
                            compliance_payload = inp.copy()
                            recruiter_payload   = inp.copy()
                            culture_payload     = inp.copy()

                            trace.log("coordinator→compliance", {
                                "to": COMPLIANCE_URL, "protocol": "A2A / JSONRPC",
                                "payload": sanitize_for_compliance(compliance_payload),
                                "stripped": list(COMPLIANCE_STRIP & set(inp.keys())),
                            }, "a2a_send")
                            trace.log("coordinator→recruiter", {
                                "to": RECRUITER_URL, "protocol": "A2A / JSONRPC",
                                "payload": sanitize_for_recruiter(recruiter_payload),
                                "stripped": list(RECRUITER_STRIP & set(inp.keys())),
                            }, "a2a_send")
                            trace.log("coordinator→culture", {
                                "to": CULTURE_URL, "protocol": "A2A / JSONRPC",
                                "payload": sanitize_for_culture(culture_payload),
                                "stripped": list(CULTURE_STRIP & set(inp.keys())),
                            }, "a2a_send")

                            if verbose:
                                print(f"\n[A2A → 3 specialist agents in parallel]")

                            # Sequential — SiliconFlow can't reliably handle
                            # 3 concurrent LLM calls from the same key.
                            compliance_r = await call_compliance(compliance_payload)
                            recruiter_r  = await call_recruiter(recruiter_payload)
                            culture_r    = await call_culture(culture_payload)
                            delegated = True

                            trace.log("compliance→coordinator", compliance_r, "a2a_receive")
                            trace.log("recruiter→coordinator",  recruiter_r,  "a2a_receive")
                            trace.log("culture→coordinator",    culture_r,    "a2a_receive")

                            if verbose:
                                print(f"[A2A ← Compliance]\n{json.dumps(compliance_r, indent=2)}")
                                print(f"[A2A ← Recruiter]\n{json.dumps(recruiter_r, indent=2)}")
                                print(f"[A2A ← Culture Fit]\n{json.dumps(culture_r, indent=2)}")

                            result = {
                                "compliance": compliance_r,
                                "recruiter":  recruiter_r,
                                "culture_fit": culture_r,
                            }

                    elif name in mcp_tool_names:
                        result = await call_mcp_tool(mcp, name, inp)
                        trace.log("coordinator", {"tool": name, "input": inp, "via": "MCP / stdio"}, "tool_call")
                        trace.log("tool_result", {"tool": name, "result": result}, "tool_result")
                        if verbose:
                            print(f"\n[MCP] {name}({json.dumps(inp)}) → {json.dumps(result)}")
                    else:
                        result = {"error": f"Unknown tool: {name}"}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    })
                continue

            if response.choices[0].finish_reason in ("stop", "end"):
                if not delegated and text:
                    messages.append({"role": "assistant", "content": text})
                    messages.append({"role": "user", "content":
                        "You have not yet called delegate_to_specialists. Please call it now."})
                    continue
                if text:
                    messages.append({"role": "assistant", "content": text})
                    trace.final_response = text
                    trace.log("coordinator", text, "final_response")
                    if verbose:
                        print(f"\n[Final Recommendation]\n{text}")
                break

        if not trace.final_response:
            # Synthesise from specialist assessments so the trace is never left empty
            compliance = next(
                (s["content"] for s in trace.steps if s.get("role") == "compliance→coordinator"), {}
            )
            recruiter = next(
                (s["content"] for s in trace.steps if s.get("role") == "recruiter→coordinator"), {}
            )
            culture = next(
                (s["content"] for s in trace.steps if s.get("role") == "culture→coordinator"), {}
            )
            eligible = compliance.get("eligible", "unknown")
            flags = compliance.get("flags", [])
            rec_text = recruiter.get("assessment", "No assessment.")[:300]
            cult_text = culture.get("assessment", "No assessment.")[:300]
            if not eligible:
                decision = "REJECT — candidate does not meet hard eligibility requirements."
            else:
                decision = "ADVANCE — candidate meets eligibility; specialist assessments support moving forward."
            trace.final_response = (
                f"[Synthesised from specialist assessments]\n\n"
                f"Compliance: {'PASS' if eligible else 'FAIL'}"
                + (f" — {'; '.join(flags)}" if flags else "") + "\n\n"
                f"Recruiter:\n{rec_text}\n\n"
                f"Culture Fit:\n{cult_text}\n\n"
                f"Recommendation: {decision}"
            )
            trace.log("coordinator", trace.final_response, "final_response_fallback")

    return trace
