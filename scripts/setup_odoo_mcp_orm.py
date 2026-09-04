# ==============================================================================
# Self-Healing ORM Script: Auto-Installs Healthcare Modules & Configures MCP
# ==============================================================================

print("==========================================================")
print("📦 Verifying Healthcare Modules Installation...")
print("==========================================================")

# 0. Provision dedicated Zelix AI Service Account (Decoupled from human administrator)
import os
try:
    User = env['res.users'].sudo()
    service_login = "zelix_service"
    service_pass = os.getenv('ZELIX_SERVICE_PASSWORD', 'zelix_service_secret_key_2026')
    service_user = User.search([('login', '=', service_login)], limit=1)
    if not service_user:
        service_user = User.create({
            'name': 'Zelix AI Service Account',
            'login': service_login,
            'email': 'service@zelix.ai',
            'password': service_pass,
            'groups_id': [(6, 0, [env.ref('base.group_system').id])],
        })
        print("[+] Created dedicated 'zelix_service' system service account.")
    else:
        service_user.write({'password': service_pass})
        print("[+] Verified 'zelix_service' system service account.")
except Exception as e:
    print(f"[*] Note on service user setup: {e}")

target_modules = ['vet_installer', 'stratos_hms', 'zelix_ai', 'mcp_server']
Module = env['ir.module.module'].sudo()

try:
    Module.update_list()
except Exception as e:
    print(f"[*] Note on update_list: {e}")

for mod_name in target_modules:
    mod = Module.search([('name', '=', mod_name)], limit=1)
    if mod and mod.state != 'installed':
        print(f"[*] Installing {mod_name} (current state: {mod.state})...")
        try:
            mod.button_immediate_install()
            print(f"[+] Successfully installed: {mod_name}")
        except Exception as e:
            print(f"[!] Error installing {mod_name}: {e}")
    elif mod and mod.state == 'installed':
        print(f"[*] Upgrading {mod_name} to sync latest views and models...")
        try:
            mod.button_immediate_upgrade()
            print(f"[+] Successfully upgraded: {mod_name}")
        except Exception as e:
            print(f"[!] Error upgrading {mod_name}: {e}")
    else:
        print(f"[!] Module '{mod_name}' not found in module list!")

env.cr.commit()

# 2. Enable MCP master switch
try:
    env['ir.config_parameter'].sudo().set_param('mcp_server.enabled', 'True')
    print("[+] Enabled 'mcp_server.enabled' in ir.config_parameter")
except Exception as e:
    print(f"[!] MCP param error: {e}")

# 3. Register VetCairn, HMS, and Core models if mcp_server is available
try:
    if 'mcp.enabled.model' in env.registry or 'mcp.enabled.model' in env:
        core_models = [
            'res.partner', 'res.users', 'res.company',
            'product.product', 'product.template', 'stock.quant', 'account.move'
        ]
        vet_models = env['ir.model'].sudo().search([('model', '=like', 'vet.%')]).mapped('model')
        hms_models = env['ir.model'].sudo().search([('model', '=like', 'hms.%')]).mapped('model')
        zelix_models = env['ir.model'].sudo().search([('model', '=like', 'zelix.%')]).mapped('model')

        all_models = list(dict.fromkeys(core_models + list(vet_models) + list(hms_models) + list(zelix_models)))
        print(f"[*] Registering {len(all_models)} models (VetCairn + HMS + Zelix + Core) for AI Copilot MCP access...")

        McpModel = env['mcp.enabled.model'].sudo()
        IrModel = env['ir.model'].sudo()

        count = 0
        for model_name in all_models:
            m = IrModel.search([('model', '=', model_name)], limit=1)
            if m:
                exists = McpModel.search([('model_id', '=', m.id)], limit=1)
                if not exists:
                    McpModel.create({
                        'model_id': m.id,
                        'allow_read': True,
                        'allow_write': True,
                        'allow_create': True,
                        'allow_unlink': True,
                        'allow_method_calls': True,
                    })
                count += 1

        env.cr.commit()
        print(f"[SUCCESS] {count} Healthcare models enabled in MCP!")
    else:
        print("[!] Model 'mcp.enabled.model' not active in current registry.")
except Exception as e:
    print(f"[*] Note on MCP model registration: {e}")
