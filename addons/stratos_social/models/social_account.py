import base64
import logging
from datetime import timedelta

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .google_api import GoogleApiError, YouTubeClient
from .meta_api import MetaApiError, MetaGraphClient
from .tiktok_api import TikTokApiError, TikTokClient

_logger = logging.getLogger(__name__)


class StratosSocialAccount(models.Model):
    _name = 'stratos.social.account'
    _description = 'Social Media Account'
    _order = 'platform, name'

    name = fields.Char(required=True)
    platform = fields.Selection([
        ('facebook', 'Facebook Page'),
        ('instagram', 'Instagram Business'),
        ('youtube', 'YouTube Channel'),
        ('tiktok', 'TikTok Account'),
    ], required=True)
    external_id = fields.Char('Platform ID', required=True, readonly=True,
                              help='Facebook Page ID, Instagram Business account ID, YouTube channel ID or TikTok open_id')
    username = fields.Char(readonly=True)
    facebook_page_id = fields.Char('Linked Facebook Page ID', readonly=True,
                                   help='For Instagram: the Facebook Page the account is connected to')
    access_token = fields.Char(groups='stratos_social.group_social_manager', copy=False)
    refresh_token = fields.Char(groups='stratos_social.group_social_manager', copy=False,
                                help='YouTube / TikTok: used to get a new access token automatically')
    token_expiry = fields.Datetime(groups='stratos_social.group_social_manager', copy=False)
    # TikTok creator settings (refreshed on connect, on "Check Connection" and before each post)
    tiktok_privacy_options = fields.Char('Allowed Privacy Levels', readonly=True)
    tiktok_comment_disabled = fields.Boolean('Comments Off on TikTok', readonly=True)
    tiktok_duet_disabled = fields.Boolean('Duet Off on TikTok', readonly=True)
    tiktok_stitch_disabled = fields.Boolean('Stitch Off on TikTok', readonly=True)
    tiktok_max_duration = fields.Integer('Max Video Length (sec)', readonly=True)
    image_128 = fields.Image('Picture', max_width=128, max_height=128)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    state = fields.Selection([
        ('connected', 'Connected'),
        ('error', 'Needs Attention'),
    ], default='connected', required=True)
    last_error = fields.Text(readonly=True)
    connected_by_id = fields.Many2one('res.users', readonly=True, default=lambda self: self.env.user)
    connected_date = fields.Datetime(readonly=True, default=fields.Datetime.now)
    live_post_ids = fields.One2many('stratos.social.live.post', 'account_id')
    post_count = fields.Integer(compute='_compute_post_count')
    account_url = fields.Char(compute='_compute_account_url', string='Open Profile')

    _unique_account = models.Constraint(
        'UNIQUE(platform, external_id, company_id)',
        'This social account is already connected for this company.',
    )

    @api.depends('live_post_ids.state')
    def _compute_post_count(self):
        for account in self:
            account.post_count = len(account.live_post_ids.filtered(lambda l: l.state == 'posted'))

    @api.depends('platform', 'external_id', 'username')
    def _compute_account_url(self):
        for account in self:
            if account.platform == 'facebook':
                account.account_url = 'https://www.facebook.com/%s' % account.external_id
            elif account.platform == 'instagram' and account.username:
                account.account_url = 'https://www.instagram.com/%s/' % account.username
            elif account.platform == 'youtube':
                account.account_url = 'https://www.youtube.com/channel/%s' % account.external_id
            elif account.platform == 'tiktok' and account.username:
                account.account_url = 'https://www.tiktok.com/@%s' % account.username
            else:
                account.account_url = False

    @api.depends('name', 'platform')
    def _compute_display_name(self):
        for account in self:
            if account.platform:
                prefix = {'facebook': 'FB', 'instagram': 'IG', 'youtube': 'YT', 'tiktok': 'TT'}[account.platform]
                account.display_name = '[%s] %s' % (prefix, account.name or '')
            else:
                account.display_name = account.name

    # ------------------------------------------------------------------
    # Connecting
    # ------------------------------------------------------------------
    def action_connect_meta(self):
        """Start the Meta login (opens Facebook, comes back to Odoo)."""
        if not self.env.user.has_group('stratos_social.group_social_manager'):
            raise UserError(_('Only Social Marketing administrators can connect accounts.'))
        icp = self.env['ir.config_parameter'].sudo()
        if not (icp.get_str('stratos_social.meta_app_id') and icp.get_str('stratos_social.meta_app_secret')):
            raise UserError(_(
                'Enter your Meta App ID and App Secret first:\n'
                'Settings > Social Marketing > Meta (Facebook & Instagram).\n\n'
                'No Meta app yet? Use "Add with Access Token" instead.'))
        return {
            'type': 'ir.actions.act_url',
            'url': '/stratos_social/meta/connect?company_id=%s' % self.env.company.id,
            'target': 'self',
        }

    def action_connect_youtube(self):
        """Start the Google login (opens Google, comes back to Odoo)."""
        if not self.env.user.has_group('stratos_social.group_social_manager'):
            raise UserError(_('Only Social Marketing administrators can connect accounts.'))
        icp = self.env['ir.config_parameter'].sudo()
        if not (icp.get_str('stratos_social.google_client_id') and icp.get_str('stratos_social.google_client_secret')):
            raise UserError(_(
                'Enter your Google OAuth Client ID and Client Secret first:\n'
                'Settings > Social Marketing > YouTube.'))
        return {
            'type': 'ir.actions.act_url',
            'url': '/stratos_social/google/connect?company_id=%s' % self.env.company.id,
            'target': 'self',
        }

    def action_connect_tiktok(self):
        """Start the TikTok login (opens TikTok, comes back to Odoo)."""
        if not self.env.user.has_group('stratos_social.group_social_manager'):
            raise UserError(_('Only Social Marketing administrators can connect accounts.'))
        icp = self.env['ir.config_parameter'].sudo()
        if not (icp.get_str('stratos_social.tiktok_client_key') and icp.get_str('stratos_social.tiktok_client_secret')):
            raise UserError(_(
                'Enter your TikTok Client Key and Client Secret first:\n'
                'Settings > Social Marketing > TikTok.'))
        return {
            'type': 'ir.actions.act_url',
            'url': '/stratos_social/tiktok/connect?company_id=%s' % self.env.company.id,
            'target': 'self',
        }

    def action_open_token_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add Accounts with Access Token'),
            'res_model': 'stratos.social.token.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    @api.model
    def _fetch_picture(self, url):
        if not url:
            return False
        try:
            response = requests.get(url, timeout=15)
            if response.ok and response.headers.get('content-type', '').startswith('image'):
                return base64.b64encode(response.content).decode()
        except requests.exceptions.RequestException:
            _logger.info('Could not download social account picture %s', url)
        return False

    @api.model
    def _sync_meta_pages(self, pages, company):
        """Create or update one account per Facebook Page and per linked
        Instagram Business account. Returns the accounts touched."""
        accounts = self.browse()
        Account = self.sudo().with_context(active_test=False)
        for page in pages:
            if not page.get('access_token'):
                continue
            vals_list = [{
                'platform': 'facebook',
                'external_id': page['id'],
                'name': page.get('name') or page['id'],
                'access_token': page['access_token'],
                'picture_url': (page.get('picture') or {}).get('data', {}).get('url'),
            }]
            ig = page.get('instagram_business_account')
            if ig and ig.get('id'):
                vals_list.append({
                    'platform': 'instagram',
                    'external_id': ig['id'],
                    'name': ig.get('name') or ig.get('username') or ig['id'],
                    'username': ig.get('username'),
                    'facebook_page_id': page['id'],
                    'access_token': page['access_token'],
                    'picture_url': ig.get('profile_picture_url'),
                })
            for vals in vals_list:
                picture = self._fetch_picture(vals.pop('picture_url', None))
                vals.update({
                    'company_id': company.id,
                    'state': 'connected',
                    'last_error': False,
                    'active': True,
                    'connected_by_id': self.env.user.id,
                    'connected_date': fields.Datetime.now(),
                })
                if picture:
                    vals['image_128'] = picture
                existing = Account.search([
                    ('platform', '=', vals['platform']),
                    ('external_id', '=', vals['external_id']),
                    ('company_id', '=', company.id),
                ], limit=1)
                if existing:
                    existing.write(vals)
                    accounts |= existing
                else:
                    accounts |= Account.create(vals)
        return accounts.sudo(False)

    @api.model
    def _sync_youtube_channels(self, token_data, company):
        """Create or update one account per YouTube channel of the Google login."""
        client = YouTubeClient.from_env(self.env)
        access_token = token_data['access_token']
        refresh_token = token_data.get('refresh_token')
        expiry = fields.Datetime.now() + timedelta(seconds=int(token_data.get('expires_in') or 3600))
        Account = self.sudo().with_context(active_test=False)
        accounts = self.browse()
        for channel in client.my_channels(access_token):
            snippet = channel.get('snippet') or {}
            thumbs = snippet.get('thumbnails') or {}
            picture_url = (thumbs.get('default') or thumbs.get('medium') or {}).get('url')
            vals = {
                'platform': 'youtube',
                'external_id': channel['id'],
                'name': snippet.get('title') or channel['id'],
                'username': (snippet.get('customUrl') or '').lstrip('@') or False,
                'access_token': access_token,
                'token_expiry': expiry,
                'company_id': company.id,
                'state': 'connected',
                'last_error': False,
                'active': True,
                'connected_by_id': self.env.user.id,
                'connected_date': fields.Datetime.now(),
            }
            if refresh_token:
                vals['refresh_token'] = refresh_token
            picture = self._fetch_picture(picture_url)
            if picture:
                vals['image_128'] = picture
            existing = Account.search([
                ('platform', '=', 'youtube'), ('external_id', '=', channel['id']),
                ('company_id', '=', company.id)], limit=1)
            if existing:
                existing.write(vals)
                accounts |= existing
            else:
                accounts |= Account.create(vals)
        return accounts.sudo(False)

    def _get_youtube_token(self, client=None):
        """Valid YouTube access token, refreshed when it is about to expire."""
        self.ensure_one()
        account = self.sudo()
        if account.access_token and account.token_expiry and \
                account.token_expiry > fields.Datetime.now() + timedelta(minutes=2):
            return account.access_token
        if not account.refresh_token:
            raise GoogleApiError(_('No refresh token: reconnect this YouTube channel.'), auth_error=True)
        client = client or YouTubeClient.from_env(self.env)
        data = client.refresh(account.refresh_token)
        account.write({
            'access_token': data['access_token'],
            'token_expiry': fields.Datetime.now() + timedelta(seconds=int(data.get('expires_in') or 3600)),
        })
        return data['access_token']

    @api.model
    def _tiktok_creator_vals(self, creator):
        return {
            'tiktok_privacy_options': ','.join(creator.get('privacy_level_options') or []),
            'tiktok_comment_disabled': bool(creator.get('comment_disabled')),
            'tiktok_duet_disabled': bool(creator.get('duet_disabled')),
            'tiktok_stitch_disabled': bool(creator.get('stitch_disabled')),
            'tiktok_max_duration': int(creator.get('max_video_post_duration_sec') or 0),
        }

    @api.model
    def _sync_tiktok_account(self, token_data, company):
        """Create or update the TikTok account of the login."""
        client = TikTokClient.from_env(self.env)
        access_token = token_data['access_token']
        open_id = token_data.get('open_id')
        user = client.user_info(access_token)
        creator = client.creator_info(access_token)
        open_id = open_id or user.get('open_id')
        if not open_id:
            raise TikTokApiError(_('TikTok did not return the account ID.'))
        now = fields.Datetime.now()
        vals = {
            'platform': 'tiktok',
            'external_id': open_id,
            'name': creator.get('creator_nickname') or user.get('display_name') or open_id,
            'username': creator.get('creator_username') or False,
            'access_token': access_token,
            'refresh_token': token_data.get('refresh_token'),
            'token_expiry': now + timedelta(seconds=int(token_data.get('expires_in') or 86400)),
            'company_id': company.id,
            'state': 'connected',
            'last_error': False,
            'active': True,
            'connected_by_id': self.env.user.id,
            'connected_date': now,
            **self._tiktok_creator_vals(creator),
        }
        picture = self._fetch_picture(creator.get('creator_avatar_url') or user.get('avatar_url'))
        if picture:
            vals['image_128'] = picture
        Account = self.sudo().with_context(active_test=False)
        existing = Account.search([('platform', '=', 'tiktok'), ('external_id', '=', open_id),
                                   ('company_id', '=', company.id)], limit=1)
        if existing:
            existing.write(vals)
            return existing.sudo(False)
        return Account.create(vals).sudo(False)

    def _get_tiktok_token(self, client=None):
        """Valid TikTok access token (they last 24 h), refreshed when needed."""
        self.ensure_one()
        account = self.sudo()
        if account.access_token and account.token_expiry and \
                account.token_expiry > fields.Datetime.now() + timedelta(minutes=5):
            return account.access_token
        if not account.refresh_token:
            raise TikTokApiError(_('No refresh token: reconnect this TikTok account.'), auth_error=True)
        client = client or TikTokClient.from_env(self.env)
        data = client.refresh(account.refresh_token)
        vals = {
            'access_token': data['access_token'],
            'token_expiry': fields.Datetime.now() + timedelta(seconds=int(data.get('expires_in') or 86400)),
        }
        if data.get('refresh_token'):
            vals['refresh_token'] = data['refresh_token']
        account.write(vals)
        return data['access_token']

    def _refresh_tiktok_creator_info(self, client=None):
        """TikTok requires fresh creator settings before posting."""
        self.ensure_one()
        client = client or TikTokClient.from_env(self.env)
        creator = client.creator_info(self._get_tiktok_token(client))
        self.sudo().write(self._tiktok_creator_vals(creator))
        return creator

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def action_test_connection(self):
        client = MetaGraphClient.from_env(self.env)
        for account in self:
            try:
                if account.platform == 'youtube':
                    yt = YouTubeClient.from_env(self.env)
                    yt.my_channels(account._get_youtube_token(yt))
                elif account.platform == 'tiktok':
                    account._refresh_tiktok_creator_info()
                else:
                    client.get(account.external_id, account.sudo().access_token, {'fields': 'id'})
                account.write({'state': 'connected', 'last_error': False})
            except (MetaApiError, GoogleApiError, TikTokApiError) as e:
                account.write({'state': 'error', 'last_error': str(e)})
        failed = self.filtered(lambda a: a.state == 'error')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'danger' if failed else 'success',
                'title': _('Connection check'),
                'message': _('%s account(s) need attention: reconnect them.', len(failed)) if failed
                else _('All selected accounts are connected.'),
                'next': {'type': 'ir.actions.act_window_close'} if not failed else False,
            },
        }

    def action_view_posts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Posts'),
            'res_model': 'stratos.social.post',
            'view_mode': 'list,form,calendar',
            'domain': [('account_ids', 'in', self.ids)],
        }
