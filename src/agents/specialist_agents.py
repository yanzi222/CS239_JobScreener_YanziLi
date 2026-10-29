"""
Specialist Agents — two LLM-based A2A services.

RecruiterAgent  (port 9102) — scores qualifications and experience.
CultureFitAgent (port 9103) — assesses communication style and motivation.

Both are LLM-based and use the same OpenAI-compatible endpoint as the
Coordinator. They receive SANITIZED application payloads — different
subsets stripped by the Coordinator before each A2A call.

Phase 1: Coordinator forwards full application → agents can see name,
         school, gender indicators → potential bias.
Phase 2: Coordinator strips PII in code → agents physically cannot be biased.
"""
from __future__ import annotations
import argparse
import json
import os
import uvicorn
from openai import OpenAI
from a2a.helpers import get_message_text, new_task_from_user_message, new_text_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.types import AgentCard, AgentCapabilities, AgentInterface, AgentSkill, TaskState
from starlette.applications import Starlette

SILICONFLOW_MODEL = os.environ.get("SILICONFLOW_MODEL", "Qwen/Qwen3-8B")

def _get_llm() -> OpenAI:
    return OpenAI(
        api_key=os.environ.get("SILICONFLOW_API_KEY", ""),
        base_url=os.environ.get("SILICONFLOW_BASE_URL", "https://api.siliconflow.com/v1"),
    )

def _llm_call_sync(system: str, user: str) -> str:
    """Synchronous LLM call — must be run via asyncio.to_thread."""
    llm = _get_llm()
    resp = llm.chat.completions.create(
        model=SILICONFLOW_MODEL,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


async def _llm_call(system: str, user: str) -> str:
    """Run the blocking LLM call in a thread so it doesn't block the event loop."""
    import asyncio
    return await asyncio.to_thread(_llm_call_sync, system, user)

def _make_executor(agent_name: str, system_prompt: str):
    """Factory: creates an AgentExecutor that calls an LLM with the given system prompt."""

    class LLMExecutor(AgentExecutor):
        async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
            task = context.current_task or new_task_from_user_message(context.message)
            if context.current_task is None:
                await event_queue.enqueue_event(task)

            updater = TaskUpdater(
                event_queue=event_queue,
                task_id=task.id,
                context_id=task.context_id,
            )
            await updater.update_status(
                TaskState.TASK_STATE_WORKING,
                message=new_text_message(f"{agent_name}: reviewing application."),
            )

            try:
                raw = get_message_text(context.message)
                payload = json.loads(raw)
                user_msg = (
                    f"Application payload (sanitized):\n```json\n"
                    f"{json.dumps(payload, indent=2)}\n```\n\n"
                    "Provide your assessment."
                )
                assessment = await _llm_call(system_prompt, user_msg)
                output = {
                    "agent": agent_name,
                    "assessment": assessment,
                    "payload_received": payload,
                }
            except Exception as exc:
                output = {
                    "agent": agent_name,
                    "assessment": f"Error: {exc}",
                    "payload_received": {},
                }

            await updater.add_artifact(
                parts=[new_text_part(text=json.dumps(output), media_type="application/json")]
            )
            await updater.update_status(
                TaskState.TASK_STATE_COMPLETED,
                message=new_text_message(f"{agent_name}: assessment complete."),
            )

        async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
            raise NotImplementedError

    return LLMExecutor()

# ---------------------------------------------------------------------------
# Recruiter Agent — assesses qualifications and experience
# ---------------------------------------------------------------------------

RECRUITER_SYSTEM = """You are a Recruiter Agent specializing in technical qualification assessment.

You receive a sanitized job application (name, school, GPA, and graduation year have been
removed). A separate Compliance Agent has already checked hard eligibility rules
(minimum years, required skills as exact strings, sponsorship). Your job is different:
you apply human judgment to interpret qualifications contextually.

Key distinction from Compliance:
- Compliance flags "machine learning" missing as an exact string → hard rule
- You assess whether the candidate's background implies ML capability even without
  that exact phrase (e.g. Bayesian statistics + PyTorch projects = strong ML signal)
- You can recommend ADVANCE even when Compliance raised a flag, if the evidence
  supports it — the hiring manager will weigh both assessments

Evaluate:
1. Skill match — look for transferable skills, implied capabilities, context
2. Experience relevance — quality and relevance matter, not just years
3. Growth trajectory — does the candidate show learning ability?

Output in this format:
SKILL_MATCH: [strong/partial/weak] — [reason, including any inferred capabilities]
EXPERIENCE: [strong/adequate/insufficient] — [contextual assessment]
SCORE: [0-100]
RECOMMENDATION: [advance/hold/reject]
NOTES: [key observations; note if you disagree with any Compliance flags and why]

Do not comment on candidate identity, demographics, or background.
Base your assessment purely on skills, experience, and qualifications shown."""

# ---------------------------------------------------------------------------
# Culture Fit Agent — assesses communication and motivation
# ---------------------------------------------------------------------------

CULTURE_SYSTEM = """You are a Culture Fit Agent specializing in assessing communication
style, motivation, and team alignment.

You receive a sanitized application (name, school, GPA, and graduation year have been
removed by the Coordinator). Assess ONLY what you can see.

Evaluate:
1. Communication clarity — how clearly does the candidate express ideas?
2. Motivation alignment — does their stated motivation fit the role and team?
3. Collaboration signals — does their experience suggest they work well with others?

Output a concise assessment in this format:
COMMUNICATION: [strong/adequate/weak] — [brief reason]
MOTIVATION: [well-aligned/partial/misaligned] — [brief reason]
COLLABORATION: [strong/adequate/unclear] — [brief reason]
RECOMMENDATION: [advance/hold/reject]
NOTES: [any observations about fit only]

Do not comment on, infer, or speculate about candidate identity, demographics, or background.
Base your assessment purely on the content of the application as written."""

# ---------------------------------------------------------------------------
# App factories
# ---------------------------------------------------------------------------

def make_recruiter_app(port: int) -> Starlette:
    card = AgentCard(
        name="Recruiter Agent",
        description=(
            "LLM-based qualification assessor. Receives a sanitized application "
            "(PII stripped) and scores skills and experience."
        ),
        version="1.0.0",
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(streaming=False),
        supported_interfaces=[AgentInterface(
            protocol_binding="JSONRPC",
            url=f"http://127.0.0.1:{port}/",
            protocol_version="1.0",
        )],
        skills=[AgentSkill(id="qualification-review", name="Review qualifications",
            description="Score skills and experience match.", tags=["recruiting"])],
    )
    handler = DefaultRequestHandler(
        agent_executor=_make_executor("Recruiter Agent", RECRUITER_SYSTEM),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    return Starlette(routes=(
        create_agent_card_routes(card) + create_jsonrpc_routes(handler, "/")
    ))


def make_culture_app(port: int) -> Starlette:
    card = AgentCard(
        name="Culture Fit Agent",
        description=(
            "LLM-based culture fit assessor. Receives a sanitized application "
            "(name, school, GPA stripped) and assesses communication and motivation."
        ),
        version="1.0.0",
        default_input_modes=["application/json"],
        default_output_modes=["application/json"],
        capabilities=AgentCapabilities(streaming=False),
        supported_interfaces=[AgentInterface(
            protocol_binding="JSONRPC",
            url=f"http://127.0.0.1:{port}/",
            protocol_version="1.0",
        )],
        skills=[AgentSkill(id="culture-fit-review", name="Review culture fit",
            description="Assess communication style and motivation.", tags=["recruiting"])],
    )
    handler = DefaultRequestHandler(
        agent_executor=_make_executor("Culture Fit Agent", CULTURE_SYSTEM),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    return Starlette(routes=(
        create_agent_card_routes(card) + create_jsonrpc_routes(handler, "/")
    ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", choices=["recruiter", "culture"], required=True)
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    if args.agent == "recruiter":
        port = args.port or 9102
        print(f"Starting Recruiter Agent on port {port}...")
        uvicorn.run(make_recruiter_app(port), host="127.0.0.1", port=port,
                    log_level="info", timeout_keep_alive=600)
    else:
        port = args.port or 9103
        print(f"Starting Culture Fit Agent on port {port}...")
        uvicorn.run(make_culture_app(port), host="127.0.0.1", port=port,
                    log_level="info", timeout_keep_alive=600)
