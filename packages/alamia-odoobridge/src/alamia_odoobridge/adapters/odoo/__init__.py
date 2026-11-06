"""
Odoo Adapter Factory.
Automatically selects and configures the optimal adapter (JSON-2 vs XML-RPC)
with active runtime capability probing on AUTO mode.
"""

import logging
import httpx
from ...config import BridgeSettings, OdooAdapterType
from ...core.interfaces import BaseOdooAdapter
from .xmlrpc import XmlRpcAdapter
from .json2 import Json2Adapter

logger = logging.getLogger("alamia_odoobridge.adapter")


def probe_json2_capability(url: str, api_key: str, timeout: float = 2.0) -> bool:
    """
    Probe the Odoo server to verify if JSON-2 API (Odoo 19+) is available
    and accepts the supplied credentials.
    """
    if not api_key:
        return False
    try:
        clean_url = url.rstrip("/")
        resp = httpx.post(
            f"{clean_url}/json/2/res.users/search_read",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"domain": [], "fields": ["id"], "limit": 1},
            timeout=timeout,
        )
        return resp.status_code == 200
    except Exception as e:
        logger.debug("JSON-2 capability probe error: %s", e)
        return False


def get_adapter(settings: BridgeSettings) -> BaseOdooAdapter:
    """
    Instantiate and return the appropriate Odoo adapter based on settings.
    - OdooAdapterType.JSON2: Uses Odoo 19+ JSON-2 adapter.
    - OdooAdapterType.XMLRPC: Uses classical XML-RPC adapter (Odoo 14-20).
    - OdooAdapterType.AUTO: Actively probes /json/2/res.users/search_read. If JSON-2 is supported
      and accepted, selects Json2Adapter; otherwise safely falls back to XmlRpcAdapter.
    """
    if settings.odoo_adapter == OdooAdapterType.JSON2:
        logger.info("Using Odoo External JSON-2 Adapter")
        return Json2Adapter(
            url=settings.odoo_url,
            db=settings.odoo_db,
            api_key=settings.odoo_password,
            timeout=settings.odoo_timeout_seconds,
        )

    if settings.odoo_adapter == OdooAdapterType.AUTO:
        logger.info("Auto-detecting Odoo RPC protocol capabilities at %s...", settings.odoo_url)
        is_json2 = probe_json2_capability(settings.odoo_url, settings.odoo_password)
        if is_json2:
            logger.info("Detected Odoo 19+ JSON-2 capability with valid Bearer key. Selecting Json2Adapter.")
            return Json2Adapter(
                url=settings.odoo_url,
                db=settings.odoo_db,
                api_key=settings.odoo_password,
                timeout=settings.odoo_timeout_seconds,
            )
        logger.info("JSON-2 probe unfulfilled or refused; selecting XML-RPC Adapter.")

    # Default / XMLRPC fallback
    logger.info("Using Odoo XML-RPC Adapter (supports Odoo 14 - 20)")
    return XmlRpcAdapter(
        url=settings.odoo_url,
        db=settings.odoo_db,
        username=settings.odoo_username,
        password=settings.odoo_password,
        timeout=settings.odoo_timeout_seconds,
    )
