"""Small client for the Meta Graph API (Facebook Pages + Instagram Business).

Kept free of ORM logic so it can be mocked easily in tests.
"""
import hashlib
import hmac
import json
import logging

import requests

_logger = logging.getLogger(__name__)

GRAPH_HOST = 'https://graph.facebook.com'
DIALOG_HOST = 'https://www.facebook.com'
DEFAULT_GRAPH_VERSION = 'v25.0'
TIMEOUT = 60

# Permissions requested when connecting through Meta login
META_SCOPES = [
    'pages_show_list',
    'pages_read_engagement',
    'pages_manage_posts',
    'business_management',
    'instagram_basic',
    'instagram_content_publish',
]


class MetaApiError(Exception):
    """Readable error raised for any failed Graph API call."""

    def __init__(self, message, code=None, payload=None):
        super().__init__(message)
        self.code = code
        self.payload = payload or {}


class MetaGraphClient:
    def __init__(self, version=None, app_id=None, app_secret=None):
        self.version = (version or DEFAULT_GRAPH_VERSION).strip()
        if not self.version.startswith('v'):
            self.version = 'v' + self.version
        self.app_id = app_id
        self.app_secret = app_secret

    @classmethod
    def from_env(cls, env):
        icp = env['ir.config_parameter'].sudo()
        return cls(
            version=icp.get_str('stratos_social.meta_graph_version') or DEFAULT_GRAPH_VERSION,
            app_id=icp.get_str('stratos_social.meta_app_id'),
            app_secret=icp.get_str('stratos_social.meta_app_secret'),
        )

    # ------------------------------------------------------------------
    # Low level
    # ------------------------------------------------------------------
    def _url(self, path):
        return '%s/%s/%s' % (GRAPH_HOST, self.version, path.lstrip('/'))

    def _proof(self, token):
        """appsecret_proof makes stolen tokens useless without the app secret."""
        if not (self.app_secret and token):
            return {}
        digest = hmac.new(self.app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
        return {'appsecret_proof': digest}

    @staticmethod
    def _handle(response):
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code >= 400 or (isinstance(data, dict) and data.get('error')):
            err = data.get('error', {}) if isinstance(data, dict) else {}
            message = err.get('error_user_msg') or err.get('message') or response.text[:500] or 'Unknown error'
            raise MetaApiError(
                'Meta API error%s: %s' % (' (%s)' % err['code'] if err.get('code') else '', message),
                code=err.get('code'), payload=data,
            )
        return data

    def get(self, path, token=None, params=None):
        params = dict(params or {})
        if token:
            params['access_token'] = token
            params.update(self._proof(token))
        try:
            response = requests.get(self._url(path), params=params, timeout=TIMEOUT)
        except requests.exceptions.RequestException as e:
            raise MetaApiError('Could not reach Meta: %s' % e) from e
        return self._handle(response)

    def post(self, path, token=None, data=None, files=None):
        data = dict(data or {})
        if token:
            data['access_token'] = token
            data.update(self._proof(token))
        try:
            response = requests.post(self._url(path), data=data, files=files, timeout=TIMEOUT)
        except requests.exceptions.RequestException as e:
            raise MetaApiError('Could not reach Meta: %s' % e) from e
        return self._handle(response)

    # ------------------------------------------------------------------
    # OAuth
    # ------------------------------------------------------------------
    def authorize_url(self, redirect_uri, state):
        from urllib.parse import urlencode
        query = urlencode({
            'client_id': self.app_id,
            'redirect_uri': redirect_uri,
            'state': state,
            'response_type': 'code',
            'scope': ','.join(META_SCOPES),
        })
        return '%s/%s/dialog/oauth?%s' % (DIALOG_HOST, self.version, query)

    def exchange_code(self, code, redirect_uri):
        data = self.get('oauth/access_token', params={
            'client_id': self.app_id,
            'client_secret': self.app_secret,
            'redirect_uri': redirect_uri,
            'code': code,
        })
        return data['access_token']

    def long_lived_user_token(self, short_token):
        """Swap a short user token (1-2 h) for a long-lived one (~60 days).
        Page tokens obtained from a long-lived user token do not expire."""
        if not (self.app_id and self.app_secret):
            return short_token
        data = self.get('oauth/access_token', params={
            'grant_type': 'fb_exchange_token',
            'client_id': self.app_id,
            'client_secret': self.app_secret,
            'fb_exchange_token': short_token,
        })
        return data.get('access_token') or short_token

    def list_pages(self, user_token):
        fields = ('id,name,access_token,picture{url},'
                  'instagram_business_account{id,username,name,profile_picture_url}')
        pages = []
        result = self.get('me/accounts', token=user_token, params={'fields': fields, 'limit': 100})
        pages.extend(result.get('data', []))
        # follow pagination (rare: more than 100 pages)
        next_url = result.get('paging', {}).get('next')
        while next_url:
            try:
                response = requests.get(next_url, timeout=TIMEOUT)
            except requests.exceptions.RequestException as e:
                raise MetaApiError('Could not reach Meta: %s' % e) from e
            result = self._handle(response)
            pages.extend(result.get('data', []))
            next_url = result.get('paging', {}).get('next')
        return pages

    # ------------------------------------------------------------------
    # Facebook Page publishing
    # ------------------------------------------------------------------
    def fb_post_text(self, page_id, token, message, link=None):
        data = {'message': message or ''}
        if link:
            data['link'] = link
        return self.post('%s/feed' % page_id, token, data)['id']

    def fb_upload_photo(self, page_id, token, filename, content, mimetype, caption=None, published=True):
        data = {'published': 'true' if published else 'false'}
        if caption:
            data['caption'] = caption
        files = {'source': (filename, content, mimetype)}
        return self.post('%s/photos' % page_id, token, data, files=files)

    def fb_post_multi_photo(self, page_id, token, message, photo_ids):
        data = {'message': message or ''}
        for i, photo_id in enumerate(photo_ids):
            data['attached_media[%d]' % i] = json.dumps({'media_fbid': photo_id})
        return self.post('%s/feed' % page_id, token, data)['id']

    # ------------------------------------------------------------------
    # Instagram publishing (image URLs must be public, JPEG)
    # ------------------------------------------------------------------
    def ig_create_image_container(self, ig_user_id, token, image_url, caption=None, carousel_item=False):
        data = {'image_url': image_url}
        if carousel_item:
            data['is_carousel_item'] = 'true'
        elif caption:
            data['caption'] = caption
        return self.post('%s/media' % ig_user_id, token, data)['id']

    def ig_create_carousel_container(self, ig_user_id, token, children, caption=None):
        data = {'media_type': 'CAROUSEL', 'children': ','.join(children)}
        if caption:
            data['caption'] = caption
        return self.post('%s/media' % ig_user_id, token, data)['id']

    def ig_container_status(self, container_id, token):
        return self.get(container_id, token, {'fields': 'status_code,status'}).get('status_code')

    def ig_publish(self, ig_user_id, token, creation_id):
        return self.post('%s/media_publish' % ig_user_id, token, {'creation_id': creation_id})['id']

    def get_permalink(self, object_id, token):
        try:
            data = self.get(object_id, token, {'fields': 'permalink,permalink_url'})
        except MetaApiError:
            return False
        return data.get('permalink') or data.get('permalink_url') or False
