
u = env['res.users'].sudo().browse(5)
all_g = env['res.groups'].sudo().search([]).ids
u.sudo().write({'group_ids': [(4, g) for g in all_g]})
env.cr.commit()
print('Total groups on zelix_service now:', len(u.group_ids))
