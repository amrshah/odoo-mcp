import base64
import io
from datetime import timedelta
from unittest.mock import patch

from PIL import Image

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models import meta_api


def _png_bytes():
    buf = io.BytesIO()
    Image.new('RGBA', (20, 20), (255, 0, 0, 128)).save(buf, format='PNG')
    return buf.getvalue()


class FakeResponse:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status
        self.text = str(data)
        self.ok = status < 400
        self.headers = {'content-type': 'application/json'}
        self.content = b''

    def json(self):
        return self._data


class FakeMeta:
    """Records every call and answers like the Graph API."""

    def __init__(self, fail_paths=()):
        self.calls = []
        self.fail_paths = fail_paths
        self.counter = 0

    def _id(self, prefix):
        self.counter += 1
        return '%s_%s' % (prefix, self.counter)

    def get(self, url, params=None, timeout=None):
        path = url.split('/v25.0/')[-1] if '/v25.0/' in url else url
        self.calls.append(('GET', path, params or {}))
        if path == 'me/accounts':
            return FakeResponse({'data': [{
                'id': 'PAGE1', 'name': 'Stratos Hub', 'access_token': 'PAGE_TOKEN',
                'instagram_business_account': {'id': 'IG1', 'username': 'stratoshub'},
            }]})
        if path == 'oauth/access_token':
            return FakeResponse({'access_token': 'LONG_TOKEN'})
        params = params or {}
        if params.get('fields') == 'status_code,status':
            return FakeResponse({'status_code': 'FINISHED'})
        if 'permalink' in (params.get('fields') or ''):
            return FakeResponse({'permalink': 'https://example.com/p/%s' % path})
        return FakeResponse({'id': path})

    def post(self, url, data=None, files=None, timeout=None):
        path = url.split('/v25.0/')[-1]
        self.calls.append(('POST', path, data or {}, files))
        for fail in self.fail_paths:
            if fail in path:
                return FakeResponse({'error': {'message': 'Invalid OAuth access token', 'code': 190}}, 400)
        if path.endswith('/photos'):
            return FakeResponse({'id': self._id('photo'), 'post_id': self._id('PAGE1_post')})
        if path.endswith('/feed'):
            return FakeResponse({'id': self._id('PAGE1_post')})
        if path.endswith('/media'):
            return FakeResponse({'id': self._id('container')})
        if path.endswith('/media_publish'):
            return FakeResponse({'id': self._id('igmedia')})
        return FakeResponse({'id': self._id('x')})


@tagged('post_install', '-at_install')
class TestSocialPost(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env['ir.config_parameter'].sudo()
        icp.set_str('web.base.url', 'https://erp.example.com')
        icp.set_str('stratos_social.meta_graph_version', 'v25.0')
        icp.set_str('stratos_social.meta_app_id', '123')
        icp.set_str('stratos_social.meta_app_secret', 'secret')
        Account = cls.env['stratos.social.account']
        cls.fb = Account.create({'name': 'Stratos FB', 'platform': 'facebook',
                                 'external_id': 'PAGE1', 'access_token': 'PAGE_TOKEN'})
        cls.ig = Account.create({'name': 'Stratos IG', 'platform': 'instagram',
                                 'external_id': 'IG1', 'username': 'stratoshub', 'access_token': 'PAGE_TOKEN'})
        cls.png = cls.env['ir.attachment'].create({
            'name': 'banner.png', 'raw': _png_bytes(), 'mimetype': 'image/png'})
        cls.png2 = cls.png.copy({'name': 'banner2.png'})

    def _patch(self, fake):
        return patch.multiple(meta_api.requests, get=fake.get, post=fake.post)

    def test_facebook_text_post(self):
        post = self.env['stratos.social.post'].create({
            'message': 'Hello from Odoo #odoo', 'account_ids': [(6, 0, self.fb.ids)],
            'link_url': 'https://www.stratos-hub.com'})
        self.assertEqual(post.hashtag_count, 1)
        fake = FakeMeta()
        with self._patch(fake):
            post.action_post_now()
        self.assertEqual(post.state, 'posted')
        feed_calls = [c for c in fake.calls if c[0] == 'POST' and c[1] == 'PAGE1/feed']
        self.assertEqual(len(feed_calls), 1)
        self.assertEqual(feed_calls[0][2]['link'], 'https://www.stratos-hub.com')
        self.assertIn('appsecret_proof', feed_calls[0][2])
        self.assertTrue(post.live_post_ids.permalink)

    def test_facebook_multi_photo(self):
        post = self.env['stratos.social.post'].create({
            'message': 'Two images', 'account_ids': [(6, 0, self.fb.ids)],
            'attachment_ids': [(6, 0, (self.png | self.png2).ids)]})
        fake = FakeMeta()
        with self._patch(fake):
            post.action_post_now()
        self.assertEqual(post.state, 'posted')
        photo_calls = [c for c in fake.calls if c[0] == 'POST' and c[1] == 'PAGE1/photos']
        self.assertEqual(len(photo_calls), 2)
        self.assertTrue(all(c[2]['published'] == 'false' for c in photo_calls))
        feed = [c for c in fake.calls if c[1] == 'PAGE1/feed'][0]
        self.assertIn('attached_media[1]', feed[2])

    def test_instagram_carousel_converts_png_to_jpeg(self):
        post = self.env['stratos.social.post'].create({
            'message': 'Carousel', 'account_ids': [(6, 0, (self.fb | self.ig).ids)],
            'attachment_ids': [(6, 0, (self.png | self.png2).ids)]})
        fake = FakeMeta()
        with self._patch(fake):
            post.action_post_now()
        self.assertEqual(post.state, 'posted', post.live_post_ids.mapped('error_message'))
        media = [c for c in fake.calls if c[0] == 'POST' and c[1] == 'IG1/media']
        self.assertEqual(len(media), 3)  # 2 children + carousel
        self.assertTrue(media[0][2]['image_url'].startswith('https://erp.example.com/web/content/'))
        self.assertEqual(media[2][2]['media_type'], 'CAROUSEL')
        jpegs = self.env['ir.attachment'].search([('res_model', '=', 'stratos.social.post'), ('res_id', '=', post.id)])
        self.assertEqual(len(jpegs), 2)
        self.assertTrue(all(j.mimetype == 'image/jpeg' for j in jpegs))

    def test_instagram_requires_image(self):
        post = self.env['stratos.social.post'].create({
            'message': 'Text only', 'account_ids': [(6, 0, self.ig.ids)]})
        self.assertIn('Instagram needs at least one image', post.warning_message)
        with self.assertRaises(UserError):
            post.action_post_now()

    def test_instagram_needs_public_https(self):
        self.env['ir.config_parameter'].sudo().set_str('web.base.url', 'http://localhost:8069')
        post = self.env['stratos.social.post'].create({
            'message': 'x', 'account_ids': [(6, 0, self.ig.ids)], 'attachment_ids': [(6, 0, self.png.ids)]})
        with self._patch(FakeMeta()):
            post.action_post_now()
        self.assertEqual(post.state, 'failed')
        self.assertIn('https', post.live_post_ids.error_message)

    def test_partial_failure_and_retry(self):
        post = self.env['stratos.social.post'].create({
            'message': 'x', 'account_ids': [(6, 0, (self.fb | self.ig).ids)],
            'attachment_ids': [(6, 0, self.png.ids)]})
        with self._patch(FakeMeta(fail_paths=('IG1/',))):
            post.action_post_now()
        self.assertEqual(post.state, 'partial')
        self.assertEqual(self.ig.state, 'error')  # code 190 flags the account
        self.ig.state = 'connected'
        fake = FakeMeta()
        with self._patch(fake):
            post.action_retry_failed()
        self.assertEqual(post.state, 'posted')
        # Facebook was not posted twice
        self.assertFalse([c for c in fake.calls if c[1].startswith('PAGE1/')])

    def test_schedule_and_cron(self):
        post = self.env['stratos.social.post'].create({
            'message': 'Later', 'account_ids': [(6, 0, self.fb.ids)], 'post_method': 'scheduled',
            'scheduled_date': fields.Datetime.now() + timedelta(hours=1)})
        post.action_schedule()
        self.assertEqual(post.state, 'scheduled')
        with self._patch(FakeMeta()):
            self.env['stratos.social.post']._cron_publish_scheduled()
        self.assertEqual(post.state, 'scheduled')  # not due yet
        post.scheduled_date = fields.Datetime.now() - timedelta(minutes=1)
        with self._patch(FakeMeta()):
            self.env['stratos.social.post']._cron_publish_scheduled()
        self.assertEqual(post.state, 'posted')

    def test_schedule_in_past_refused(self):
        post = self.env['stratos.social.post'].create({
            'message': 'x', 'account_ids': [(6, 0, self.fb.ids)], 'post_method': 'scheduled',
            'scheduled_date': fields.Datetime.now() - timedelta(hours=1)})
        with self.assertRaises(UserError):
            post.action_schedule()

    def test_sync_pages_creates_fb_and_ig(self):
        company = self.env.company
        with self._patch(FakeMeta()):
            client = meta_api.MetaGraphClient.from_env(self.env)
            pages = client.list_pages('USER')
            accounts = self.env['stratos.social.account']._sync_meta_pages(pages, company)
        # existing PAGE1 / IG1 records are updated, not duplicated
        self.assertEqual(accounts, self.fb | self.ig)
        self.assertEqual(self.ig.facebook_page_id, 'PAGE1')

    def test_token_wizard(self):
        wizard = self.env['stratos.social.token.wizard'].create({'user_token': 'SHORT'})
        with self._patch(FakeMeta()):
            action = wizard.action_connect()
        self.assertEqual(len(action['domain'][0][2]), 2)

    def test_user_without_manager_rights_can_publish(self):
        user = self.env['res.users'].create({
            'name': 'Social Poster', 'login': 'poster',
            'group_ids': [(6, 0, [self.env.ref('stratos_social.group_social_user').id])]})
        post = self.env['stratos.social.post'].with_user(user).create({
            'message': 'by user', 'account_ids': [(6, 0, self.fb.ids)]})
        with self._patch(FakeMeta()):
            post.action_post_now()
        self.assertEqual(post.state, 'posted')

    def test_calendar_drag_reschedules(self):
        post = self.env['stratos.social.post'].create({
            'message': 'drag me', 'account_ids': [(6, 0, self.fb.ids)]})
        new_date = fields.Datetime.now() + timedelta(days=3)
        post.calendar_date = new_date
        self.assertEqual(post.scheduled_date, new_date)
        self.assertEqual(post.post_method, 'scheduled')
