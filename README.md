# Odoo 19 Community + Odoo MCP Server for Clinic/Hospital AI Copilot

This project provides a complete Dockerized setup for **Odoo 19.0 Community** with **PostgreSQL 16** and a high-performance **Odoo FastMCP Server**. It serves as the foundation for building an AI Copilot for Clinic and Hospital Management systems.

---

## 🏗️ Architecture

```mermaid
graph TD
    Copilot["AI Copilot / Client (Claude, Antigravity, Custom Agent)"]
    MCP["Odoo MCP Server (FastMCP / Stdio & SSE)"]
    Odoo["Odoo 19.0 Community (Docker: web)"]
    DB[("PostgreSQL 16 (Docker: db)")]
    Addons["Custom Addons Directory (./addons)<br/>(Ready for Clinic/Hospital Modules)"]

    Copilot <-->|MCP Protocol (Stdio / SSE)| MCP
    MCP <-->|XML-RPC / JSON-RPC API| Odoo
    Odoo <--> DB
    Addons -.->|Mounted into /mnt/extra-addons| Odoo
```

---

## 📁 Directory Structure

```
odoo-mcp/
├── .env                  # Active environment configuration
├── .env.example          # Environment variables template
├── docker-compose.yml    # Multi-container Docker orchestration (Odoo, DB, MCP)
├── config/
│   └── odoo.conf         # Odoo 19 configuration file
├── addons/               # Custom addons directory (Clinic/Hospital modules)
│   └── README.md
├── mcp-server/
│   ├── Dockerfile        # Container definition for MCP Server (SSE mode)
│   ├── requirements.txt  # Python MCP dependencies (fastmcp, mcp, uvicorn)
│   ├── odoo_client.py    # XML-RPC client wrapper with error handling
│   └── server.py         # FastMCP tools exposing Odoo CRUD & methods
└── scripts/
    └── test_mcp.py       # Verification script to test connectivity
```

---

## 🚀 Quick Start

### 1. Start the Containers

Start PostgreSQL, Odoo 19, and the Odoo MCP server:

```powershell
docker compose up -d
```

Check the status of the containers:

```powershell
docker compose ps
```

### 2. Initialize Odoo Database

1. Open your browser and navigate to: **[http://localhost:8069](http://localhost:8069)**
2. Create a new database:
   - **Master Password**: `admin_master_secret` (or value set in `.env`)
   - **Database Name**: `odoo_hospital`
   - **Email / Login**: `admin`
   - **Password**: `admin`
   - **Language**: English
   - **Demo data**: Optional (check if you want sample records)
3. Click **Create Database**.

---

## 🔌 Connecting your AI Copilot via MCP

### Option A: Docker SSE Server Mode (Recommended for Web Copilots & Remote Agents)

When running via Docker Compose, the MCP Server is active on port **8008** with SSE transport:

- **SSE Endpoint**: `http://localhost:8008/sse`

### Option B: Local Stdio Mode (For Claude Desktop, Cursor, Antigravity)

You can run the MCP server directly using Python:

```powershell
cd mcp-server
pip install -r requirements.txt
python server.py --stdio
```

#### Claude Desktop Configuration (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "odoo": {
      "command": "python",
      "args": ["E:\\myapps\\odoo-mcp\\mcp-server\\server.py", "--stdio"],
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_DB": "odoo_hospital",
        "ODOO_USERNAME": "admin",
        "ODOO_PASSWORD": "admin"
      }
    }
  }
}
```

---

## 🛠️ Available MCP Tools

| Tool Name | Description |
|---|---|
| `odoo_status` | Checks Odoo server connectivity, version, and auth status |
| `odoo_list_models` | Search and list available models (e.g., search for `patient`, `partner`, `appointment`) |
| `odoo_get_model_fields` | Inspect fields, data types, required flags, and relations for any model |
| `odoo_search_read` | Query records with domain filters, field selection, offset, limit, and ordering |
| `odoo_read_records` | Fetch details of records by ID list |
| `odoo_create_record` | Create new records (Patients, Appointments, Contacts, Invoices) |
| `odoo_write_record` | Update existing records by ID |
| `odoo_unlink_record` | Delete records by ID |
| `odoo_execute_method` | Trigger business workflow methods (e.g., `action_confirm`, `button_validate`) |
| `odoo_list_modules` | List installed or available Odoo modules |

---

## 🏥 Adding Clinic / Hospital Modules

To expand into a specialized Hospital/Clinic Management System:
1. Place custom Odoo modules inside the [`addons/`](addons/) directory.
2. In Odoo Web UI:
   - Activate **Developer Mode** (Settings > Developer Tools).
   - Go to **Apps** > **Update Apps List**.
   - Search for your clinic module and click **Activate**.
3. The MCP server automatically discovers newly created models and fields without needing changes to the MCP code!
