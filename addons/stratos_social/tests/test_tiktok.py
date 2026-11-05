import base64
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged

from ..models import social_live_post, tiktok_api
from .test_social_post import FakeMeta, FakeResponse

MB = 1024 * 1024


class FakeTT:
    def __init__(self, status='PUBLISH_COMPLETE', post_ids=('7300000000000000001',), options=None,
                 refresh_fails=False, comment_disabled=False):
        self.calls = []
        self.status = status
        self.post_ids = list(post_ids)
        self.options = options or ['PUBLIC_TO_EVERYONE', 'MUTUAL_FOLLOW_FRIENDS', 'SELF_ONLY']
        self.refresh_fails = refresh_fails
        self.comment_disabled = comment_disabled

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        ok = {'error': {'code': 'ok', 'message': ''}}
        if url == tiktok_api.TOKEN_URL:
            if kw['data']['grant_type'] == 'refresh_token' and self.refresh_fails:
                return FakeResponse({'error': 'invalid_grant', 'error_description': 'Refresh token is invalid or expired.'}, 400)
            return FakeResponse({'access_token': 'TT_ACCESS', 'expires_in': 86400, 'refresh_token': 'TT_REFRESH2',
                                 'refresh_expires_in': 31536000, 'open_id': 'OPEN1',
                                 'scope': 'user.info.basic,video.publish'})
        if url.endswith('/user/info/'):
            return FakeResponse(dict(ok, data={'user': {'open_id': 'OPEN1', 'display_name': 'Stratos'}}))
        if url.endswith('/creator_info/query/'):
            return FakeResponse(dict(ok, data={
                'creator_nickname': 'Stratos Hub', 'creator_username': 'stratoshub',
                'privacy_level_options': self.options, 'comment_disabled': self.comment_disabled,
                'duet_disabled': True, 'stitch_disabled': False, 'max_video_post_duration_sec': 600}))
        if url.endswith('/video/init/'):
            return FakeResponse(dict(ok, data={'publish_id': 'v_pub_123', 'upload_url': 'https://upload.tiktok.test/abc'}))
        if url == 'https://upload.tiktok.test/abc':
            return FakeResponse({}, 201)
        if url.endswith('/status/fetch/'):
            return FakeResponse(dict(ok, data={'status': self.status, 'fail_reason': 'file_format_check_failed',
                                               'publicaly_available_post_id': self.post_ids}))
        return FakeResponse({'error': {'code': 'unexpected', 'message': url}}, 404)


@tagged('post_install', '-at_install')
class TestTikTok(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env['ir.config_parameter'].sudo()
        icp.set_str('stratos_social.tiktok_client_key', 'ck')
        icp.set_str('stratos_social.tiktok_client_secret', 'cs')
        icp.set_bool('stratos_social.tiktok_audited', True)
        cls.tt = cls.env['stratos.social.account'].create({
            'name': 'Stratos Hub', 'platform': 'tiktok', 'external_id': 'OPEN1', 'username': 'stratoshub',
            'access_token': 'OLD', 'refresh_token': 'TT_REFRESH',
            'token_expiry': fields.Datetime.now() - timedelta(hours=1),
            'tiktok_privacy_options': 'PUBLIC_TO_EVERYONE,MUTUAL_FOLLOW_FRIENDS,SELF_ONLY'})
        cls.video = cls.env['ir.attachment'].create({
            'name': 'reel.mp4', 'raw': b'v' * 1000, 'mimetype': 'video/mp4'})

    def setUp(self):
        super().setUp()
        sleeper = patch.object(social_live_post.time, 'sleep', lambda s: None)
        sleeper.start()
        self.addCleanup(sleeper.stop)

    def _patch(self, tt, meta=None):
        meta = meta or FakeMeta()
        return patch.multiple(tiktok_api.requests, request=tt.request, get=meta.get, post=meta.post)

    def _post(self, **vals):
        base = {'message': 'Odoo 20 Light Users #Odoo20', 'account_ids': [(6, 0, self.tt.ids)],
                'video_ids': [(6, 0, self.video.ids)], 'tiktok_privacy': 'PUBLIC_TO_EVERYONE',
                'tiktok_allow_comment': True}
        base.update(vals)
        return self.env['stratos.social.post'].create(base)

    def test_direct_post_flow(self):
        post = self._post(tiktok_commercial=True, tiktok_brand_organic=True, tiktok_is_aigc=True)
        tt = FakeTT()
        with self._patch(tt):
            post.action_post_now()
        line = post.live_post_ids
        self.assertEqual(line.state, 'posted', line.error_message)
        self.assertEqual(post.state, 'posted')
        self.assertEqual(line.permalink, 'https://www.tiktok.com/@stratoshub/video/7300000000000000001')
        self.assertEqual(self.tt.sudo().refresh_token, 'TT_REFRESH2')
        urls = [c[1] for c in tt.calls]
        # order required by TikTok: creator info -> init -> upload -> status
        creator_i = next(i for i, u in enumerate(urls) if u.endswith('/creator_info/query/'))
        init_i = next(i for i, u in enumerate(urls) if u.endswith('/video/init/'))
        self.assertLess(creator_i, init_i)
        init = json.loads(tt.calls[init_i][2]['data'])
        info = init['post_info']
        self.assertEqual(info['privacy_level'], 'PUBLIC_TO_EVERYONE')
        self.assertFalse(info['disable_comment'])
        self.assertTrue(info['disable_duet'])       # not ticked
        self.assertTrue(info['brand_organic_toggle'])
        self.assertFalse(info['brand_content_toggle'])
        self.assertTrue(info['is_aigc'])
        self.assertEqual(init['source_info'], {'source': 'FILE_UPLOAD', 'video_size': 1000,
                                               'chunk_size': 1000, 'total_chunk_count': 1})
        put = [c for c in tt.calls if c[0] == 'PUT'][0]
        self.assertEqual(put[2]['headers']['Content-Range'], 'bytes 0-999/1000')

    def test_processing_then_cron_completes(self):
        post = self._post()
        tt = FakeTT(status='PROCESSING_UPLOAD')
        with self._patch(tt):
            post.action_post_now()
        self.assertEqual(post.live_post_ids.state, 'processing')
        self.assertEqual(post.state, 'posted')  # accepted by TikTok
        tt.status = 'PUBLISH_COMPLETE'
        with self._patch(tt):
            self.env['stratos.social.post']._cron_publish_scheduled()
        self.assertEqual(post.live_post_ids.state, 'posted')
        self.assertIn('/video/7300000000000000001', post.live_post_ids.permalink)

    def test_processing_then_failed(self):
        post = self._post()
        tt = FakeTT(status='PROCESSING_DOWNLOAD')
        with self._patch(tt):
            post.action_post_now()
        tt.status = 'FAILED'
        with self._patch(tt):
            self.env['stratos.social.post']._cron_publish_scheduled()
        self.assertEqual(post.live_post_ids.state, 'failed')
        self.assertIn('file_format_check_failed', post.live_post_ids.error_message)
        self.assertEqual(post.state, 'failed')

    def test_private_post_links_to_profile(self):
        post = self._post(tiktok_privacy='SELF_ONLY')
        with self._patch(FakeTT(post_ids=())):
            post.action_post_now()
        self.assertEqual(post.live_post_ids.permalink, 'https://www.tiktok.com/@stratoshub')

    def test_guideline_checks(self):
        post = self._post(tiktok_privacy=False)
        self.assertIn('Who can view', post.warning_message)
        post.write({'tiktok_privacy': 'SELF_ONLY', 'tiktok_commercial': True})
        self.assertIn('Your Brand', post.warning_message)
        post.write({'tiktok_brand_content': True})
        self.assertIn('cannot be "Only me"', post.warning_message)
        post.write({'tiktok_privacy': 'FOLLOWER_OF_CREATOR', 'tiktok_brand_content': False, 'tiktok_brand_organic': True})
        self.assertIn('does not allow', post.warning_message)  # not in account options
        self.tt.tiktok_duet_disabled = True
        post.write({'tiktok_privacy': 'PUBLIC_TO_EVERYONE', 'tiktok_allow_duet': True})
        self.assertIn('Duet turned off', post.warning_message)
        post.write({'tiktok_allow_duet': False, 'video_ids': [(5, 0, 0)]})
        self.assertIn('exactly one video', post.warning_message)

    def test_unaudited_app_only_me(self):
        self.env['ir.config_parameter'].sudo().set_bool('stratos_social.tiktok_audited', False)
        post = self._post()
        self.assertIn('Only me', post.warning_message)
        post.tiktok_privacy = 'SELF_ONLY'
        self.assertFalse(post.warning_message)

    def test_privacy_changed_on_tiktok_side(self):
        post = self._post()
        with self._patch(FakeTT(options=['SELF_ONLY'])):
            post.action_post_now()
        self.assertEqual(post.state, 'failed')
        self.assertIn('Allowed: SELF_ONLY', post.live_post_ids.error_message)
        self.assertEqual(self.tt.tiktok_privacy_options, 'SELF_ONLY')  # settings refreshed

    def test_revoked_refresh_token(self):
        post = self._post()
        with self._patch(FakeTT(refresh_fails=True)):
            post.action_post_now()
        self.assertEqual(post.state, 'failed')
        self.assertEqual(self.tt.state, 'error')

    def test_chunk_plan(self):
        self.assertEqual(tiktok_api.chunk_plan(3 * MB), (3 * MB, 1))
        self.assertEqual(tiktok_api.chunk_plan(64 * MB), (64 * MB, 1))
        size, count = tiktok_api.chunk_plan(105 * MB)
        self.assertEqual((size, count), (10 * MB, 10))  # last chunk carries 15 MB

    def test_multi_chunk_upload_ranges(self):
        client = tiktok_api.TikTokClient('k', 's')
        tt = FakeTT()
        content = b'x' * 25
        with self._patch(tt):
            client.upload_video('https://upload.tiktok.test/abc', content, 'video/mp4', 10, 2)
        ranges = [c[2]['headers']['Content-Range'] for c in tt.calls]
        self.assertEqual(ranges, ['bytes 0-9/25', 'bytes 10-24/25'])

    def test_connect_sync(self):
        with self._patch(FakeTT()):
            client = tiktok_api.TikTokClient.from_env(self.env)
            data = client.exchange_code('CODE', 'https://erp/cb')
            account = self.env['stratos.social.account']._sync_tiktok_account(data, self.env.company)
        self.assertEqual(account, self.tt)
        self.assertEqual(account.display_name, '[TT] Stratos Hub')
        self.assertTrue(account.tiktok_duet_disabled)
        self.assertEqual(account.tiktok_max_duration, 600)
        self.assertEqual(account.account_url, 'https://www.tiktok.com/@stratoshub')

    def test_one_video_to_youtube_and_tiktok(self):
        yt = self.env['stratos.social.account'].create({
            'name': 'YT', 'platform': 'youtube', 'external_id': 'UCX', 'access_token': 'A',
            'token_expiry': fields.Datetime.now() + timedelta(hours=1)})
        post = self._post(account_ids=[(6, 0, (self.tt | yt).ids)], youtube_title='Day 1')
        self.assertFalse(post.warning_message)
