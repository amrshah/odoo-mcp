
u = env['res.users'].sudo().browse(5)
print('User 5 name:', u.name, 'login:', u.login)
print('User 5 groups:', [g.name for g in u.group_ids])
