
admin = env['res.users'].sudo().browse(2)
svc = env['res.users'].sudo().search([('login', '=', 'zelix_service')], limit=1)
print('Admin:', admin.login, 'groups count:', len(admin.group_ids if hasattr(admin, 'group_ids') else []))
print('Service:', svc.login if svc else 'None')
if svc:
    admin_groups = env['res.users'].sudo().browse(2).groups_id if hasattr(env['res.users'], 'groups_id') else []
    print('Service groups:', [g.name for g in svc.groups_id] if hasattr(svc, 'groups_id') else 'no groups_id')
