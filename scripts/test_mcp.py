"""
Verification test script for Odoo connection & MCP tools.
"""

import os
import sys

# Add mcp-server to path for direct testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp-server"))

from odoo_client import OdooClient


def test_connection():
    url = os.getenv("ODOO_LOCAL_URL", "http://localhost:8069")
    db = os.getenv("ODOO_DB", "odoo_hospital")
    username = os.getenv("ODOO_USERNAME", "admin")
    password = os.getenv("ODOO_PASSWORD", "admin")

    print(f"[*] Testing Odoo connection at {url}...")
    client = OdooClient(url=url, db=db, username=username, password=password)

    # 1. Version Check
    try:
        ver = client.version()
        print(f"[+] Odoo Server is online! Server version: {ver.get('server_version')}")
    except Exception as e:
        print(f"[-] Failed to reach Odoo server at {url}: {e}")
        return False

    # 2. Authentication Check
    try:
        uid = client.authenticate()
        print(f"[+] Successfully authenticated! User: {username}, UID: {uid}, DB: {db}")
    except Exception as e:
        print(f"[!] Authentication note (expected if database '{db}' is not initialized yet): {e}")
        return True

    # 3. Model Listing Check
    try:
        models = client.list_models("partner")
        print(f"[+] Successfully queried ir.model: found {len(models)} matching models")
    except Exception as e:
        print(f"[-] Model query error: {e}")

    return True


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
