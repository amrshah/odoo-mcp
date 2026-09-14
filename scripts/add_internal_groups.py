
u = env['res.users'].sudo().browse(5)
excluded = [env.ref('base.group_portal').id, env.ref('base.group_public').id]
valid_groups = env['res.groups'].sudo().search([('id', 'not in', excluded)]).ids
u.sudo().write({'group_ids': [(6, 0, valid_groups)]})
env.cr.commit()
print('Total valid internal groups on zelix_service:', len(u.group_ids))
