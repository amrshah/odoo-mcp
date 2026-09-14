"""Confirmation Policy.

Authoritatively dictates whether an action requires explicit human confirmation.
The LLM may never bypass this backend policy.
"""

from typing import Dict, Optional, Set
from core.policies.base import PolicyEvaluationResult
from core.policies.risk import RiskLevel


class ConfirmationPolicy:
    """Evaluates human confirmation requirements based on risk levels and action rules."""

    def __init__(
        self,
        confirmation_risk_threshold: str = RiskLevel.HIGH,
        always_require_confirmation_actions: Optional[Set[str]] = None
    ) -> None:
        self.confirmation_risk_threshold = confirmation_risk_threshold
        self.always_require_confirmation_actions = always_require_confirmation_actions or {
            "delete",
            "cancel_booking",
            "mark_paid",
            "financial_transfer",
            "refund",
            "send_email",
        }

    def evaluate(self, action_type: str, risk_level: str) -> PolicyEvaluationResult:
        """Determine if confirmation is strictly required by backend rules."""
        requires_conf = False
        reason = "Operation does not require explicit confirmation."

        if action_type in self.always_require_confirmation_actions:
            requires_conf = True
            reason = f"Action '{action_type}' is in always-confirm policy list."
        elif risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            requires_conf = True
            reason = f"Risk level {risk_level} meets or exceeds threshold {self.confirmation_risk_threshold}."

        return PolicyEvaluationResult(
            allowed=True,
            policy_name="BackendConfirmationPolicy",
            requires_confirmation=requires_conf,
            risk_level=risk_level,
            reason=reason,
        )
