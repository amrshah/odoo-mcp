"""Policy Engine.

Coordinates backend validation of permissions, risks, and confirmations for proposed operations.
"""

from typing import Optional
from core.actions.proposal import ActionProposal, ActionStatus
from core.policies.confirmation import ConfirmationPolicy
from core.policies.permission import PermissionPolicy
from core.policies.risk import RiskPolicy
from core.sessions.context import EmployeeContext


class PolicyEngine:
    """Evaluates security, permissions, and confirmation requirements."""

    def __init__(
        self,
        permission_policy: Optional[PermissionPolicy] = None,
        risk_policy: Optional[RiskPolicy] = None,
        confirmation_policy: Optional[ConfirmationPolicy] = None,
    ) -> None:
        self.permission_policy = permission_policy or PermissionPolicy()
        self.risk_policy = risk_policy or RiskPolicy()
        self.confirmation_policy = confirmation_policy or ConfirmationPolicy()

    def evaluate_proposal(self, context: EmployeeContext, proposal: ActionProposal) -> ActionProposal:
        """Evaluate an ActionProposal against all backend security policies.
        
        Overwrites any LLM-supplied security bypasses with backend authority.
        """
        # 1. Permission check
        perm_res = self.permission_policy.evaluate(context, proposal.required_permission)
        if not perm_res.allowed:
            proposal.status = ActionStatus.REJECTED
            proposal.error = f"Unauthorized: {perm_res.reason}"
            return proposal

        # 2. Authoritative Risk calculation
        risk_res = self.risk_policy.evaluate(proposal.action_type, proposal.risk_level)
        proposal.risk_level = risk_res.risk_level

        # 3. Authoritative Confirmation check
        conf_res = self.confirmation_policy.evaluate(proposal.action_type, proposal.risk_level)
        proposal.requires_confirmation = conf_res.requires_confirmation

        # 4. Set appropriate status if not already explicitly CONFIRMED or in execution lifecycle
        if proposal.status in (ActionStatus.PROPOSED, ActionStatus.AWAITING_CONFIRMATION):
            if proposal.requires_confirmation:
                proposal.status = ActionStatus.AWAITING_CONFIRMATION
            else:
                proposal.status = ActionStatus.PROPOSED

        return proposal
