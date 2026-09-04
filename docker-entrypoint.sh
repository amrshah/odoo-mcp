#!/usr/bin/env bash
# ==============================================================================
# Robust Container Entrypoint for Odoo 19 Healthcare Stack
# ==============================================================================

set -e

CONFIG_FILE="/etc/odoo/odoo.conf"
DATABASE="${ODOO_DB:-odoo_hospital}"
INIT_LOCK="/var/lib/odoo/.hms_initialized"

# Ensure config file exists
if [ ! -f "$CONFIG_FILE" ] || [ ! -s "$CONFIG_FILE" ]; then
    mkdir -p /etc/odoo
    cat <<EOF > "$CONFIG_FILE"
[options]
addons_path = /usr/lib/python3/dist-packages/odoo/addons,/var/lib/odoo/addons/19.0,/mnt/extra-addons,/mnt/extra-addons/VetCairn
data_dir = /var/lib/odoo
admin_passwd = ${ADMIN_PASSWORD:-admin_master_secret}
db_host = ${HOST:-db}
db_port = ${PORT:-5432}
db_user = ${USER:-odoo}
db_password = ${PASSWORD:-odoo_db_password_123}
proxy_mode = True
limit_time_cpu = 600
limit_time_real = 1200
limit_memory_hard = 2684354560
limit_memory_soft = 2147483648
EOF
fi

export ODOO_RC="$CONFIG_FILE"

echo "=========================================================="
echo "🏥 Starting Odoo 19 Healthcare Stack (1-Click Deployment)"
echo "=========================================================="

# 1. Wait for Postgres database
echo "[*] Waiting for PostgreSQL at ${HOST:-db}:${PORT:-5432}..."
until pg_isready -h "${HOST:-db}" -p "${PORT:-5432}" -U "${USER:-odoo}" >/dev/null 2>&1; do
    echo "    Postgres not ready yet, retrying in 2 seconds..."
    sleep 2
done
echo "[+] PostgreSQL connection established!"

# 2. First-time auto install vs update
if [ ! -f "$INIT_LOCK" ]; then
    echo "[1/3] First-time startup detected. Auto-installing Healthcare modules..."
    odoo -c "$CONFIG_FILE" -d "$DATABASE" -i vet_installer,stratos_hms,zelix_ai,mcp_server --stop-after-init
    
    echo "[2/3] Enabling MCP master switch and registering 81 clinical models..."
    if [ -f "/scripts/setup_odoo_mcp.py" ]; then
        python3 /scripts/setup_odoo_mcp.py || true
    fi
    
    touch "$INIT_LOCK"
    echo "[3/3] Initial setup completed successfully!"
else
    echo "[+] System already initialized. Ensuring MCP models are registered..."
    if [ -f "/scripts/setup_odoo_mcp.py" ]; then
        python3 /scripts/setup_odoo_mcp.py || true
    fi
fi

echo "=========================================================="
echo "🚀 Starting Odoo 19 Web Service on port 8069..."
echo "=========================================================="
exec odoo -c "$CONFIG_FILE" -d "$DATABASE"
