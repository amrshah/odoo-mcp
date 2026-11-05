import io
import logging
import re
import time

from odoo import api, fields, models, _

from .google_api import GoogleApiError, YouTubeClient
from .meta_api import MetaApiError, MetaGraphClient
from .tiktok_api import TikTokApiError, TikTokClient

_logger = logging.getLogger(__name__)

IG_STATUS_RETRIES = 10
IG_STATUS_WAIT = 3  # seconds
TT_STATUS_CHECKS = 3
TT_STATUS_WAIT = 5  # seconds (TikTok allows few calls per minute per user)


class StratosSocialLivePost(models.Model):
    """The result of one post on one account."""
    _name = 'stratos.social.live.post'
    _description = 'Social Post Result'
    _order = 'id desc'

    post_id = fields.Many2one('stratos.social.post', required=True, ondelete='cascade', index=True)
    account_id = fields.Many2one('stratos.social.account', required=True, ondelete='restrict')
    platform = fields.Selection(related='account_id.platform', store=True)
    company_id = fields.Many2one(related='post_id.company_id', store=True)
    state = fields.Selection([
        ('ready', 'Ready'),
        ('processing', 'Processing'),
        ('posted', 'Posted'),
        ('failed', 'Failed'),
    ], default='ready', required=True)
    external_post_id = fields.Char('Platform Post ID', readonly=True)
    permalink = fields.Char('View Post', readonly=True)
    error_message = fields.Text(readonly=True)
    published_date = fields.Datetime(readonly=True)

    @api.depends('post_id', 'account_id')
    def _compute_display_name(self):
        for line in self:
            line.display_name = '%s - %s' % (line.account_id.display_name or '', line.post_id.name or '')

    # ------------------------------------------------------------------
    def _publish(self):
        client = MetaGraphClient.from_env(self.env)
        for line in self.filtered(lambda l: l.state == 'ready'):
            try:
                if line.platform == 'tiktok':
                    line._publish_tiktok()
                    continue  # state set by _publish_tiktok / status check
                if line.platform == 'youtube':
                    post_id = line._publish_youtube()
                    permalink = 'https://www.youtube.com/watch?v=%s' % post_id
                else:
                    if line.platform == 'facebook':
                        post_id = line._publish_facebook(client)
                    else:
                        post_id = line._publish_instagram(client)
                    token = line.account_id.sudo().access_token
                    permalink = client.get_permalink(post_id, token)
                    if not permalink and line.platform == 'facebook':
                        permalink = 'https://www.facebook.com/%s' % post_id
                line.write({
                    'state': 'posted',
                    'external_post_id': post_id,
                    'permalink': permalink,
                    'published_date': fields.Datetime.now(),
                    'error_message': False,
                })
            except (MetaApiError, GoogleApiError, TikTokApiError, ValueError) as e:
                _logger.warning('Social post %s failed on %s: %s', line.post_id.id, line.account_id.name, e)
                line.write({'state': 'failed', 'error_message': str(e)})
                token_dead = (isinstance(e, MetaApiError) and e.code in (190, 102)) or \
                    (isinstance(e, (GoogleApiError, TikTokApiError)) and e.auth_error)
                if token_dead:
                    line.account_id.sudo().write({'state': 'error', 'last_error': str(e)})

    # ------------------------------------------------------------------
    # TikTok
    # ------------------------------------------------------------------
    def _tiktok_post_info(self, creator):
        post = self.post_id
        privacy = post.tiktok_privacy
        allowed = creator.get('privacy_level_options') or []
        if allowed and privacy not in allowed:
            raise ValueError(_('TikTok does not allow this visibility for this account right now. Allowed: %s',
                               ', '.join(allowed)))
        return {
            'title': post.message or '',
            'privacy_level': privacy,
            'disable_comment': not post.tiktok_allow_comment or bool(creator.get('comment_disabled')),
            'disable_duet': not post.tiktok_allow_duet or bool(creator.get('duet_disabled')),
            'disable_stitch': not post.tiktok_allow_stitch or bool(creator.get('stitch_disabled')),
            'brand_organic_toggle': bool(post.tiktok_commercial and post.tiktok_brand_organic),
            'brand_content_toggle': bool(post.tiktok_commercial and post.tiktok_brand_content),
            'is_aigc': bool(post.tiktok_is_aigc),
        }

    def _publish_tiktok(self):
        video = self.post_id.video_ids[:1].sudo()
        if not video:
            raise ValueError(_('TikTok needs a video file.'))
        client = TikTokClient.from_env(self.env)
        account = self.account_id
        token = account._get_tiktok_token(client)
        creator = client.creator_info(token)  # required by TikTok right before posting
        account.sudo().write(account._tiktok_creator_vals(creator))
        post_info = self._tiktok_post_info(creator)
        content = bytes(video.raw)
        publish_id, upload_url, chunk_size, count = client.init_video_post(token, post_info, len(content))
        client.upload_video(upload_url, content, video.mimetype or 'video/mp4', chunk_size, count)
        self.write({
            'state': 'processing',
            'external_post_id': publish_id,
            'error_message': False,
            'published_date': fields.Datetime.now(),
        })
        for _attempt in range(TT_STATUS_CHECKS):
            time.sleep(TT_STATUS_WAIT)
            if self._check_tiktok_status(client, token):
                break

    def _check_tiktok_status(self, client=None, token=None):
        """Update one processing TikTok result. Returns True when it is final."""
        self.ensure_one()
        client = client or TikTokClient.from_env(self.env)
        token = token or self.account_id._get_tiktok_token(client)
        data = client.post_status(token, self.external_post_id)
        status = data.get('status')
        if status == 'PUBLISH_COMPLETE':
            # TikTok's field name really is spelled "publicaly"
            ids = data.get('publicaly_available_post_id') or data.get('publicly_available_post_id') or []
            username = self.account_id.username
            vals = {'state': 'posted'}
            if ids:
                vals['external_post_id'] = str(ids[0])
                vals['permalink'] = ('https://www.tiktok.com/@%s/video/%s' % (username, ids[0])) if username \
                    else 'https://www.tiktok.com/video/%s' % ids[0]
            else:
                # private ("Only me") posts have no public ID: link to the profile
                vals['permalink'] = self.account_id.account_url or False
            self.write(vals)
            return True
        if status == 'FAILED':
            self.write({'state': 'failed', 'error_message': _('TikTok could not publish the video: %s',
                                                              data.get('fail_reason') or _('unknown reason'))})
            return True
        return False

    @api.model
    def _cron_check_tiktok_processing(self, limit=20):
        lines = self.search([('platform', '=', 'tiktok'), ('state', '=', 'processing')], limit=limit)
        posts = self.env['stratos.social.post']
        for line in lines:
            try:
                if line._check_tiktok_status():
                    posts |= line.post_id
            except TikTokApiError as e:
                _logger.info('TikTok status check failed for %s: %s', line.id, e)
                if e.auth_error:
                    line.write({'state': 'failed', 'error_message': str(e)})
                    line.account_id.sudo().write({'state': 'error', 'last_error': str(e)})
                    posts |= line.post_id
        posts._update_state_from_results()

    # ------------------------------------------------------------------
    # YouTube
    # ------------------------------------------------------------------
    def _publish_youtube(self):
        post = self.post_id
        video = post.video_ids[:1].sudo()
        if not video:
            raise ValueError(_('YouTube needs a video file.'))
        tags = list(dict.fromkeys(re.findall(r'(?<!\w)#(\w+)', post.message or '')))[:30]
        metadata = {
            'snippet': {
                'title': (post.youtube_title or post.name or '')[:100],
                'description': post.message or '',
                'categoryId': post.youtube_category or '22',
            },
            'status': {
                'privacyStatus': post.youtube_privacy or 'public',
                'selfDeclaredMadeForKids': bool(post.youtube_made_for_kids),
            },
        }
        if tags:
            metadata['snippet']['tags'] = tags
        client = YouTubeClient.from_env(self.env)
        token = self.account_id._get_youtube_token(client)
        result = client.upload_video(token, bytes(video.raw), video.mimetype or 'video/mp4', metadata)
        return result['id']

    # ------------------------------------------------------------------
    # Facebook
    # ------------------------------------------------------------------
    def _publish_facebook(self, client):
        post = self.post_id
        account = self.account_id
        token = account.sudo().access_token
        images = post.attachment_ids.filtered(lambda a: (a.mimetype or '').startswith('image/'))
        message = post.message or ''
        if not images:
            return client.fb_post_text(account.external_id, token, message, post.link_url)
        if post.link_url and post.link_url not in message:
            message = ('%s\n\n%s' % (message, post.link_url)).strip()
        if len(images) == 1:
            image = images.sudo()
            result = client.fb_upload_photo(
                account.external_id, token, image.name or 'image.jpg', bytes(image.raw), image.mimetype, caption=message)
            return result.get('post_id') or result['id']
        photo_ids = []
        for image in images.sudo():
            result = client.fb_upload_photo(
                account.external_id, token, image.name or 'image.jpg', bytes(image.raw), image.mimetype, published=False)
            photo_ids.append(result['id'])
        return client.fb_post_multi_photo(account.external_id, token, message, photo_ids)

    # ------------------------------------------------------------------
    # Instagram
    # ------------------------------------------------------------------
    def _get_public_base_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_str('web.base.url') or ''
        if not base_url.startswith('https://') or 'localhost' in base_url or '127.0.0.1' in base_url:
            raise ValueError(_(
                'Instagram downloads images from your Odoo, so Odoo must be reachable on a public '
                'https:// address. Current web.base.url is "%s".', base_url))
        return base_url.rstrip('/')

    def _get_public_jpeg_url(self, attachment):
        """Instagram only accepts JPEG images from a public URL."""
        attachment = attachment.sudo()
        if attachment.mimetype not in ('image/jpeg', 'image/jpg'):
            attachment = self._convert_to_jpeg(attachment)
        if not attachment.access_token:
            attachment.generate_access_token()
        return '%s/web/content/%s?access_token=%s' % (
            self._get_public_base_url(), attachment.id, attachment.access_token)

    def _convert_to_jpeg(self, attachment):
        from PIL import Image
        jpeg_name = (attachment.name or 'image').rsplit('.', 1)[0] + '.jpg'
        existing = self.env['ir.attachment'].sudo().search([
            ('res_model', '=', 'stratos.social.post'),
            ('res_id', '=', self.post_id.id),
            ('name', '=', 'ig_' + jpeg_name),
        ], limit=1)
        if existing:
            return existing
        image = Image.open(io.BytesIO(bytes(attachment.raw)))
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGBA')
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        else:
            image = image.convert('RGB')
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=92)
        return self.env['ir.attachment'].sudo().create({
            'name': 'ig_' + jpeg_name,
            'raw': buffer.getvalue(),
            'mimetype': 'image/jpeg',
            'res_model': 'stratos.social.post',
            'res_id': self.post_id.id,
        })

    def _wait_ig_container(self, client, container_id, token):
        for _attempt in range(IG_STATUS_RETRIES):
            status = client.ig_container_status(container_id, token)
            if status in (None, 'FINISHED', 'PUBLISHED'):
                return
            if status in ('ERROR', 'EXPIRED'):
                raise MetaApiError(_('Instagram could not process the image (status %s).', status))
            time.sleep(IG_STATUS_WAIT)
        raise MetaApiError(_('Instagram is still processing the image. Press "Retry Failed" in a minute.'))

    def _publish_instagram(self, client):
        post = self.post_id
        account = self.account_id
        token = account.sudo().access_token
        images = post.attachment_ids.filtered(lambda a: (a.mimetype or '').startswith('image/'))
        if not images:
            raise ValueError(_('Instagram needs at least one image.'))
        caption = post.message or ''
        ig_id = account.external_id
        if len(images) == 1:
            container = client.ig_create_image_container(ig_id, token, self._get_public_jpeg_url(images), caption)
        else:
            children = []
            for image in images:
                child = client.ig_create_image_container(
                    ig_id, token, self._get_public_jpeg_url(image), carousel_item=True)
                children.append(child)
            for child in children:
                self._wait_ig_container(client, child, token)
            container = client.ig_create_carousel_container(ig_id, token, children, caption)
        self._wait_ig_container(client, container, token)
        return client.ig_publish(ig_id, token, container)
