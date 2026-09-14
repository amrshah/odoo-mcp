
u = env['res.users'].sudo().search([('login', '=', 'zelix_service')], limit=1)
if u:
    all_groups = env['res.groups'].sudo().search([])
    for g in all_groups:
        try:
            g.sudo().write({'users': [(4, u.id)]})
        except Exception:
            pass
    try:
        u.sudo().write({'vet_is_provider': True})
    except Exception:
        pass
    env.cr.commit()
    print('Granted all groups to zelix_service!')
