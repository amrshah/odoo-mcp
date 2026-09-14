"""Risk Policy.

Authoritatively classifies and evaluates risk levels on the backend.
"""

from typing import Dict, Optional
from core.policies.base import PolicyEvaluationResult


class RiskLevel:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskPolicy:
    """Evaluates risk levels for action types and operational payloads."""

    def __init__(self, default_risk_map: Optional[Dict[str, str]] = None) -> None:
        self._risk_map: Dict[str, str] = default_risk_map or {
            "get": RiskLevel.LOW,
            "search": RiskLevel.LOW,
            "read": RiskLevel.LOW,
            "create": RiskLevel.MEDIUM,
            "update": RiskLevel.MEDIUM,
            "delete": RiskLevel.HIGH,
            "financial_transfer": RiskLevel.CRITICAL,
            "cancel_booking": RiskLevel.HIGH,
            "mark_paid": RiskLevel.HIGH,
        }

    def evaluate(self, action_type: str, explicit_risk: Optional[str] = None) -> PolicyEvaluationResult:
        """Evaluate backend risk level for a given action."""
        # Backend authority takes precedence over LLM input
        risk = self._risk_map.get(action_type, explicit_risk or RiskLevel.MEDIUM)
        
        return PolicyEvaluationResult(
            allowed=True,
            policy_name="BackendRiskPolicy",
            risk_level=risk,
            reason=f"Action '{action_type}' evaluated with risk level {risk}."
        )
