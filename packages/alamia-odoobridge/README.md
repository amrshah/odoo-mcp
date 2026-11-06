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

### 1. Run with `stdio` (Claude Desktop / Cursor)
```json
{
  "mcpServers": {
    "odoo": {
      "command": "uvx",
      "args": [
        "alamia-odoobridge",
        "--url", "https://your-odoo.com",
        "--db", "your_db",
        "--user", "ai_service",
        "--password", "your_secret_password"
      ]
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
