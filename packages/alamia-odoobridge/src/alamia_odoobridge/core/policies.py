"""
Policy Engine and Security Guardrails for Alamia OdooBridge.
Enforces execution modes, delete protection, model-method pair allowlists,
service-account scope boundaries, and explicit allowlist-based human role permissions.
"""

import fnmatch
from typing import Dict, List, Any, Optional
from ..config import BridgeSettings, ExecutionPolicy
from .context import current_principal, PrincipalClaims
from .exceptions import PolicyViolationError, PermissionDeniedError


def matches_any_pattern(name: str, patterns: List[str]) -> bool:
    """Check if a string matches any glob pattern in an explicit allowlist."""
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


# Declarative Role / Action / Model Permission Matrix (Explicit Allowlist-First)
ROLE_PERMISSIONS: Dict[str, Dict[str, Any]] = {
    "admin": {
        "description": "System administrator with broad operational access (governed by identity issuer)",
        "allowed_actions": ["read", "write", "unlink", "execute"],
        "allowed_read_models": ["*"],
        "allowed_write_models": ["*"],
        "allowed_methods": ["*"],
    },
    "doctor": {
        "description": "Veterinarian / Clinician with clinical patient and appointment access",
        "allowed_actions": ["read", "write", "execute"],
        "allowed_read_models": [
            "vet.*",
            "res.partner",
            "crm.lead",
            "product.*",
            "calendar.event",
            "mail.message",
        ],
        "allowed_write_models": [
            "vet.*",
            "res.partner",
            "crm.lead",
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
        "description": "Veterinary technician or clinical assistant with vitals and inventory access",
        "allowed_actions": ["read", "write"],
        "allowed_read_models": [
            "vet.*",
            "product.*",
            "stock.picking",
            "stock.move",
            "stock.lot",
        ],
        "allowed_write_models": [
            "vet.appointment",
            "vet.patient",
        ],
        "allowed_methods": [],
    },
    "receptionist": {
        "description": "Front-desk receptionist handling bookings and customer records",
        "allowed_actions": ["read", "write", "execute"],
        "allowed_read_models": [
            "vet.appointment",
            "vet.patient",
            "res.partner",
            "crm.lead",
            "product.*",
        ],
        "allowed_write_models": [
            "vet.appointment",
            "res.partner",
            "crm.lead",
        ],
        "allowed_methods": [
            "vet.appointment:action_confirm",
            "vet.appointment:action_cancel",
        ],
    },
    "viewer": {
        "description": "Read-only auditor with strict explicit business-model allowlist",
        "allowed_actions": ["read"],
        "allowed_read_models": [
            "vet.patient",
            "vet.appointment",
            "res.partner",
            "product.*",
            "crm.lead",
        ],
        "allowed_write_models": [],
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
                if "read" not in self.settings.service_scopes and "admin" not in self.settings.service_scopes:
                    raise PermissionDeniedError(
                        f"Service account lacks 'read' scope. Current service scopes: {self.settings.service_scopes}"
                    )
            else:
                role_info = self._get_role_config(principal.role)
                if "read" not in role_info["allowed_actions"]:
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' is not authorized to read records"
                    )
                allowed_models = role_info.get("allowed_read_models", [])
                if not matches_any_pattern(model, allowed_models):
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' is not permitted to read '{model}'. "
                        f"Allowed read models: {allowed_models}"
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
                if "write" not in self.settings.service_scopes and "admin" not in self.settings.service_scopes:
                    raise PermissionDeniedError(
                        "Service account is restricted to read-only access. Write operations require 'write' scope "
                        "or a verified human principal token."
                    )
            else:
                role_info = self._get_role_config(principal.role)
                if "write" not in role_info["allowed_actions"]:
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' is not authorized to write to records"
                    )
                allowed_models = role_info.get("allowed_write_models", [])
                if not matches_any_pattern(model, allowed_models):
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' is not permitted to write to '{model}'. "
                        f"Allowed write models: {allowed_models}"
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
                if "unlink" not in self.settings.service_scopes and "admin" not in self.settings.service_scopes:
                    raise PermissionDeniedError(
                        "Service account is not permitted to delete records. "
                        "Delete operations require 'unlink' scope and BRIDGE_ALLOW_UNLINK=True."
                    )
            else:
                role_info = self._get_role_config(principal.role)
                if "unlink" not in role_info["allowed_actions"]:
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' is not authorized to delete records"
                    )
                allowed_models = role_info.get("allowed_write_models", [])
                if not matches_any_pattern(model, allowed_models):
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' cannot delete from '{model}'"
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
                if "execute" not in self.settings.service_scopes and "admin" not in self.settings.service_scopes:
                    raise PermissionDeniedError(
                        "Service account is not permitted to execute business methods. "
                        "Requires 'execute' scope or a verified human principal token."
                    )
            else:
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

    def check_model_discovery(self) -> None:
        """Verify that the caller has permissions to discover models."""
        principal = self._get_principal()
        if principal:
            if principal.is_service_only:
                if "read" not in self.settings.service_scopes and "admin" not in self.settings.service_scopes:
                    raise PermissionDeniedError(
                        f"Service account lacks 'read' scope for model discovery. Current scopes: {self.settings.service_scopes}"
                    )
            else:
                role_info = self._get_role_config(principal.role)
                if "read" not in role_info["allowed_actions"]:
                    raise PermissionDeniedError(
                        f"Principal '{principal.sub}' with role '{principal.role}' is not authorized to list models"
                    )

    def filter_models_for_principal(self, models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter a list of models according to the current principal's role allowlists and system exclusions."""
        principal = self._get_principal()
        allowed_patterns: List[str] = ["*"]
        if principal and not principal.is_service_only:
            role_info = self._get_role_config(principal.role)
            allowed_patterns = role_info.get("allowed_read_models", [])

        filtered = []
        for m in models:
            m_name = m.get("model", "")
            if m_name in self.settings.disallowed_models:
                continue
            if matches_any_pattern(m_name, allowed_patterns):
                filtered.append(m)
        return filtered
