# Alamia OdooBridge: Client Integration Guide

This guide documents how to connect **Alamia OdooBridge** to various AI frontends, IDEs, and copilot environments, including:
- **Claude Desktop** (Windows / macOS)
- **ChatGPT & OpenAI Custom GPTs**
- **Cursor & Windsurf IDEs**
- **Claude Code CLI**
- **LibreChat & Custom Agent Runtimes**

---

## 1. Claude Desktop Integration

### Why `%APPDATA%\Claude\claude_desktop_config.json` Doesn't Exist Yet
By default, the Claude Desktop Windows installer does not generate `claude_desktop_config.json` until the user configures their first MCP server. 

You can create it automatically by:
1. Clicking **Settings** (`Ctrl + ,`) in Claude Desktop ➔ **Developer** ➔ **Edit Config**. Claude will initialize the directory and open the file.
2. Or running the following PowerShell one-liner:
   ```powershell
   New-Item -ItemType Directory -Force -Path "$env:APPDATA\Claude"; New-Item -ItemType File -Force -Path "$env:APPDATA\Claude\claude_desktop_config.json"
   ```

### Recommended Configuration (stdio Mode)
Add the following into `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "alamia-odoobridge": {
      "command": "python",
      "args": [
        "-m",
        "alamia_odoobridge.cli",
        "--transport",
        "stdio"
      ],
      "cwd": "E:\\myapps\\odoo-mcp\\packages\\alamia-odoobridge",
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_DB": "odoo_hospital",
        "ODOO_USERNAME": "zelix_service",
        "ODOO_PASSWORD": "zelix_service_secret_key_2026",
        "BRIDGE_EXECUTION_POLICY": "controlled_writes",
        "BRIDGE_ALLOW_UNLINK": "false",
        "BRIDGE_ENABLE_SCHEMA_CACHE": "true"
      }
    }
  }
}
```

### Alternative Configuration (Docker Container via SSE)
If you prefer Claude Desktop to communicate with the running Docker container `odoo_mcp` instead of spawning Python:
```json
{
  "mcpServers": {
    "alamia-odoobridge": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://localhost:8008/sse"
      ]
    }
  }
}
```

---

## 2. ChatGPT & OpenAI Custom GPTs Integration

OpenAI's ChatGPT (Custom GPTs / Actions) does not use the raw MCP JSON-RPC protocol directly. Instead, ChatGPT connects to external systems via **OpenAPI 3.1 REST Schemas** (GPT Actions) or via **Responses API / Function Calling**.

### Option A: ChatGPT Custom GPT (GPT Action via Reverse Proxy / Tunnel)
1. Expose `alamia-odoobridge` or Odoo using a secure tunnel (e.g. Cloudflare Tunnel, ngrok, or Tailscale Funnel) if running locally.
2. In the Custom GPT Builder:
   - Go to **Configure** ➔ **Create new action**.
   - Import the OpenAPI schema generated from Alamia OdooBridge (or map the endpoints):
   ```yaml
   openapi: 3.1.0
   info:
     title: Alamia OdooBridge Gateway
     version: 1.0.0
     description: Guarded Odoo ERP connector for ChatGPT.
   servers:
     - url: https://bridge.your-domain.com
   paths:
     /api/odoo/status:
       get:
         operationId: odooStatus
         summary: Check Odoo connection and active database.
         responses:
           '200':
             description: Connection status
     /api/odoo/search:
       post:
         operationId: odooSearchRead
         summary: Search and read Odoo ERP records.
         requestBody:
           required: true
           content:
             application/json:
               schema:
                 type: object
                 properties:
                   model:
                     type: string
                   domain:
                     type: array
                     items: {}
                   fields:
                     type: array
                     items:
                       type: string
                   limit:
                     type: integer
         responses:
           '200':
             description: Matching records
   ```

### Option B: OpenAI Assistants API / Function Calling (Python SDK)
If you are developing a custom agent using the OpenAI Python SDK, map Alamia OdooBridge tools directly into OpenAI tools:

```python
from openai import OpenAI
from alamia_odoobridge.client import OdooClient

odoo = OdooClient(
    url="http://localhost:8069",
    db="odoo_hospital",
    username="zelix_service",
    password="zelix_service_secret_key_2026",
)

tools = [
    {
        "type": "function",
        "function": {
            "name": "odoo_search_read",
            "description": "Query Odoo ERP models (patients, partners, invoices)",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string"},
                    "domain": {"type": "array", "items": {}},
                    "fields": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["model"],
            },
        },
    }
]
```

---

## 3. Cursor & Windsurf IDE Integration

Both **Cursor** and **Windsurf** support MCP servers natively through a project-level or global configuration.

### Project-level Configuration (`.cursor/mcp.json` or `.codeium/windsurf/mcp_config.json`)
Create a file at `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "alamia-odoobridge": {
      "command": "python",
      "args": ["-m", "alamia_odoobridge.cli", "--transport", "stdio"],
      "cwd": "E:\\myapps\\odoo-mcp\\packages\\alamia-odoobridge",
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_DB": "odoo_hospital",
        "ODOO_USERNAME": "zelix_service",
        "ODOO_PASSWORD": "zelix_service_secret_key_2026"
      }
    }
  }
}
```

---

## 4. Claude Code CLI Integration

To add Alamia OdooBridge to the **Claude Code** terminal tool:

```bash
claude mcp add alamia-odoobridge python -m alamia_odoobridge.cli --transport stdio
```

Or connect to the Docker container over SSE:
```bash
claude mcp add alamia-odoobridge --url http://localhost:8008/sse
```

---

## 5. LibreChat & Open-Source Agent Platforms

In `librechat.yaml`:

```yaml
mcpServers:
  alamia-odoobridge:
    type: sse
    url: "http://localhost:8008/sse"
    headers:
      X-Bridge-Principal: "doctor@alamia.ai"
```

---

## 6. Verification Checklist

When any client is connected, ask the assistant:
1. *"What is the status of the Odoo ERP connection?"* ➔ Calls `odoo_status`.
2. *"List all veterinary patient models available in the system."* ➔ Calls `odoo_list_models(filter_term="vet.patient")`.
3. *"Search the database for the first 3 registered partners or clients."* ➔ Calls `odoo_search_read(model="res.partner", limit=3)`.
4. *"Delete record ID 1 from res.partner."* ➔ Must return an execution error explaining that unlinking is disabled by policy.
