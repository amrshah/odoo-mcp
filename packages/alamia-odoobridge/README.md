# Alamia OdooBridge

**The Independent Integration Gateway for Odoo & AI Agents.**

Alamia OdooBridge connects AI assistants, autonomous agent swarms, and clinical copilots to Odoo ERP instances through a secure, independently deployable Model Context Protocol (MCP) gateway.

---

## Key Highlights

- **Zero Odoo Runtime Modifications**: Connects externally via standard HTTPS (XML-RPC or Odoo 19+ JSON-2 API). Works out of the box with Odoo 14, 15, 16, 17, 18, 19, and 20.
- **Enterprise Security & Policy Guardrails**:
  - Execution policies: `read_only`, `controlled_writes`, and `workflow_execution`.
  - Destructive delete protection: `unlink` is disabled by default.
  - Safe method execution: restricts model method calls to vetted business workflows.
  - Principal Propagation: forwards caller identity for granular audit logging.
- **Modern MCP Transports**:
  - `stdio`: Seamless integration with local IDEs (Cursor, Claude Desktop, Windsurf).
  - `streamable-http`: Modern standard for remote agents and cloud orchestrators.
  - `sse`: Backward-compatible streaming SSE on port 8008.

---

## Quickstart

### 1. Run with `stdio` (Claude Desktop / Cursor / Windsurf)
See the full [Client Integration Guide](../../docs/Alamia-Odoo-Bridge/client-integrations.md) for step-by-step setup for Claude Desktop, ChatGPT, Cursor, and Claude Code.

Example Claude Desktop config (`%APPDATA%\Claude\claude_desktop_config.json`):
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
        "ODOO_PASSWORD": "zelix_service_secret_key_2026"
      }
    }
  }
}
```

### 2. Run as a Remote SSE / HTTP Gateway (Docker)
```bash
docker run -d -p 8008:8008 \
  -e ODOO_URL="http://web:8069" \
  -e ODOO_DB="odoo_hospital" \
  -e ODOO_USERNAME="zelix_service" \
  -e ODOO_PASSWORD="your_service_password" \
  -e MCP_TRANSPORT="sse" \
  -e BRIDGE_API_KEY="your_secret_bridge_token" \
  alamia-odoobridge:latest
```
