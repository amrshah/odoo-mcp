"""
Policy Engine and Security Guardrails for Alamia OdooBridge.
Enforces execution modes, delete protection, model-method pair allowlists,
and verified human principal role constraints.
"""

from typing import List, Optional
from ..config import BridgeSettings, ExecutionPolicy
from .context import current_principal
from .exceptions import PolicyViolationError, PermissionDeniedError


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
                details={"model": model, "policy": self.settings.execution_policy.value},
            )

        if model in self.settings.disallowed_models:
            raise PolicyViolationError(
                f"Modifying administrative model '{model}' is prohibited by security policy",
                details={"model": model, "reason": "model_disallowed"},
            )

        # Enforce human principal role checks if bound
        principal = current_principal.get()
        if principal and not principal.is_service_only:
            # Example role restriction: read-only roles cannot execute writes
            if principal.role in ("viewer", "guest", "auditor"):
                raise PermissionDeniedError(
                    f"Principal '{principal.sub}' with role '{principal.role}' is not authorized to write to '{model}'"
                )

    def check_unlink(self, model: str, ids: List[int]) -> None:
        """Verify that record deletion is explicitly allowed."""
        if self.settings.execution_policy == ExecutionPolicy.READ_ONLY:
            raise PolicyViolationError(
                "Delete operation rejected: Bridge is running in READ_ONLY mode",
                details={"model": model, "policy": self.settings.execution_policy.value},
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
        """Verify that business method execution is vetted and explicitly allowlisted by model:method."""
        if self.settings.execution_policy == ExecutionPolicy.READ_ONLY:
            raise PolicyViolationError(
                f"Method execution '{model}:{method}' rejected: Bridge is running in READ_ONLY mode",
                details={"model": model, "method": method},
            )

        if model in self.settings.disallowed_models:
            raise PolicyViolationError(
                f"Executing methods on administrative model '{model}' is strictly forbidden",
                details={"model": model, "method": method},
            )

        # Enforce explicit model:method pair allowlisting
        pair = f"{model}:{method}"
        if pair not in self.settings.allowed_methods:
            raise PolicyViolationError(
                f"Method '{pair}' is not in the permitted model:method allowlist. "
                f"Allowed pairs: {self.settings.allowed_methods}",
                details={"model": model, "method": method, "allowed": self.settings.allowed_methods},
            )

        # Enforce human principal role checks if bound
        principal = current_principal.get()
        if principal and not principal.is_service_only:
            if principal.role in ("viewer", "guest", "auditor"):
                raise PermissionDeniedError(
                    f"Principal '{principal.sub}' with role '{principal.role}' cannot execute business method '{pair}'"
                )

    def check_module_inspection(self) -> None:
        """Verify that module inspection is permitted."""
        if "ir.module.module" in self.settings.disallowed_models:
            raise PolicyViolationError(
                "Module inspection is prohibited because 'ir.module.module' is restricted by security policy"
            )
