
admin = env['res.users'].sudo().browse(2)
svc = env['res.users'].sudo().search([('login', '=', 'zelix_service')], limit=1)
if svc and admin:
    svc.sudo().write({'group_ids': [(6, 0, admin.group_ids.ids)]})
    env.cr.commit()
    print('Copied', len(svc.group_ids), 'groups from Admin to zelix_service!')
