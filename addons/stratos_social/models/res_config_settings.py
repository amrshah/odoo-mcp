from odoo import api, fields, models

from .meta_api import DEFAULT_GRAPH_VERSION


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    stratos_social_meta_app_id = fields.Char(
        'Meta App ID', config_parameter='stratos_social.meta_app_id')
    stratos_social_meta_app_secret = fields.Char(
        'Meta App Secret', config_parameter='stratos_social.meta_app_secret')
    stratos_social_meta_graph_version = fields.Char(
        'Graph API Version', config_parameter='stratos_social.meta_graph_version',
        default=DEFAULT_GRAPH_VERSION)
    stratos_social_redirect_uri = fields.Char(
        'Valid OAuth Redirect URI', compute='_compute_stratos_social_redirect_uri')
    stratos_social_google_client_id = fields.Char(
        'Google Client ID', config_parameter='stratos_social.google_client_id')
    stratos_social_google_client_secret = fields.Char(
        'Google Client Secret', config_parameter='stratos_social.google_client_secret')
    stratos_social_google_redirect_uri = fields.Char(
        'Authorized Redirect URI', compute='_compute_stratos_social_redirect_uri')
    stratos_social_tiktok_client_key = fields.Char(
        'TikTok Client Key', config_parameter='stratos_social.tiktok_client_key')
    stratos_social_tiktok_client_secret = fields.Char(
        'TikTok Client Secret', config_parameter='stratos_social.tiktok_client_secret')
    stratos_social_tiktok_audited = fields.Boolean(
        'TikTok App Audited', config_parameter='stratos_social.tiktok_audited',
        help='Tick only after TikTok approves your app for public Direct Post. Before that, TikTok only accepts "Only me" posts.')
    stratos_social_tiktok_redirect_uri = fields.Char(
        'TikTok Redirect URI', compute='_compute_stratos_social_redirect_uri')

    @api.depends('company_id')
    def _compute_stratos_social_redirect_uri(self):
        base_url = self.env['ir.config_parameter'].sudo().get_str('web.base.url') or ''
        for settings in self:
            settings.stratos_social_redirect_uri = '%s/stratos_social/meta/callback' % base_url.rstrip('/')
            settings.stratos_social_google_redirect_uri = '%s/stratos_social/google/callback' % base_url.rstrip('/')
            settings.stratos_social_tiktok_redirect_uri = '%s/stratos_social/tiktok/callback' % base_url.rstrip('/')
