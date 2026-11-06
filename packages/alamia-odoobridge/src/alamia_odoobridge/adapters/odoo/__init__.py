"""
Odoo Adapter Factory.
Automatically selects and configures the optimal adapter (JSON-2 vs XML-RPC).
"""

import logging
from ...config import BridgeSettings, OdooAdapterType
from ...core.interfaces import BaseOdooAdapter
from .xmlrpc import XmlRpcAdapter
from .json2 import Json2Adapter

logger = logging.getLogger("alamia_odoobridge.adapter")


def get_adapter(settings: BridgeSettings) -> BaseOdooAdapter:
    """Instantiate and return the appropriate Odoo adapter based on settings."""
    if settings.odoo_adapter == OdooAdapterType.JSON2:
        logger.info("Using Odoo External JSON-2 Adapter")
        return Json2Adapter(
            url=settings.odoo_url,
            db=settings.odoo_db,
            api_key=settings.odoo_password,
            timeout=settings.odoo_timeout_seconds,
        )

    # In AUTO or XMLRPC mode, default to the robust XML-RPC adapter
    logger.info("Using Odoo XML-RPC Adapter (supports Odoo 14 - 20)")
    return XmlRpcAdapter(
        url=settings.odoo_url,
        db=settings.odoo_db,
        username=settings.odoo_username,
        password=settings.odoo_password,
        timeout=settings.odoo_timeout_seconds,
    )
