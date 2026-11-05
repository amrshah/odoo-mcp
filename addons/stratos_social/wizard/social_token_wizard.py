from odoo import fields, models, _
from odoo.exceptions import UserError

from ..models.meta_api import MetaApiError, MetaGraphClient


class StratosSocialTokenWizard(models.TransientModel):
    """Connect pages by pasting a user access token (e.g. from Meta's
    Graph API Explorer). Useful for testing before the Meta app is reviewed."""
    _name = 'stratos.social.token.wizard'
    _description = 'Add Social Accounts with Access Token'

    user_token = fields.Char('User Access Token', required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)

    def action_connect(self):
        self.ensure_one()
        if not self.env.user.has_group('stratos_social.group_social_manager'):
            raise UserError(_('Only Social Marketing administrators can connect accounts.'))
        client = MetaGraphClient.from_env(self.env)
        token = self.user_token.strip()
        try:
            try:
                token = client.long_lived_user_token(token)
            except MetaApiError:
                pass  # keep the short token; pages will still connect
            pages = client.list_pages(token)
        except MetaApiError as e:
            raise UserError(_('Meta refused the token:\n%s', e)) from e
        if not pages:
            raise UserError(_(
                'This token has no Facebook Pages. When generating it, grant: %s, and select your Page.',
                'pages_show_list, pages_manage_posts, pages_read_engagement, instagram_basic, '
                'instagram_content_publish'))
        accounts = self.env['stratos.social.account']._sync_meta_pages(pages, self.company_id)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Connected Accounts'),
            'res_model': 'stratos.social.account',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', accounts.ids)],
        }
