"""Small client for TikTok Login Kit (OAuth v2) + Content Posting API (Direct Post, FILE_UPLOAD)."""
import json
import logging
from urllib.parse import urlencode

import requests

_logger = logging.getLogger(__name__)

AUTH_URL = 'https://www.tiktok.com/v2/auth/authorize/'
API_HOST = 'https://open.tiktokapis.com/v2'
TOKEN_URL = API_HOST + '/oauth/token/'
TIMEOUT = 60
UPLOAD_TIMEOUT = 1800

TIKTOK_SCOPES = ['user.info.basic', 'video.publish']

MB = 1024 * 1024
SINGLE_CHUNK_MAX = 64 * MB   # whole file in one PUT up to this size
CHUNK_SIZE = 10 * MB         # TikTok allows 5-64 MB chunks; last chunk absorbs the remainder

AUTH_ERROR_CODES = {'access_token_invalid', 'scope_not_authorized', 'invalid_grant', 'token_expired'}


class TikTokApiError(Exception):
    def __init__(self, message, auth_error=False, payload=None):
        super().__init__(message)
        self.auth_error = auth_error
        self.payload = payload or {}


def chunk_plan(size):
    """Return (chunk_size, total_chunk_count) following TikTok's media transfer rules."""
    if size <= SINGLE_CHUNK_MAX:
        return size, 1
    count = size // CHUNK_SIZE
    return CHUNK_SIZE, count


class TikTokClient:
    def __init__(self, client_key=None, client_secret=None):
        self.client_key = client_key
        self.client_secret = client_secret

    @classmethod
    def from_env(cls, env):
        icp = env['ir.config_parameter'].sudo()
        return cls(
            client_key=icp.get_str('stratos_social.tiktok_client_key'),
            client_secret=icp.get_str('stratos_social.tiktok_client_secret'),
        )

    # ------------------------------------------------------------------
    def _request(self, method, url, **kwargs):
        kwargs.setdefault('timeout', TIMEOUT)
        try:
            return requests.request(method, url, **kwargs)
        except requests.exceptions.RequestException as e:
            raise TikTokApiError('Could not reach TikTok: %s' % e) from e

    @staticmethod
    def _handle(response):
        try:
            data = response.json()
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        # OAuth endpoint style: {"error": "invalid_grant", "error_description": "..."}
        if isinstance(data.get('error'), str) and data.get('error'):
            code = data['error']
            raise TikTokApiError('TikTok error (%s): %s' % (code, data.get('error_description') or ''),
                                 auth_error=code in AUTH_ERROR_CODES, payload=data)
        # API style: {"data": {...}, "error": {"code": "ok", "message": ""}}
        err = data.get('error') if isinstance(data.get('error'), dict) else {}
        code = err.get('code')
        if response.status_code >= 400 or (code and code != 'ok'):
            message = err.get('message') or response.text[:500] or 'Unknown error'
            raise TikTokApiError('TikTok error (%s): %s' % (code or response.status_code, message),
                                 auth_error=response.status_code == 401 or code in AUTH_ERROR_CODES,
                                 payload=data)
        return data

    def _api(self, method, path, token, payload=None, params=None):
        headers = {'Authorization': 'Bearer %s' % token}
        kwargs = {'headers': headers}
        if payload is not None:
            headers['Content-Type'] = 'application/json; charset=UTF-8'
            kwargs['data'] = json.dumps(payload)
        if params:
            kwargs['params'] = params
        return self._handle(self._request(method, API_HOST + path, **kwargs)).get('data') or {}

    # ------------------------------------------------------------------
    # OAuth
    # ------------------------------------------------------------------
    def authorize_url(self, redirect_uri, state):
        return '%s?%s' % (AUTH_URL, urlencode({
            'client_key': self.client_key,
            'scope': ','.join(TIKTOK_SCOPES),
            'response_type': 'code',
            'redirect_uri': redirect_uri,
            'state': state,
        }))

    def _token_call(self, data):
        data = dict(data, client_key=self.client_key, client_secret=self.client_secret)
        response = self._request('POST', TOKEN_URL, data=data, headers={
            'Content-Type': 'application/x-www-form-urlencoded', 'Cache-Control': 'no-cache'})
        result = self._handle(response)
        if not result.get('access_token'):
            raise TikTokApiError('TikTok did not return an access token.', payload=result)
        return result  # access_token, expires_in, refresh_token, refresh_expires_in, open_id, scope

    def exchange_code(self, code, redirect_uri):
        return self._token_call({'code': code, 'grant_type': 'authorization_code', 'redirect_uri': redirect_uri})

    def refresh(self, refresh_token):
        return self._token_call({'grant_type': 'refresh_token', 'refresh_token': refresh_token})

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------
    def user_info(self, token):
        data = self._api('GET', '/user/info/', token, params={'fields': 'open_id,avatar_url,display_name'})
        return data.get('user') or {}

    def creator_info(self, token):
        """Nickname, username, allowed privacy levels, disabled interactions, max duration."""
        return self._api('POST', '/post/publish/creator_info/query/', token, payload={})

    # ------------------------------------------------------------------
    # Direct post
    # ------------------------------------------------------------------
    def init_video_post(self, token, post_info, video_size):
        chunk_size, count = chunk_plan(video_size)
        data = self._api('POST', '/post/publish/video/init/', token, payload={
            'post_info': post_info,
            'source_info': {
                'source': 'FILE_UPLOAD',
                'video_size': video_size,
                'chunk_size': chunk_size,
                'total_chunk_count': count,
            },
        })
        if not data.get('publish_id') or not data.get('upload_url'):
            raise TikTokApiError('TikTok did not return an upload address.', payload=data)
        return data['publish_id'], data['upload_url'], chunk_size, count

    def upload_video(self, upload_url, content, mimetype, chunk_size, count):
        size = len(content)
        for index in range(count):
            start = index * chunk_size
            end = size - 1 if index == count - 1 else start + chunk_size - 1
            part = content[start:end + 1]
            response = self._request('PUT', upload_url, data=part, timeout=UPLOAD_TIMEOUT, headers={
                'Content-Type': mimetype or 'video/mp4',
                'Content-Length': str(len(part)),
                'Content-Range': 'bytes %d-%d/%d' % (start, end, size),
            })
            if response.status_code not in (200, 201, 206):
                raise TikTokApiError('TikTok upload failed (HTTP %s) on part %s of %s.'
                                     % (response.status_code, index + 1, count))

    def post_status(self, token, publish_id):
        """status: PROCESSING_UPLOAD, PROCESSING_DOWNLOAD, SEND_TO_USER_INBOX, PUBLISH_COMPLETE, FAILED"""
        return self._api('POST', '/post/publish/status/fetch/', token, payload={'publish_id': publish_id})
