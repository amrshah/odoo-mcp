"""
Standardized exception hierarchy for Alamia OdooBridge.
"""

from typing import Optional, Any, Dict


class OdooBridgeError(Exception):
    """Base exception for all Alamia OdooBridge errors."""
    def __init__(self, message: str, code: str = "BRIDGE_ERROR", details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class AuthenticationError(OdooBridgeError):
    """Raised when Odoo or Bridge authentication fails."""
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AUTH_FAILED", details=details)


class PermissionDeniedError(OdooBridgeError):
    """Raised when an operation is forbidden by Odoo access controls."""
    def __init__(self, message: str = "Permission denied", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="PERMISSION_DENIED", details=details)


class PolicyViolationError(OdooBridgeError):
    """Raised when an operation violates Bridge security policies (e.g. unvetted delete)."""
    def __init__(self, message: str = "Operation violates security policy", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="POLICY_VIOLATION", details=details)


class ModelNotFoundError(OdooBridgeError):
    """Raised when the specified model does not exist in Odoo."""
    def __init__(self, model: str):
        super().__init__(f"Odoo model '{model}' does not exist", code="MODEL_NOT_FOUND", details={"model": model})


class RecordNotFoundError(OdooBridgeError):
    """Raised when specified record IDs do not exist."""
    def __init__(self, model: str, ids: Any):
        super().__init__(f"Record(s) not found in '{model}': {ids}", code="RECORD_NOT_FOUND", details={"model": model, "ids": ids})


class ConnectionError(OdooBridgeError):
    """Raised when Odoo is unreachable or timed out."""
    def __init__(self, message: str = "Failed to connect to Odoo", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="CONNECTION_ERROR", details=details)
