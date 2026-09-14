"""Action Executor module.

Enforces idempotency, permissions, confirmation checks, and dispatches mutations to application adapter.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from core.actions.proposal import ActionProposal, ActionStatus
from core.actions.statemachine import ActionStateMachine


class IdempotencyViolationError(Exception):
    """Raised when an operation with the same idempotency key is re-executed invalidly."""
    pass


class ActionExecutionError(Exception):
    """Raised when an action execution fails or is unauthorized."""
    pass


class ActionExecutor:
    """Coordinates execution of validated ActionProposals."""

    def __init__(self) -> None:
        self._executed_idempotency_keys: Dict[str, ActionProposal] = {}

    def is_already_executed(self, idempotency_key: str) -> bool:
        """Check if an action with the given idempotency key has already executed successfully."""
        existing = self._executed_idempotency_keys.get(idempotency_key)
        return existing is not None and existing.status == ActionStatus.COMPLETED

    def get_executed_action(self, idempotency_key: str) -> Optional[ActionProposal]:
        """Get previously executed action proposal for an idempotency key."""
        return self._executed_idempotency_keys.get(idempotency_key)

    def execute(
        self,
        proposal: ActionProposal,
        adapter: Any,
    ) -> ActionProposal:
        """Execute the ActionProposal against the given application adapter with idempotency guarantee."""
        # 1. Check idempotency
        if proposal.idempotency_key in self._executed_idempotency_keys:
            existing = self._executed_idempotency_keys[proposal.idempotency_key]
            if existing.status == ActionStatus.COMPLETED:
                # Return cached result without re-executing
                return existing
            elif existing.status in (ActionStatus.EXECUTING, ActionStatus.FAILED):
                raise IdempotencyViolationError(
                    f"Action with idempotency key '{proposal.idempotency_key}' is in state {existing.status.value}."
                )

        # 2. Check confirmation requirement
        if proposal.requires_confirmation and proposal.status != ActionStatus.CONFIRMED:
            raise ActionExecutionError(
                f"Action '{proposal.action_id}' requires confirmation before execution (current status: {proposal.status.value})."
            )

        # 3. Transition to EXECUTING
        if proposal.status != ActionStatus.CONFIRMED:
            # If confirmation was not required, transition from PROPOSED -> CONFIRMED -> EXECUTING
            if proposal.status == ActionStatus.PROPOSED:
                ActionStateMachine.transition(proposal, ActionStatus.CONFIRMED)
        
        ActionStateMachine.transition(proposal, ActionStatus.EXECUTING)
        self._executed_idempotency_keys[proposal.idempotency_key] = proposal

        # 4. Dispatch to ApplicationAdapter
        try:
            result = adapter.execute(
                action_type=proposal.action_type,
                target=proposal.target,
                proposed_changes=proposal.proposed_changes,
                metadata=proposal.metadata,
            )
            proposal.result = result
            proposal.executed_at = datetime.now(timezone.utc).isoformat()
            ActionStateMachine.transition(proposal, ActionStatus.COMPLETED)
            return proposal
        except Exception as ex:
            proposal.error = str(ex)
            ActionStateMachine.transition(proposal, ActionStatus.FAILED, reason=str(ex))
            raise ActionExecutionError(f"Execution failed for action '{proposal.action_id}': {ex}") from ex
