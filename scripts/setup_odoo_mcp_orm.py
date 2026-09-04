# ==============================================================================
# ORM Script to configure in-Odoo mcp_server module via odoo shell
# ==============================================================================

try:
    # 1. Enable MCP master switch
    env['ir.config_parameter'].sudo().set_param('mcp_server.enabled', 'True')
    print("[+] Enabled 'mcp_server.enabled' in ir.config_parameter")

    # 2. Register VetCairn, HMS, and Core models
    core_models = [
        'res.partner', 'res.users', 'res.company',
        'product.product', 'product.template', 'stock.quant', 'account.move'
    ]
    vet_models = env['ir.model'].sudo().search([('model', '=like', 'vet.%')]).mapped('model')
    hms_models = env['ir.model'].sudo().search([('model', '=like', 'hms.%')]).mapped('model')

    all_models = list(dict.fromkeys(core_models + list(vet_models) + list(hms_models)))
    print(f"[*] Registering {len(all_models)} models (VetCairn + HMS + Core) for AI Copilot MCP access...")

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
except Exception as e:
    print(f"[WARNING] MCP ORM setup encountered: {e}")
