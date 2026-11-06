"""
Policy Engine and Security Guardrails for Alamia OdooBridge.
Enforces execution modes, delete protection, model-method pair allowlists,
service-account scope boundaries, and fine-grained human role-action-model matrices.
"""

import fnmatch
from typing import Dict, List, Any, Optional
from ..config import BridgeSettings, ExecutionPolicy
from .context import current_principal, PrincipalClaims
from .exceptions import PolicyViolationError, PermissionDeniedError


def matches_any_pattern(name: str, patterns: List[str]) -> bool:
    """Check if a string matches any glob pattern in a list."""
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


# Declarative Role / Action / Model Permission Matrix
ROLE_PERMISSIONS: Dict[str, Dict[str, Any]] = {
    "admin": {
        "description": "System administrator with full operational access",
        "allowed_actions": ["read", "write", "unlink", "execute"],
        "allowed_models": ["*"],
        "denied_models": [],
        "allowed_methods": ["*"],
    },
    "doctor": {
        "description": "Veterinarian / Clinician with clinical and patient management access",
        "allowed_actions": ["read", "write", "execute"],
        "allowed_models": [
            "vet.*",
            "res.partner",
            "crm.lead",
            "product.*",
            "calendar.*",
            "mail.*",
        ],
        "denied_models": [
            "account.move",
            "account.payment",
            "res.company",
            "res.users",
        ],
        "allowed_methods": [
            "vet.appointment:action_confirm",
            "vet.appointment:action_done",
            "vet.appointment:action_cancel",
            "vet.cm.case:get_dashboard_data",
            "vet.cm.case:get_rfp_dashboard_data",
            "crm.lead:action_set_won",
            "crm.lead:action_set_lost",
        ],
    },
    "technician": {
        "description": "Veterinary technician or clinical assistant",
        "allowed_actions": ["read", "write"],
        "allowed_models": [
            "vet.*",
            "product.*",
            "stock.*",
        ],
        "denied_models": [
            "account.*",
            "sale.*",
            "res.users",
            "res.company",
        ],
        "allowed_methods": [],
    },
    "receptionist": {
        "description": "Front-desk receptionist handling bookings and customer records",
        "allowed_actions": ["read", "write", "execute"],
        "allowed_models": [
            "vet.appointment",
            "res.partner",
            "crm.lead",
        ],
        "denied_models": [
            "vet.cm.case",
            "account.*",
            "stock.*",
            "res.users",
            "res.company",
        ],
        "allowed_methods": [
            "vet.appointment:action_confirm",
            "vet.appointment:action_cancel",
        ],
    },
    "viewer": {
        "description": "Read-only auditor or guest",
        "allowed_actions": ["read"],
        "allowed_models": ["*"],
        "denied_models": [
            "account.*",
            "res.users",
        ],
        "allowed_methods": [],
    },
}


class PolicyEngine:
    """Enforces fine-grained operation policies before forwarding calls to Odoo."""

    def __init__(self, settings: BridgeSettings):
        self.settings = settings

    def _get_principal(self) -> Optional[PrincipalClaims]:
        return current_principal.get()

    def _get_role_config(self, role: Optional[str]) -> Dict[str, Any]:
        """Resolve role configuration, falling back to least-privilege viewer."""
        if not role or role not in ROLE_PERMISSIONS:
            return ROLE_PERMISSIONS["viewer"]
        return ROLE_PERMISSIONS[role]

    def check_read(self, model: str) -> None:
        """Verify that read access to the model is permitted."""
        if model in self.settings.disallowed_models:
            raise PolicyViolationError(
                f"Access to administrative model '{model}' is prohibited by security policy",
                details={"model": model, "reason": "model_disallowed"},
            )

        principal = self._get_principal()
        if principal:
            if principal.is_service_only:
                # Service identity check: verify service_scopes
                if "read" not in self.settings.service_scopes and "admin" not in self.settings.service_scopes:
                    raise PermissionDeniedError(
                        f"Service account lacks 'read' scope. Current service scopes: {self.settings.service_scopes}"
                    )
            else:
                # Human principal check: verify role matrix
                role_info = self._get_role_config(principal.role)
                if "read" not in role_info["allowed_actions"]:
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' is not authorized to read records"
                    )
                if matches_any_pattern(model, role_info.get("denied_models", [])):
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' is prohibited from reading '{model}'"
                    )
                if not matches_any_pattern(model, role_info.get("allowed_models", ["*"])):
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' cannot read unpermitted model '{model}'"
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

        principal = self._get_principal()
        if principal:
            if principal.is_service_only:
                # Service identity check: verify service_scopes
                if "write" not in self.settings.service_scopes and "admin" not in self.settings.service_scopes:
                    raise PermissionDeniedError(
                        "Service account is restricted to read-only access. Write operations require 'write' scope "
                        "or a verified human principal token."
                    )
            else:
                # Human principal check: verify role matrix
                role_info = self._get_role_config(principal.role)
                if "write" not in role_info["allowed_actions"]:
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' is not authorized to write to records"
                    )
                if matches_any_pattern(model, role_info.get("denied_models", [])):
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' is prohibited from writing to '{model}'"
                    )
                if not matches_any_pattern(model, role_info.get("allowed_models", ["*"])):
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' cannot write to unpermitted model '{model}'"
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

        principal = self._get_principal()
        if principal:
            if principal.is_service_only:
                # Service identity check: verify service_scopes
                if "unlink" not in self.settings.service_scopes and "admin" not in self.settings.service_scopes:
                    raise PermissionDeniedError(
                        "Service account is not permitted to delete records. "
                        "Delete operations require 'unlink' scope and BRIDGE_ALLOW_UNLINK=True."
                    )
            else:
                # Human principal check: verify role matrix
                role_info = self._get_role_config(principal.role)
                if "unlink" not in role_info["allowed_actions"]:
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' is not authorized to delete records"
                    )
                if matches_any_pattern(model, role_info.get("denied_models", [])):
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' cannot delete from '{model}'"
                    )
                if not matches_any_pattern(model, role_info.get("allowed_models", ["*"])):
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' cannot delete from unpermitted model '{model}'"
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

        principal = self._get_principal()
        if principal:
            if principal.is_service_only:
                # Service identity check: verify service_scopes
                if "execute" not in self.settings.service_scopes and "admin" not in self.settings.service_scopes:
                    raise PermissionDeniedError(
                        "Service account is not permitted to execute business methods. "
                        "Requires 'execute' scope or a verified human principal token."
                    )
            else:
                # Human principal check: verify role matrix
                role_info = self._get_role_config(principal.role)
                if "execute" not in role_info["allowed_actions"]:
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' cannot execute business method '{pair}'"
                    )
                allowed_methods = role_info.get("allowed_methods", [])
                if "*" not in allowed_methods and pair not in allowed_methods:
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' is not permitted to execute '{pair}'"
                    )

    def check_module_inspection(self) -> None:
        """Verify that module inspection is permitted."""
        if "ir.module.module" in self.settings.disallowed_models:
            raise PolicyViolationError(
                "Module inspection is prohibited because 'ir.module.module' is restricted by security policy"
            )
        principal = self._get_principal()
        if principal:
            if principal.is_service_only:
                if "read" not in self.settings.service_scopes and "admin" not in self.settings.service_scopes:
                    raise PermissionDeniedError("Service account lacks 'read' scope for module inspection")
            else:
                role_info = self._get_role_config(principal.role)
                if "read" not in role_info["allowed_actions"]:
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' is not authorized to inspect modules"
                    )
