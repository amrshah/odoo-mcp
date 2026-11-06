"""
Alamia OdooBridge
The Independent Integration Gateway for Odoo & AI Agents.
"""

from .client import OdooClient
from .config import BridgeSettings, get_settings
from .mcp.server import create_bridge_server

__version__ = "0.1.0"
__author__ = "Alamia AI Team"
__all__ = ["OdooClient", "BridgeSettings", "get_settings", "create_bridge_server"]
