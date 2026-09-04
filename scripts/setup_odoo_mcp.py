"""
Helper script to configure in-Odoo mcp_server module:
- Enables the MCP master switch (mcp_server.enabled = True)
- Automatically enables all VetCairn veterinary models (vet.patient, vet.appointment, vet.encounter, etc.) for full MCP CRUD operations
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp-server"))
from odoo_client import OdooClient


def setup_in_app_mcp():
    url = os.getenv("ODOO_LOCAL_URL", "http://localhost:8069")
    db = os.getenv("ODOO_DB", "odoo_hospital")
    username = os.getenv("ODOO_USERNAME", "admin")
    password = os.getenv("ODOO_PASSWORD", "admin")

    client = OdooClient(url=url, db=db, username=username, password=password)
    uid = client.authenticate()
    print(f"[+] Authenticated as {username} (UID: {uid}) on DB: {db}")

    # 1. Enable master switch in ir.config_parameter
    client.execute_kw(
        "ir.config_parameter",
        "set_param",
        ["mcp_server.enabled", "True"],
    )
    print("[+] Enabled 'mcp_server.enabled' in ir.config_parameter")

    # 2. Find all VetCairn and Stratos HMS models and standard models to expose to AI Copilot
    core_models = ["res.partner", "res.users", "res.company", "product.product", "product.template", "stock.quant", "account.move"]
    vet_models = client.execute_kw(
        "ir.model",
        "search_read",
        [[["model", "like", "vet."]]],
        {"fields": ["id", "model", "name"]},
    )
    hms_models = client.execute_kw(
        "ir.model",
        "search_read",
        [[["model", "like", "hms."]]],
        {"fields": ["id", "model", "name"]},
    )
    
    all_models_to_enable = list(dict.fromkeys(core_models + [m["model"] for m in vet_models] + [m["model"] for m in hms_models]))
    print(f"[*] Registering {len(all_models_to_enable)} models (VetCairn + HMS + Core) for AI Copilot MCP access...")

    enabled_count = 0
    for model_name in all_models_to_enable:
        model_record = client.execute_kw(
            "ir.model",
            "search_read",
            [[["model", "=", model_name]]],
            {"fields": ["id", "name"]},
        )
        if model_record:
            model_id = model_record[0]["id"]
            existing = client.execute_kw(
                "mcp.enabled.model",
                "search",
                [[["model_id", "=", model_id]]],
            )
            if not existing:
                client.execute_kw(
                    "mcp.enabled.model",
                    "create",
                    [{
                        "model_id": model_id,
                        "allow_read": True,
                        "allow_write": True,
                        "allow_create": True,
                        "allow_unlink": True,
                        "allow_method_calls": True,
                    }],
                )
                enabled_count += 1
                print(f"  [+] Enabled: {model_name} ({model_record[0]['name']})")
            else:
                enabled_count += 1

    print(f"\n[SUCCESS] {enabled_count} models are fully active and available via MCP for AI Copilot!")


if __name__ == "__main__":
    setup_in_app_mcp()
