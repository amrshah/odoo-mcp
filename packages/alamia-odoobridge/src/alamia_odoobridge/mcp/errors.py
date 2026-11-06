"""
Standardized MCP error formatting.
Ensures tool failures communicate proper error semantics to AI agents instead of false success dictionaries.
"""

from typing import Any, Dict
from ..core.exceptions import OdooBridgeError


def format_mcp_error(e: Exception) -> Dict[str, Any]:
    """Convert an exception into a standardized MCP tool error structure."""
    if isinstance(e, OdooBridgeError):
        return {
            "error": True,
            "code": e.code,
            "message": e.message,
            "details": e.details,
        }
    return {
        "error": True,
        "code": "INTERNAL_ERROR",
        "message": str(e),
        "details": {},
    }
