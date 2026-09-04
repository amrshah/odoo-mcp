#!/usr/bin/env bash
# ==============================================================================
# VPS Bootstrap Script: Initialize Odoo 19, VetCairn, Stratos HMS & 81 MCP Models
# Run this once after launching the Portainer stack on the Hetzner CX43 VPS
# ==============================================================================

set -e

echo "=========================================================="
echo "🚀 Initializing Odoo 19 + Healthcare Suites on Hetzner VPS"
echo "=========================================================="

echo "[1/4] Waiting for Odoo web container to be ready..."
until docker exec odoo_web python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8069/web/health')" 2>/dev/null; do
    echo "      Waiting for Odoo HTTP service (:8069)..."
    sleep 3
done
echo "      [+] Odoo 19 is online!"

echo "[2/4] Installing / Updating VetCairn and Stratos HMS modules..."
docker exec odoo_web odoo -c /etc/odoo/odoo.conf -d odoo_hospital -i vet_installer,stratos_hms,zelix_ai,mcp_server --stop-after-init
echo "      [+] Modules installed successfully!"

echo "[3/4] Enabling MCP Master Switch & Registering 81 Clinical Models..."
docker exec odoo_web python3 /mnt/extra-addons/../scripts/setup_odoo_mcp.py
echo "      [+] 81 Healthcare Models registered in MCP!"

echo "[4/4] Restarting odoo_web to finalize in-memory registries..."
docker restart odoo_web
echo "      [+] Odoo web restarted and fully synchronized!"

echo "=========================================================="
echo "✅ VPS DEPLOYMENT COMPLETED SUCCESSFULLY!"
echo "   - Odoo Web UI:      http://localhost:8069"
echo "   - FastMCP Server:   http://localhost:8008/sse"
echo "   - Zelix Copilot:    http://localhost:8010"
echo "   - Alamia AI Link:   https://ai.alamiaconnect.com"
echo "=========================================================="
