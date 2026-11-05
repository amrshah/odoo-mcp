"""Small client for Google OAuth + YouTube Data API v3 (channel lookup, video upload)."""
import json
import logging
from urllib.parse import urlencode

import requests

_logger = logging.getLogger(__name__)

AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
API_URL = 'https://www.googleapis.com/youtube/v3'
UPLOAD_URL = 'https://www.googleapis.com/upload/youtube/v3/videos'
TIMEOUT = 60
UPLOAD_TIMEOUT = 1800  # large videos

YOUTUBE_SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly',
]


class GoogleApiError(Exception):
    def __init__(self, message, auth_error=False, payload=None):
        super().__init__(message)
        self.auth_error = auth_error  # token revoked / expired: account needs reconnect
        self.payload = payload or {}


class YouTubeClient:
    def __init__(self, client_id=None, client_secret=None):
        self.client_id = client_id
        self.client_secret = client_secret

    @classmethod
    def from_env(cls, env):
        icp = env['ir.config_parameter'].sudo()
        return cls(
            client_id=icp.get_str('stratos_social.google_client_id'),
            client_secret=icp.get_str('stratos_social.google_client_secret'),
        )

    @staticmethod
    def _handle(response):
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code >= 400:
            err = data.get('error') if isinstance(data, dict) else None
            if isinstance(err, dict):
                message = err.get('message') or str(err)
                reasons = [e.get('reason') for e in err.get('errors', []) if isinstance(e, dict)]
                if reasons:
                    message = '%s (%s)' % (message, ', '.join(r for r in reasons if r))
            else:
                message = data.get('error_description') or err or response.text[:500] or 'Unknown error'
            auth_error = response.status_code == 401 or err == 'invalid_grant'
            raise GoogleApiError('YouTube error (%s): %s' % (response.status_code, message),
                                 auth_error=auth_error, payload=data)
        return data

    def _request(self, method, url, **kwargs):
        kwargs.setdefault('timeout', TIMEOUT)
        try:
            response = requests.request(method, url, **kwargs)
        except requests.exceptions.RequestException as e:
            raise GoogleApiError('Could not reach Google: %s' % e) from e
        return response

    # ------------------------------------------------------------------
    # OAuth
    # ------------------------------------------------------------------
    def authorize_url(self, redirect_uri, state):
        return '%s?%s' % (AUTH_URL, urlencode({
            'client_id': self.client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(YOUTUBE_SCOPES),
            'access_type': 'offline',       # gives a refresh token
            'prompt': 'consent select_account',
            'include_granted_scopes': 'true',
            'state': state,
        }))

    def exchange_code(self, code, redirect_uri):
        response = self._request('POST', TOKEN_URL, data={
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        })
        return self._handle(response)  # access_token, refresh_token, expires_in

    def refresh(self, refresh_token):
        response = self._request('POST', TOKEN_URL, data={
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
        })
        return self._handle(response)  # access_token, expires_in

    # ------------------------------------------------------------------
    # YouTube
    # ------------------------------------------------------------------
    def my_channels(self, access_token):
        response = self._request('GET', API_URL + '/channels', params={
            'part': 'snippet', 'mine': 'true', 'maxResults': 50,
        }, headers={'Authorization': 'Bearer %s' % access_token})
        return self._handle(response).get('items', [])

    def upload_video(self, access_token, content, mimetype, metadata):
        """Resumable upload in two calls: open a session, then send the bytes."""
        headers = {
            'Authorization': 'Bearer %s' % access_token,
            'Content-Type': 'application/json; charset=UTF-8',
            'X-Upload-Content-Type': mimetype,
            'X-Upload-Content-Length': str(len(content)),
        }
        response = self._request(
            'POST', UPLOAD_URL + '?' + urlencode({'uploadType': 'resumable', 'part': 'snippet,status'}),
            data=json.dumps(metadata), headers=headers)
        self._handle(response)
        session_url = response.headers.get('Location') or response.headers.get('location')
        if not session_url:
            raise GoogleApiError('YouTube did not open an upload session.')
        response = self._request('PUT', session_url, data=content, headers={
            'Authorization': 'Bearer %s' % access_token,
            'Content-Type': mimetype,
        }, timeout=UPLOAD_TIMEOUT)
        return self._handle(response)  # video resource, with 'id'
