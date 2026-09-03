# Operational Lessons & Troubleshooting

## 1. Port Collisions on Windows/Docker
- **Observation:** Host port `8000` is frequently occupied by other local development web services or backends.
- **Resolution:** Dedicated MCP Server is configured to use host port `8008` (`MCP_SERVER_PORT=8008`) across `.env`, `docker-compose.yml`, and `Dockerfile`.

## 2. Python 3.12 PEP 668 in Debian Containers
- **Observation:** Running `pip install` inside Debian 12 / Python 3.12 containers raises `error: externally-managed-environment`.
- **Resolution:** When installing requirements inside the running Odoo container, pass `--break-system-packages` (e.g. `pip3 install --break-system-packages -r requirements.txt`).

## 3. Demo Data Dependencies on Accounting Journals
- **Observation:** Installing `vet_demo_data` on a fresh database without a configured Chart of Accounts raises `UserError: No journal could be found in company My Company for any of those types: sale` during demo invoice creation.
- **Resolution:** Install `vet_installer` first, configure standard chart of accounts / sales journals, and then install `vet_demo_data` or create records directly through MCP.

## 4. MCP 2.x Package Migration
- **Observation:** In `mcp 2.x`, `mcp.server.fastmcp` was deprecated/moved, and the standalone `fastmcp` package (version 4.x) should be imported directly (`from fastmcp import FastMCP`).
- **Resolution:** Import `FastMCP` directly from `fastmcp` and specify `host` and `port` in `mcp.run(transport="sse", host=host, port=port)`.

## 5. In-Memory ORM Registry Reload
- **Observation:** After installing custom addons from the CLI (`odoo -i <module> --stop-after-init`), running background web worker processes must be restarted to refresh their in-memory model registry.
- **Resolution:** Run `docker compose restart web` after installing new modules to ensure all XML-RPC/HTTP endpoints see the new models immediately.
