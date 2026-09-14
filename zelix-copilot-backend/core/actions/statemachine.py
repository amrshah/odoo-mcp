"""Action State Machine.

Enforces valid state transitions and lifecycle rules for ActionProposals.
"""

from typing import Dict, Set
from core.actions.proposal import ActionProposal, ActionStatus


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class ActionStateMachine:
    """State machine governing ActionProposal lifecycle."""

    VALID_TRANSITIONS: Dict[ActionStatus, Set[ActionStatus]] = {
        ActionStatus.PROPOSED: {
            ActionStatus.AWAITING_CONFIRMATION,
            ActionStatus.CONFIRMED,
            ActionStatus.REJECTED,
            ActionStatus.EXPIRED,
            ActionStatus.FAILED,
        },
        ActionStatus.AWAITING_CONFIRMATION: {
            ActionStatus.CONFIRMED,
            ActionStatus.REJECTED,
            ActionStatus.EXPIRED,
        },
        ActionStatus.CONFIRMED: {
            ActionStatus.EXECUTING,
            ActionStatus.REJECTED,
            ActionStatus.EXPIRED,
        },
        ActionStatus.EXECUTING: {
            ActionStatus.COMPLETED,
            ActionStatus.FAILED,
        },
        ActionStatus.COMPLETED: set(),
        ActionStatus.REJECTED: set(),
        ActionStatus.EXPIRED: set(),
        ActionStatus.FAILED: set(),
    }

    @classmethod
    def can_transition(cls, current_status: ActionStatus, target_status: ActionStatus) -> bool:
        """Check if transition from current_status to target_status is valid."""
        allowed = cls.VALID_TRANSITIONS.get(current_status, set())
        return target_status in allowed

    @classmethod
    def transition(cls, proposal: ActionProposal, target_status: ActionStatus, reason: str = "") -> ActionProposal:
        """Perform state transition or raise InvalidStateTransitionError."""
        if not cls.can_transition(proposal.status, target_status):
            raise InvalidStateTransitionError(
                f"Cannot transition ActionProposal {proposal.action_id} from {proposal.status.value} to {target_status.value}."
            )
        proposal.status = target_status
        if reason:
            proposal.metadata["transition_reason"] = reason
        return proposal
