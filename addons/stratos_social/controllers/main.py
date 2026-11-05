import logging
import secrets

from markupsafe import escape

from odoo import http, _
from odoo.http import request

from ..models.google_api import GoogleApiError, YouTubeClient
from ..models.meta_api import MetaApiError, MetaGraphClient
from ..models.tiktok_api import TikTokApiError, TikTokClient

_logger = logging.getLogger(__name__)

SESSION_KEY = 'stratos_social_oauth'
GOOGLE_SESSION_KEY = 'stratos_social_google_oauth'
TIKTOK_SESSION_KEY = 'stratos_social_tiktok_oauth'


class StratosSocialController(http.Controller):

    def _redirect_uri(self):
        base_url = request.env['ir.config_parameter'].sudo().get_str('web.base.url') or ''
        return '%s/stratos_social/meta/callback' % base_url.rstrip('/')

    def _back_to_accounts(self, error=None, count=None):
        url = '/odoo/action-stratos_social.action_social_account'
        if not error:
            return request.redirect(url, local=True)
        # show the reason instead of failing silently
        html = (
            '<html><head><meta name="viewport" content="width=device-width"/></head>'
            '<body style="font-family:sans-serif;max-width:560px;margin:60px auto;padding:0 16px">'
            '<h2>Could not connect the account</h2>'
            '<p style="background:#fdecea;padding:12px;border-radius:6px">%s</p>'
            '<p><a href="%s">Back to Social Accounts</a></p></body></html>'
        ) % (escape(error), url)
        return request.make_response(html, headers=[('Content-Type', 'text/html; charset=utf-8')])

    @http.route('/stratos_social/meta/connect', type='http', auth='user')
    def meta_connect(self, company_id=None, **kw):
        if not request.env.user.has_group('stratos_social.group_social_manager'):
            return request.not_found()
        company_ids = request.env.user.company_ids.ids
        company_id = int(company_id) if company_id and int(company_id) in company_ids else request.env.company.id
        state = secrets.token_urlsafe(32)
        request.session[SESSION_KEY] = {'state': state, 'company_id': company_id}
        client = MetaGraphClient.from_env(request.env)
        return request.redirect(client.authorize_url(self._redirect_uri(), state), local=False)

    @http.route('/stratos_social/meta/callback', type='http', auth='user')
    def meta_callback(self, code=None, state=None, error=None, error_description=None, **kw):
        stored = request.session.pop(SESSION_KEY, None)
        if not request.env.user.has_group('stratos_social.group_social_manager'):
            return request.not_found()
        if error:
            return self._back_to_accounts(error=error_description or error)
        if not stored or not state or not secrets.compare_digest(stored.get('state', ''), state):
            return self._back_to_accounts(error=_('The login session expired. Please try connecting again.'))
        if not code:
            return self._back_to_accounts(error=_('Meta did not return an authorization code.'))
        company = request.env['res.company'].browse(stored['company_id'])
        client = MetaGraphClient.from_env(request.env)
        try:
            user_token = client.exchange_code(code, self._redirect_uri())
            user_token = client.long_lived_user_token(user_token)
            pages = client.list_pages(user_token)
        except MetaApiError as e:
            _logger.warning('Meta connection failed: %s', e)
            return self._back_to_accounts(error=str(e))
        if not pages:
            return self._back_to_accounts(error=_(
                'No Facebook Pages were shared. Make sure you are an admin of the Page and '
                'that you ticked it during the Meta login.'))
        accounts = request.env['stratos.social.account']._sync_meta_pages(pages, company)
        return self._back_to_accounts(count=len(accounts))

    # ------------------------------------------------------------------
    # YouTube (Google OAuth)
    # ------------------------------------------------------------------
    def _google_redirect_uri(self):
        base_url = request.env['ir.config_parameter'].sudo().get_str('web.base.url') or ''
        return '%s/stratos_social/google/callback' % base_url.rstrip('/')

    @http.route('/stratos_social/google/connect', type='http', auth='user')
    def google_connect(self, company_id=None, **kw):
        if not request.env.user.has_group('stratos_social.group_social_manager'):
            return request.not_found()
        company_ids = request.env.user.company_ids.ids
        company_id = int(company_id) if company_id and int(company_id) in company_ids else request.env.company.id
        state = secrets.token_urlsafe(32)
        request.session[GOOGLE_SESSION_KEY] = {'state': state, 'company_id': company_id}
        client = YouTubeClient.from_env(request.env)
        return request.redirect(client.authorize_url(self._google_redirect_uri(), state), local=False)

    @http.route('/stratos_social/google/callback', type='http', auth='user')
    def google_callback(self, code=None, state=None, error=None, **kw):
        stored = request.session.pop(GOOGLE_SESSION_KEY, None)
        if not request.env.user.has_group('stratos_social.group_social_manager'):
            return request.not_found()
        if error:
            return self._back_to_accounts(error=error)
        if not stored or not state or not secrets.compare_digest(stored.get('state', ''), state):
            return self._back_to_accounts(error=_('The login session expired. Please try connecting again.'))
        if not code:
            return self._back_to_accounts(error=_('Google did not return an authorization code.'))
        company = request.env['res.company'].browse(stored['company_id'])
        client = YouTubeClient.from_env(request.env)
        try:
            token_data = client.exchange_code(code, self._google_redirect_uri())
            accounts = request.env['stratos.social.account']._sync_youtube_channels(token_data, company)
        except GoogleApiError as e:
            _logger.warning('YouTube connection failed: %s', e)
            return self._back_to_accounts(error=str(e))
        if not accounts:
            return self._back_to_accounts(error=_(
                'This Google account has no YouTube channel. Create a channel on youtube.com first, '
                'or choose the Google account that owns the channel.'))
        return self._back_to_accounts()

    # ------------------------------------------------------------------
    # TikTok (Login Kit v2)
    # ------------------------------------------------------------------
    def _tiktok_redirect_uri(self):
        base_url = request.env['ir.config_parameter'].sudo().get_str('web.base.url') or ''
        return '%s/stratos_social/tiktok/callback' % base_url.rstrip('/')

    @http.route('/stratos_social/tiktok/connect', type='http', auth='user')
    def tiktok_connect(self, company_id=None, **kw):
        if not request.env.user.has_group('stratos_social.group_social_manager'):
            return request.not_found()
        company_ids = request.env.user.company_ids.ids
        company_id = int(company_id) if company_id and int(company_id) in company_ids else request.env.company.id
        state = secrets.token_urlsafe(32)
        request.session[TIKTOK_SESSION_KEY] = {'state': state, 'company_id': company_id}
        client = TikTokClient.from_env(request.env)
        return request.redirect(client.authorize_url(self._tiktok_redirect_uri(), state), local=False)

    @http.route('/stratos_social/tiktok/callback', type='http', auth='user')
    def tiktok_callback(self, code=None, state=None, error=None, error_description=None, **kw):
        stored = request.session.pop(TIKTOK_SESSION_KEY, None)
        if not request.env.user.has_group('stratos_social.group_social_manager'):
            return request.not_found()
        if error:
            return self._back_to_accounts(error=error_description or error)
        if not stored or not state or not secrets.compare_digest(stored.get('state', ''), state):
            return self._back_to_accounts(error=_('The login session expired. Please try connecting again.'))
        if not code:
            return self._back_to_accounts(error=_('TikTok did not return an authorization code.'))
        company = request.env['res.company'].browse(stored['company_id'])
        client = TikTokClient.from_env(request.env)
        try:
            token_data = client.exchange_code(code, self._tiktok_redirect_uri())
            if 'video.publish' not in (token_data.get('scope') or 'video.publish'):
                return self._back_to_accounts(error=_(
                    'TikTok did not grant the "video.publish" permission. Connect again and allow posting.'))
            request.env['stratos.social.account']._sync_tiktok_account(token_data, company)
        except TikTokApiError as e:
            _logger.warning('TikTok connection failed: %s', e)
            return self._back_to_accounts(error=str(e))
        return self._back_to_accounts()
