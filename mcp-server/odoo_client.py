"""
Odoo XML-RPC Client helper for MCP Server.
Delegates to the canonical alamia_odoobridge package.
"""

import sys
from pathlib import Path

try:
    from alamia_odoobridge import OdooClient
except ImportError:
    bridge_src = Path(__file__).resolve().parent.parent / "packages" / "alamia-odoobridge" / "src"
    if bridge_src.exists() and str(bridge_src) not in sys.path:
        sys.path.insert(0, str(bridge_src))
    from alamia_odoobridge import OdooClient

__all__ = ["OdooClient"]
