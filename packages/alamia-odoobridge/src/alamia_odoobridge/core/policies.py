"""
Policy Engine and Security Guardrails for Alamia OdooBridge.
Enforces execution modes, delete protection, and business method allowlists.
"""

from typing import List, Optional
from ..config import BridgeSettings, ExecutionPolicy
from .exceptions import PolicyViolationError


class PolicyEngine:
    """Enforces fine-grained operation policies before forwarding calls to Odoo."""

    def __init__(self, settings: BridgeSettings):
        self.settings = settings

    def check_read(self, model: str) -> None:
        """Verify that read access to the model is permitted."""
        if model in self.settings.disallowed_models:
            raise PolicyViolationError(
                f"Access to administrative model '{model}' is prohibited by security policy",
                details={"model": model, "reason": "model_disallowed"},
            )

    def check_write(self, model: str) -> None:
        """Verify that create/write access to the model is permitted."""
        if self.settings.execution_policy == ExecutionPolicy.READ_ONLY:
            raise PolicyViolationError(
                f"Write operation on '{model}' rejected: Bridge is running in READ_ONLY mode",
                details={"model": model, "policy": self.settings.execution_policy},
            )

        if model in self.settings.disallowed_models:
            raise PolicyViolationError(
                f"Modifying administrative model '{model}' is prohibited by security policy",
                details={"model": model, "reason": "model_disallowed"},
            )

    def check_unlink(self, model: str, ids: List[int]) -> None:
        """Verify that record deletion is explicitly allowed."""
        if self.settings.execution_policy == ExecutionPolicy.READ_ONLY:
            raise PolicyViolationError(
                "Delete operation rejected: Bridge is running in READ_ONLY mode",
                details={"model": model, "policy": self.settings.execution_policy},
            )

        if not self.settings.allow_unlink:
            raise PolicyViolationError(
                f"Destructive record deletion on '{model}' (IDs: {ids}) is disabled by default. "
                "Set BRIDGE_ALLOW_UNLINK=True in settings to enable.",
                details={"model": model, "ids": ids, "reason": "unlink_disabled"},
            )

        if model in self.settings.disallowed_models:
            raise PolicyViolationError(
                f"Deleting records from administrative model '{model}' is strictly forbidden",
                details={"model": model, "ids": ids},
            )

    def check_method_execution(self, model: str, method: str) -> None:
        """Verify that business method execution is vetted and permitted."""
        if self.settings.execution_policy == ExecutionPolicy.READ_ONLY:
            raise PolicyViolationError(
                f"Method execution '{model}.{method}()' rejected: Bridge is running in READ_ONLY mode",
                details={"model": model, "method": method},
            )

        if model in self.settings.disallowed_models:
            raise PolicyViolationError(
                f"Executing methods on administrative model '{model}' is strictly forbidden",
                details={"model": model, "method": method},
            )

        # In WORKFLOW_EXECUTION or CONTROLLED_WRITES, methods must be allowlisted
        if method not in self.settings.allowed_methods:
            raise PolicyViolationError(
                f"Method '{model}.{method}()' is not in the permitted business methods allowlist. "
                f"Allowed methods: {self.settings.allowed_methods}",
                details={"model": model, "method": method, "allowed": self.settings.allowed_methods},
            )
