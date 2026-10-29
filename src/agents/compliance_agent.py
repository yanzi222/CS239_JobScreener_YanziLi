"""
Compliance Agent — deterministic A2A service (port 9101).

Checks hard legal and policy rules that cannot be delegated to an LLM:
- Work authorization / sponsorship eligibility
- Minimum experience requirement
- Salary expectation within posted range
- No disqualifying flags

This agent is intentionally deterministic (no LLM) — legal compliance
must be predictable, auditable, and immune to LLM hallucination.
The A2A boundary separates it from the LLM agents; the implementation
inside is rule-based, exactly as the course tutorial's RemoteReviewer shows.
"""
from __future__ import annotations
import argparse
import json
import uvicorn
from a2a.helpers import get_message_text, new_task_from_user_message, new_text_message, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.types import AgentCard, AgentCapabilities, AgentInterface, AgentSkill, TaskState
from starlette.applications import Starlette
from dataclasses import dataclass, field


@dataclass
class ComplianceResult:
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    triggered_rules: list[str] = field(default_factory=list)


# Prohibited fields — Compliance only needs work auth and experience
PROHIBITED_FOR_COMPLIANCE = {
    "name", "email", "phone", "address",
    "gender", "ethnicity", "nationality_name",
    "school", "university", "graduation_year",
    "gpa", "photo_url", "linkedin_url",
}


def _assert_sanitized(payload: dict) -> None:
    found = PROHIBITED_FOR_COMPLIANCE & set(payload.keys())
    if found:
        raise ValueError(
            f"COMPLIANCE VIOLATION: prohibited PII fields present: {found}. "
            "Coordinator must strip these before sending to Compliance Agent."
        )


def run_compliance_checks(payload: dict) -> ComplianceResult:
    """Apply hard eligibility rules. All checks are deterministic."""
    _assert_sanitized(payload)

    result = ComplianceResult(eligible=True)

    # Rule C1: Work authorization
    requires_sponsorship = payload.get("requires_sponsorship", False)
    job_offers_sponsorship = payload.get("job_offers_sponsorship", False)
    if requires_sponsorship and not job_offers_sponsorship:
        result.eligible = False
        result.flags.append("Candidate requires sponsorship; position does not offer it.")
        result.triggered_rules.append("COMPLIANCE-C1")

    # Rule C2: Minimum experience
    years_required = payload.get("min_experience_years", 0)
    years_actual = payload.get("years_experience", 0)
    if years_actual < years_required:
        result.eligible = False
        result.flags.append(
            f"Insufficient experience: {years_actual} years provided, "
            f"{years_required} required."
        )
        result.triggered_rules.append("COMPLIANCE-C2")

    # Rule C3: Salary expectation in range
    expected_salary = payload.get("expected_salary_usd")
    salary_range = payload.get("salary_range_usd", [0, 999999])
    if expected_salary is not None:
        if expected_salary < salary_range[0] * 0.9 or expected_salary > salary_range[1] * 1.1:
            result.flags.append(
                f"Salary expectation ${expected_salary:,} is outside posted "
                f"range ${salary_range[0]:,}–${salary_range[1]:,}."
            )
            result.triggered_rules.append("COMPLIANCE-C3")
            # Salary mismatch is a flag, not a hard disqualifier

    # Rule C4: Required skills present
    required_skills = set(s.lower() for s in payload.get("required_skills", []))
    candidate_skills = set(s.lower() for s in payload.get("candidate_skills", []))
    missing = required_skills - candidate_skills
    if missing:
        result.flags.append(f"Missing required skills: {', '.join(sorted(missing))}.")
        result.triggered_rules.append("COMPLIANCE-C4")
        # Missing skills are a flag for LLM agents to weigh, not a hard disqualifier

    if result.eligible and not result.flags:
        result.reasons.append("All hard eligibility criteria met.")
        result.triggered_rules.append("COMPLIANCE-PASS")

    return result


# ---------------------------------------------------------------------------
# A2A Executor
# ---------------------------------------------------------------------------

class ComplianceExecutor(AgentExecutor):

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
            message=new_text_message("Compliance Agent: running eligibility checks."),
        )

        try:
            raw = get_message_text(context.message)
            payload = json.loads(raw)
            result = run_compliance_checks(payload)
            output = {
                "eligible": result.eligible,
                "reasons": result.reasons,
                "flags": result.flags,
                "triggered_rules": result.triggered_rules,
                "reviewed_by": "Compliance Agent (deterministic)",
            }
        except Exception as exc:
            output = {
                "eligible": False,
                "reasons": [],
                "flags": [f"Compliance check error: {exc}"],
                "triggered_rules": ["COMPLIANCE-ERROR"],
                "reviewed_by": "Compliance Agent (deterministic)",
            }

        await updater.add_artifact(
            parts=[new_text_part(text=json.dumps(output), media_type="application/json")]
        )
        await updater.update_status(
            TaskState.TASK_STATE_COMPLETED,
            message=new_text_message("Compliance check complete."),
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError


def make_app(port: int) -> Starlette:
    card = AgentCard(
        name="Job Application Compliance Agent",
        description=(
            "Runs hard legal eligibility checks: work authorization, "
            "minimum experience, salary range. Deterministic — no LLM. "
            "Validates that prohibited PII fields are absent."
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
        skills=[
            AgentSkill(id="eligibility-check", name="Check eligibility",
                description="Hard rules: sponsorship, experience, salary.", tags=["compliance"]),
        ],
    )
    handler = DefaultRequestHandler(
        agent_executor=ComplianceExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    return Starlette(routes=(
        create_agent_card_routes(card) + create_jsonrpc_routes(handler, "/")
    ))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compliance Agent A2A service")
    parser.add_argument("--port", type=int, default=9101)
    args = parser.parse_args()
    print(f"Starting Compliance Agent on port {args.port}...")
    uvicorn.run(make_app(args.port), host="127.0.0.1", port=args.port, log_level="info")
