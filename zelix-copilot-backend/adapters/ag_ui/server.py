"""AG-UI Protocol Server Endpoint Handler.

Provides a standalone, framework-agnostic HTTP/SSE bridge connecting CopilotKit and AG-UI clients
to the Alamia Copilot Engine.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, Iterator, List, Optional
from adapters.ag_ui.events import AGUIEvent, AGUIEventType, InterruptData
from adapters.ag_ui.serializer import AGUISerializer
from core.actions.proposal import ActionProposal, ActionStatus
from core.actions.statemachine import ActionStateMachine
from core.runtime.engine import CopilotEngine
from core.sessions.context import EmployeeContext


class AGUIHandler:
    """Orchestrates AG-UI event generation from CopilotEngine interactions."""

    def __init__(self, engine: CopilotEngine) -> None:
        self.engine = engine
        self._pending_interrupts: Dict[str, tuple[ActionProposal, EmployeeContext]] = {}

    def handle_agent_turn(
        self,
        skill_id: str,
        context: EmployeeContext,
        inputs: Dict[str, Any],
        run_id: str = "run_default",
        thread_id: Optional[str] = None,
    ) -> Iterator[str]:
        """Stream AG-UI protocol events for a skill execution."""
        # 1. RUN_STARTED
        yield AGUISerializer.encode_sse(
            AGUIEvent(
                event_type=AGUIEventType.RUN_STARTED,
                run_id=run_id,
                thread_id=thread_id,
                data={"skill_id": skill_id, "user_id": context.user_id, "role": context.role},
            )
        )

        # 2. STATE_UPDATE (Initial EmployeeContext)
        yield AGUISerializer.encode_sse(
            AGUIEvent(
                event_type=AGUIEventType.STATE_UPDATE,
                run_id=run_id,
                thread_id=thread_id,
                data={"employee_context": context.model_dump()},
            )
        )

        # 3. Execute Skill
        result = self.engine.execute_skill(skill_id, context, **inputs)

        if not result.success:
            yield AGUISerializer.encode_sse(
                AGUIEvent(
                    event_type=AGUIEventType.RUN_ERROR,
                    run_id=run_id,
                    thread_id=thread_id,
                    data={"error": result.error or "Skill execution failed"},
                )
            )
            return

        # 4. Stream text delta output
        if result.output:
            out_str = json.dumps(result.output) if isinstance(result.output, (dict, list)) else str(result.output)
            yield AGUISerializer.encode_sse(
                AGUIEvent(
                    event_type=AGUIEventType.TEXT_DELTA,
                    run_id=run_id,
                    thread_id=thread_id,
                    data={"delta": out_str},
                )
            )

        # 5. Process Proposed Actions / HITL Interrupts
        for raw_proposal in result.proposed_actions:
            proposal = ActionProposal.model_validate(raw_proposal)
            if proposal.status == ActionStatus.AWAITING_CONFIRMATION:
                interrupt_id = f"int_{proposal.action_id}"
                self._pending_interrupts[interrupt_id] = (proposal, context)

                yield AGUISerializer.encode_sse(
                    AGUIEvent(
                        event_type=AGUIEventType.INTERRUPT,
                        run_id=run_id,
                        thread_id=thread_id,
                        data=InterruptData(
                            interrupt_id=interrupt_id,
                            action_proposal=proposal.model_dump(),
                            prompt=f"Confirm action '{proposal.action_type}' for {proposal.target.get('type')}:{proposal.target.get('id')}",
                            options=["Approve", "Reject"],
                        ).model_dump(),
                    )
                )

        # 6. RUN_FINISHED
        yield AGUISerializer.encode_sse(
            AGUIEvent(
                event_type=AGUIEventType.RUN_FINISHED,
                run_id=run_id,
                thread_id=thread_id,
                data={"result": result.model_dump()},
            )
        )

    def resolve_interrupt(self, interrupt_id: str, decision: str) -> Optional[ActionProposal]:
        """Resolve a pending Human-in-the-Loop interrupt."""
        if interrupt_id not in self._pending_interrupts:
            return None

        proposal, context = self._pending_interrupts.pop(interrupt_id)

        if decision.lower() in ("approve", "confirm", "confirmed", "true"):
            ActionStateMachine.transition(proposal, ActionStatus.CONFIRMED)
            return self.engine.execute_action(proposal, context)
        else:
            ActionStateMachine.transition(proposal, ActionStatus.REJECTED, reason="Rejected by human operator.")
            return proposal
