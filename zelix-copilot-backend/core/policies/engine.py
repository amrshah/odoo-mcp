"""
core/policies/engine.py
Deterministic Policy Engine evaluating RBAC, risk ratings, and confirmation requirements.
"""

from typing import List, Optional
from core.sessions.context import EmployeeContext
from core.actions.proposal import ActionProposal, RiskLevel
from core.policies.confirmation import ConfirmationPolicy


class PolicyEngine:
    """Evaluates security, permission boundaries, and risk compliance."""

    def __init__(self, confirmation_policy: Optional[ConfirmationPolicy] = None) -> None:
        self.confirmation_policy = confirmation_policy or ConfirmationPolicy()

    def evaluate_action(self, context: EmployeeContext, proposal: ActionProposal) -> ActionProposal:
        """Applies confirmation policies and verifies caller permissions."""
        # 1. Enforce confirmation policy
        if self.confirmation_policy.requires_confirmation(proposal.action_type) or proposal.risk_level == RiskLevel.HIGH:
            proposal.requires_confirmation = True

        # 2. Check permission if specified
        if proposal.required_permission:
            has_perm = (
                proposal.required_permission in context.permissions
                or "all" in context.permissions
                or context.role in ["veterinarian", "doctor", "practice_manager", "admin"]
            )
            if not has_perm:
                proposal.requires_confirmation = True

        return proposal

    def check_permission(self, context: EmployeeContext, required_permission: str) -> bool:
        if not required_permission or "all" in context.permissions:
            return True
        return required_permission in context.permissions
