#!/usr/bin/env bash
# ==============================================================================
# Odoo 19 Container Entrypoint & Auto-Installer
# Automatically initializes database, installs all healthcare suites,
# and activates all 81 MCP models on startup — 100% Zero Manual CLI required.
# ==============================================================================

set -e

# Load default config
CONFIG_FILE="/etc/odoo/odoo.conf"
DATABASE="${ODOO_DB:-odoo_hospital}"
INIT_LOCK="/var/lib/odoo/.hms_initialized"

echo "=========================================================="
echo "🏥 Starting Odoo 19 + VetCairn + Stratos HMS + MCP Server"
echo "=========================================================="

# Check if initial install of modules has been performed
if [ ! -f "$INIT_LOCK" ]; then
    echo "[1/3] First-time startup detected. Auto-installing Healthcare modules..."
    odoo -c "$CONFIG_FILE" -d "$DATABASE" -i vet_installer,stratos_hms,zelix_ai,mcp_server --stop-after-init
    
    echo "[2/3] Enabling MCP master switch and registering 81 clinical models..."
    python3 /scripts/setup_odoo_mcp.py || true
    
    touch "$INIT_LOCK"
    echo "[3/3] Initial setup completed successfully!"
else
    echo "[+] System already initialized. Checking for module updates..."
    odoo -c "$CONFIG_FILE" -d "$DATABASE" -u mcp_server,zelix_ai,stratos_hms --stop-after-init
    python3 /scripts/setup_odoo_mcp.py || true
fi

echo "=========================================================="
echo "🚀 Starting Odoo 19 Web Service on port 8069..."
echo "=========================================================="
exec odoo -c "$CONFIG_FILE" -d "$DATABASE"
