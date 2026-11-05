import base64
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged

from ..models import google_api
from .test_social_post import FakeMeta, FakeResponse


class FakeGoogleResponse(FakeResponse):
    def __init__(self, data, status=200, headers=None):
        super().__init__(data, status)
        self.headers = headers or {}


class FakeGoogle:
    def __init__(self, refresh_fails=False, upload_fails=False):
        self.calls = []
        self.refresh_fails = refresh_fails
        self.upload_fails = upload_fails

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        if url == google_api.TOKEN_URL:
            grant = kw['data']['grant_type']
            if grant == 'refresh_token' and self.refresh_fails:
                return FakeGoogleResponse({'error': 'invalid_grant', 'error_description': 'Token has been expired or revoked.'}, 400)
            data = {'access_token': 'ACCESS_NEW', 'expires_in': 3599}
            if grant == 'authorization_code':
                data['refresh_token'] = 'REFRESH'
            return FakeGoogleResponse(data)
        if url.endswith('/channels'):
            return FakeGoogleResponse({'items': [{'id': 'UC123', 'snippet': {
                'title': 'Stratos Hub', 'customUrl': '@stratoshub', 'thumbnails': {}}}]})
        if url.startswith(google_api.UPLOAD_URL):
            if self.upload_fails:
                return FakeGoogleResponse({'error': {'message': 'The request cannot be completed because you have exceeded your quota.',
                                                     'errors': [{'reason': 'quotaExceeded'}]}}, 403)
            return FakeGoogleResponse({}, 200, {'Location': 'https://upload.example/session/1'})
        if url == 'https://upload.example/session/1':
            return FakeGoogleResponse({'id': 'VIDEO123', 'status': {'privacyStatus': 'public'}})
        return FakeGoogleResponse({'error': {'message': 'unexpected %s' % url}}, 404)


@tagged('post_install', '-at_install')
class TestYouTube(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env['ir.config_parameter'].sudo()
        icp.set_str('stratos_social.google_client_id', 'gid')
        icp.set_str('stratos_social.google_client_secret', 'gsecret')
        icp.set_str('stratos_social.meta_graph_version', 'v25.0')
        cls.yt = cls.env['stratos.social.account'].create({
            'name': 'Stratos YT', 'platform': 'youtube', 'external_id': 'UCX',
            'access_token': 'OLD', 'refresh_token': 'REFRESH',
            'token_expiry': fields.Datetime.now() - timedelta(minutes=5)})
        cls.fb = cls.env['stratos.social.account'].create({
            'name': 'Stratos FB', 'platform': 'facebook', 'external_id': 'PAGE1', 'access_token': 'PAGE_TOKEN'})
        cls.video = cls.env['ir.attachment'].create({
            'name': 'reel.mp4', 'raw': b'\x00\x00\x00\x18ftypmp42 fake video',
            'mimetype': 'video/mp4'})
        cls.image = cls.env['ir.attachment'].create({
            'name': 'pic.jpg', 'raw': b'\xff\xd8\xff fake', 'mimetype': 'image/jpeg'})

    def _patch(self, google, meta=None):
        meta = meta or FakeMeta()
        return patch.multiple(google_api.requests, request=google.request, get=meta.get, post=meta.post)

    def _post(self, **vals):
        base = {'message': 'Day 1 #Odoo20 #ERP', 'account_ids': [(6, 0, self.yt.ids)],
                'video_ids': [(6, 0, self.video.ids)], 'youtube_title': "What's new in Odoo 20 - Day 1"}
        base.update(vals)
        return self.env['stratos.social.post'].create(base)

    def test_upload_refreshes_token_and_posts(self):
        post = self._post(youtube_privacy='unlisted', youtube_category='28')
        google = FakeGoogle()
        with self._patch(google):
            post.action_post_now()
        self.assertEqual(post.state, 'posted', post.live_post_ids.mapped('error_message'))
        line = post.live_post_ids
        self.assertEqual(line.external_post_id, 'VIDEO123')
        self.assertEqual(line.permalink, 'https://www.youtube.com/watch?v=VIDEO123')
        self.assertEqual(self.yt.access_token, 'ACCESS_NEW')
        import json
        session = [c for c in google.calls if c[1].startswith(google_api.UPLOAD_URL)][0]
        meta = json.loads(session[2]['data'])
        self.assertEqual(meta['status']['privacyStatus'], 'unlisted')
        self.assertFalse(meta['status']['selfDeclaredMadeForKids'])
        self.assertEqual(meta['snippet']['categoryId'], '28')
        self.assertEqual(meta['snippet']['tags'], ['Odoo20', 'ERP'])
        self.assertEqual(session[2]['headers']['X-Upload-Content-Type'], 'video/mp4')
        put = [c for c in google.calls if c[0] == 'PUT'][0]
        self.assertEqual(put[2]['data'], bytes(self.video.raw))

    def test_valid_token_not_refreshed(self):
        self.yt.write({'access_token': 'STILL_GOOD', 'token_expiry': fields.Datetime.now() + timedelta(minutes=30)})
        google = FakeGoogle()
        with self._patch(google):
            self._post().action_post_now()
        self.assertFalse([c for c in google.calls if c[1] == google_api.TOKEN_URL])

    def test_revoked_token_flags_account(self):
        post = self._post()
        with self._patch(FakeGoogle(refresh_fails=True)):
            post.action_post_now()
        self.assertEqual(post.state, 'failed')
        self.assertEqual(self.yt.state, 'error')
        self.assertIn('revoked', post.live_post_ids.error_message)

    def test_quota_error_keeps_account_connected(self):
        post = self._post()
        with self._patch(FakeGoogle(upload_fails=True)):
            post.action_post_now()
        self.assertEqual(post.state, 'failed')
        self.assertIn('quotaExceeded', post.live_post_ids.error_message)
        self.assertEqual(self.yt.state, 'connected')

    def test_youtube_checks(self):
        post = self._post(video_ids=[(5, 0, 0)], youtube_title=False)
        self.assertIn('exactly one video', post.warning_message)
        self.assertIn('YouTube Title', post.warning_message)
        post.write({'video_ids': [(6, 0, self.image.ids)], 'youtube_title': 'x' * 101})
        self.assertIn('only takes video files', post.warning_message)
        self.assertIn('limit is 100', post.warning_message)
        post.write({'video_ids': [(6, 0, self.video.ids)], 'youtube_title': 'Odoo <20>'})
        self.assertIn('< and >', post.warning_message)
        post.write({'youtube_title': 'Fine', 'account_ids': [(6, 0, self.fb.ids)]})
        self.assertIn('published to YouTube and TikTok only', post.warning_message)

    def test_facebook_images_and_youtube_video_together(self):
        post = self._post(account_ids=[(6, 0, (self.yt | self.fb).ids)],
                          attachment_ids=[(6, 0, self.image.ids)])
        self.assertFalse(post.warning_message)
        meta = FakeMeta()
        with self._patch(FakeGoogle(), meta):
            post.action_post_now()
        self.assertEqual(post.state, 'posted', post.live_post_ids.mapped('error_message'))
        self.assertTrue([c for c in meta.calls if c[1] == 'PAGE1/photos'])

    def test_sync_channels(self):
        with self._patch(FakeGoogle()):
            client = google_api.YouTubeClient.from_env(self.env)
            token = client.exchange_code('CODE', 'https://x/cb')
            accounts = self.env['stratos.social.account']._sync_youtube_channels(token, self.env.company)
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts.external_id, 'UC123')
        self.assertEqual(accounts.username, 'stratoshub')
        self.assertEqual(accounts.sudo().refresh_token, 'REFRESH')
        self.assertEqual(accounts.display_name, '[YT] Stratos Hub')

    def test_authorize_url_requests_offline_access(self):
        url = google_api.YouTubeClient('gid', 's').authorize_url('https://erp/cb', 'ST')
        self.assertIn('access_type=offline', url)
        self.assertIn('youtube.upload', url)
