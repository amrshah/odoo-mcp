"""Permission Policy.

Evaluates user and context permissions strictly on the backend.
Never trusts LLM claims of permission.
"""

from typing import Optional
from core.policies.base import PolicyEvaluationResult
from core.sessions.context import EmployeeContext


class PermissionPolicy:
    """Evaluates whether an actor has sufficient permissions to perform an operation."""

    def __init__(self, name: str = "BackendPermissionPolicy") -> None:
        self.name = name

    def evaluate(self, context: EmployeeContext, required_permission: str) -> PolicyEvaluationResult:
        """Evaluate permission against EmployeeContext."""
        if not required_permission:
            return PolicyEvaluationResult(
                allowed=True,
                policy_name=self.name,
                reason="No permission required.",
            )

        has_perm = context.has_permission(required_permission)
        return PolicyEvaluationResult(
            allowed=has_perm,
            policy_name=self.name,
            reason="Permission granted." if has_perm else f"Missing required permission: '{required_permission}'.",
        )
