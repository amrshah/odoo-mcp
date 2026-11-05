import re

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

IG_CAPTION_LIMIT = 2200
IG_HASHTAG_LIMIT = 30
IG_CAROUSEL_LIMIT = 10
FB_PHOTO_LIMIT = 10
FB_MESSAGE_LIMIT = 63206
YT_TITLE_LIMIT = 100
TT_CAPTION_LIMIT = 2200
TT_PRIVACY = [
    ('PUBLIC_TO_EVERYONE', 'Everyone'),
    ('MUTUAL_FOLLOW_FRIENDS', 'Friends'),
    ('FOLLOWER_OF_CREATOR', 'Followers'),
    ('SELF_ONLY', 'Only me'),
]
YT_DESCRIPTION_LIMIT = 5000

YT_CATEGORIES = [
    ('1', 'Film & Animation'), ('2', 'Autos & Vehicles'), ('10', 'Music'), ('15', 'Pets & Animals'),
    ('17', 'Sports'), ('19', 'Travel & Events'), ('20', 'Gaming'), ('22', 'People & Blogs'),
    ('23', 'Comedy'), ('24', 'Entertainment'), ('25', 'News & Politics'), ('26', 'Howto & Style'),
    ('27', 'Education'), ('28', 'Science & Technology'), ('29', 'Nonprofits & Activism'),
]


class StratosSocialPost(models.Model):
    _name = 'stratos.social.post'
    _description = 'Social Media Post'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'calendar_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(compute='_compute_name', store=True)
    message = fields.Text(tracking=True)
    account_ids = fields.Many2many(
        'stratos.social.account', string='Post To', required=True, check_company=True,
        domain="[('company_id', '=', company_id), ('state', '=', 'connected')]")
    attachment_ids = fields.Many2many(
        'ir.attachment', 'stratos_social_post_attachment_rel', 'post_id', 'attachment_id',
        string='Images', help='JPEG or PNG images. Instagram needs at least one image.')
    video_ids = fields.Many2many(
        'ir.attachment', 'stratos_social_post_video_rel', 'post_id', 'attachment_id',
        string='Video', help='One video file (MP4 recommended) for YouTube and TikTok.')
    youtube_title = fields.Char('YouTube Title', help='Required for YouTube, up to 100 characters.')
    youtube_privacy = fields.Selection([
        ('public', 'Public'),
        ('unlisted', 'Unlisted'),
        ('private', 'Private'),
    ], string='YouTube Visibility', default='public')
    youtube_category = fields.Selection(YT_CATEGORIES, string='YouTube Category', default='22')
    youtube_made_for_kids = fields.Boolean('Made for Kids', help='YouTube legal requirement (COPPA).')
    # TikTok (fields and defaults follow TikTok's Content Sharing Guidelines:
    # privacy has no default, interactions start unchecked, commercial disclosure off)
    tiktok_privacy = fields.Selection(TT_PRIVACY, string='Who can view this video')
    tiktok_allow_comment = fields.Boolean('Allow Comment')
    tiktok_allow_duet = fields.Boolean('Allow Duet')
    tiktok_allow_stitch = fields.Boolean('Allow Stitch')
    tiktok_commercial = fields.Boolean('Disclose Commercial Content',
                                       help='Turn on if this video promotes yourself, a brand, product or service.')
    tiktok_brand_organic = fields.Boolean('Your Brand', help='You are promoting yourself or your own business.')
    tiktok_brand_content = fields.Boolean('Branded Content', help='You are promoting another brand or a third party.')
    tiktok_is_aigc = fields.Boolean('AI-generated Content', help='Adds TikTok\'s "AI-generated" label.')
    tiktok_account_info = fields.Html(compute='_compute_tiktok_account_info', sanitize=False)
    tiktok_comment_locked = fields.Boolean(compute='_compute_tiktok_account_info')
    tiktok_duet_locked = fields.Boolean(compute='_compute_tiktok_account_info')
    tiktok_stitch_locked = fields.Boolean(compute='_compute_tiktok_account_info')
    link_url = fields.Char('Link', help='Facebook shows a link preview. On Instagram links are not clickable.')
    post_method = fields.Selection([
        ('now', 'Post Now'),
        ('scheduled', 'Schedule Later'),
    ], default='now', required=True)
    scheduled_date = fields.Datetime('Scheduled For', tracking=True, copy=False)
    published_date = fields.Datetime(readonly=True, copy=False)
    calendar_date = fields.Datetime(compute='_compute_calendar_date', inverse='_inverse_calendar_date',
                                    store=True, string='Date')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('posting', 'Posting'),
        ('posted', 'Posted'),
        ('partial', 'Partly Posted'),
        ('failed', 'Failed'),
        ('cancel', 'Cancelled'),
    ], default='draft', required=True, tracking=True, copy=False, group_expand=True)
    live_post_ids = fields.One2many('stratos.social.live.post', 'post_id', string='Results', copy=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self.env.user, tracking=True)
    utm_campaign_id = fields.Many2one('utm.campaign', 'Campaign')
    has_instagram = fields.Boolean(compute='_compute_has_platforms')
    has_facebook = fields.Boolean(compute='_compute_has_platforms')
    has_youtube = fields.Boolean(compute='_compute_has_platforms')
    has_tiktok = fields.Boolean(compute='_compute_has_platforms')
    message_length = fields.Integer(compute='_compute_message_stats')
    hashtag_count = fields.Integer(compute='_compute_message_stats')
    warning_message = fields.Text(compute='_compute_warning_message')
    preview_html = fields.Html(compute='_compute_preview_html', sanitize=False)
    live_post_count = fields.Integer(compute='_compute_live_post_count')

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('message', 'attachment_ids', 'youtube_title', 'video_ids')
    def _compute_name(self):
        for post in self:
            text = (post.message or '').strip().split('\n')[0] or (post.youtube_title or '').strip()
            if len(text) > 60:
                text = text[:57] + '...'
            post.name = text or (_('Video post') if post.video_ids else
                                 _('Image post') if post.attachment_ids else _('New post'))

    @api.depends('state', 'scheduled_date', 'published_date', 'create_date')
    def _compute_calendar_date(self):
        for post in self:
            post.calendar_date = post.published_date or post.scheduled_date or post.create_date or fields.Datetime.now()

    def _inverse_calendar_date(self):
        """Dragging a post on the content calendar reschedules it."""
        for post in self:
            if post.state not in ('draft', 'scheduled'):
                raise UserError(_('Only draft or scheduled posts can be moved on the calendar.'))
            if post.state == 'scheduled' and post.calendar_date <= fields.Datetime.now():
                raise UserError(_('A scheduled post cannot be moved into the past.'))
            post.scheduled_date = post.calendar_date
            if post.state == 'draft':
                post.post_method = 'scheduled'

    @api.depends('account_ids.platform')
    def _compute_has_platforms(self):
        for post in self:
            platforms = set(post.account_ids.mapped('platform'))
            post.has_instagram = 'instagram' in platforms
            post.has_facebook = 'facebook' in platforms
            post.has_youtube = 'youtube' in platforms
            post.has_tiktok = 'tiktok' in platforms

    @api.depends('account_ids')
    def _compute_tiktok_account_info(self):
        labels = dict(TT_PRIVACY)
        for post in self:
            rows = []
            for account in post.account_ids.filtered(lambda a: a.platform == 'tiktok'):
                options = [labels.get(o, o) for o in (account.tiktok_privacy_options or '').split(',') if o]
                off = [name for name, flag in (('Comment', account.tiktok_comment_disabled),
                                               ('Duet', account.tiktok_duet_disabled),
                                               ('Stitch', account.tiktok_stitch_disabled)) if flag]
                rows.append(Markup('<div>Posting to <b>%s</b>%s%s%s</div>') % (
                    account.name,
                    Markup(' (@%s)') % account.username if account.username else '',
                    Markup(' &middot; allowed: %s') % ', '.join(options) if options else '',
                    Markup(' &middot; turned off on TikTok: %s') % ', '.join(off) if off else '',
                ))
            post.tiktok_account_info = Markup('').join(rows) if rows else False
            tiktok = post.account_ids.filtered(lambda a: a.platform == 'tiktok')
            post.tiktok_comment_locked = any(tiktok.mapped('tiktok_comment_disabled'))
            post.tiktok_duet_locked = any(tiktok.mapped('tiktok_duet_disabled'))
            post.tiktok_stitch_locked = any(tiktok.mapped('tiktok_stitch_disabled'))

    @api.depends('message')
    def _compute_message_stats(self):
        for post in self:
            text = post.message or ''
            post.message_length = len(text)
            post.hashtag_count = len(re.findall(r'(?<!\w)#\w+', text))

    @api.depends('live_post_ids')
    def _compute_live_post_count(self):
        for post in self:
            post.live_post_count = len(post.live_post_ids)

    @api.depends('message', 'attachment_ids', 'account_ids', 'link_url', 'video_ids', 'youtube_title',
                 'tiktok_privacy', 'tiktok_allow_comment', 'tiktok_allow_duet', 'tiktok_allow_stitch',
                 'tiktok_commercial', 'tiktok_brand_organic', 'tiktok_brand_content')
    def _compute_warning_message(self):
        for post in self:
            post.warning_message = '\n'.join(post._get_problems()) or False

    def _get_problems(self):
        """Human readable list of reasons this post cannot be published."""
        self.ensure_one()
        problems = []
        images = self.attachment_ids
        if not self.account_ids:
            problems.append(_('Select at least one account in "Post To".'))
        if not (self.message or '').strip() and not images and not self.video_ids:
            problems.append(_('Write a message or add an image.'))
        non_images = images.filtered(lambda a: not (a.mimetype or '').startswith('image/'))
        if non_images:
            problems.append(_('Only images are supported in this version (remove: %s).',
                              ', '.join(non_images.mapped('name'))))
        if self.has_instagram:
            if not images:
                problems.append(_('Instagram needs at least one image.'))
            if len(images) > IG_CAROUSEL_LIMIT:
                problems.append(_('Instagram allows at most %s images in one post.', IG_CAROUSEL_LIMIT))
            if self.message_length > IG_CAPTION_LIMIT:
                problems.append(_('Instagram caption is %(n)s characters; the limit is %(max)s.',
                                  n=self.message_length, max=IG_CAPTION_LIMIT))
            if self.hashtag_count > IG_HASHTAG_LIMIT:
                problems.append(_('Instagram allows at most %s hashtags.', IG_HASHTAG_LIMIT))
        if self.has_facebook:
            if len(images) > FB_PHOTO_LIMIT:
                problems.append(_('Use at most %s images for a Facebook post.', FB_PHOTO_LIMIT))
            if self.message_length > FB_MESSAGE_LIMIT:
                problems.append(_('Facebook message is too long.'))
        videos = self.video_ids
        non_videos = videos.filtered(lambda a: not (a.mimetype or '').startswith('video/'))
        if non_videos:
            problems.append(_('The Video field only takes video files (remove: %s).',
                              ', '.join(non_videos.mapped('name'))))
        if self.has_youtube:
            title = (self.youtube_title or '').strip()
            if len(videos) != 1:
                problems.append(_('YouTube needs exactly one video file.'))
            if not title:
                problems.append(_('Enter a YouTube Title.'))
            elif len(title) > YT_TITLE_LIMIT:
                problems.append(_('YouTube title is %(n)s characters; the limit is %(max)s.',
                                  n=len(title), max=YT_TITLE_LIMIT))
            if '<' in title + (self.message or '') or '>' in title + (self.message or ''):
                problems.append(_('YouTube does not accept the characters < and > in the title or description.'))
            if self.message_length > YT_DESCRIPTION_LIMIT:
                problems.append(_('YouTube description is limited to %s characters.', YT_DESCRIPTION_LIMIT))
        if self.has_tiktok:
            problems += self._get_tiktok_problems()
        if videos and not (self.has_youtube or self.has_tiktok):
            problems.append(_('Videos are published to YouTube and TikTok only: add one of those accounts or remove the video.'))
        disconnected = self.account_ids.filtered(lambda a: a.state != 'connected')
        if disconnected:
            problems.append(_('Reconnect these accounts first: %s', ', '.join(disconnected.mapped('display_name'))))
        return problems

    def _get_tiktok_problems(self):
        self.ensure_one()
        problems = []
        labels = dict(TT_PRIVACY)
        if len(self.video_ids) != 1:
            problems.append(_('TikTok needs exactly one video file.'))
        if not self.tiktok_privacy:
            problems.append(_('TikTok: choose "Who can view this video".'))
        if self.message_length > TT_CAPTION_LIMIT:
            problems.append(_('TikTok caption is limited to %s characters.', TT_CAPTION_LIMIT))
        if self.tiktok_commercial and not (self.tiktok_brand_organic or self.tiktok_brand_content):
            problems.append(_('TikTok: you turned on commercial content, so tick "Your Brand" and/or "Branded Content".'))
        if self.tiktok_commercial and self.tiktok_brand_content and self.tiktok_privacy == 'SELF_ONLY':
            problems.append(_('TikTok: branded content cannot be "Only me". Choose another visibility.'))
        audited = self.env['ir.config_parameter'].sudo().get_bool('stratos_social.tiktok_audited')
        if not audited and self.tiktok_privacy and self.tiktok_privacy != 'SELF_ONLY':
            problems.append(_('TikTok: until your TikTok app passes TikTok\'s audit, videos can only be posted '
                              'as "Only me" (and the TikTok account must be private).'))
        for account in self.account_ids.filtered(lambda a: a.platform == 'tiktok'):
            options = [o for o in (account.tiktok_privacy_options or '').split(',') if o]
            if self.tiktok_privacy and options and self.tiktok_privacy not in options:
                problems.append(_('TikTok account %(name)s does not allow "%(level)s" (allowed: %(opts)s).',
                                  name=account.name, level=labels.get(self.tiktok_privacy),
                                  opts=', '.join(labels.get(o, o) for o in options)))
            for allowed, disabled, label in ((self.tiktok_allow_comment, account.tiktok_comment_disabled, 'Comment'),
                                             (self.tiktok_allow_duet, account.tiktok_duet_disabled, 'Duet'),
                                             (self.tiktok_allow_stitch, account.tiktok_stitch_disabled, 'Stitch')):
                if allowed and disabled:
                    problems.append(_('TikTok account %(name)s has %(label)s turned off in its TikTok settings: untick "Allow %(label)s".',
                                      name=account.name, label=label))
        return problems

    @api.onchange('tiktok_commercial')
    def _onchange_tiktok_commercial(self):
        if not self.tiktok_commercial:
            self.tiktok_brand_organic = False
            self.tiktok_brand_content = False

    @api.depends('message', 'attachment_ids', 'link_url', 'account_ids', 'video_ids',
                 'youtube_title', 'youtube_privacy', 'tiktok_privacy', 'tiktok_brand_organic',
                 'tiktok_brand_content', 'tiktok_commercial')
    def _compute_preview_html(self):
        for post in self:
            first_image = post.attachment_ids.filtered(lambda a: (a.mimetype or '').startswith('image/'))[:1]
            img_html = Markup('')
            if first_image and first_image.id:
                img_html = Markup(
                    '<img src="/web/image/%s" style="width:100%%;max-height:260px;object-fit:cover;display:block"/>'
                ) % first_image.id
            more = len(post.attachment_ids) - 1
            more_html = Markup('<div class="text-muted small px-2">+%s more image(s)</div>') % more if more > 0 else Markup('')
            text = escape(post.message or '').replace('\n', Markup('<br/>'))
            text = Markup(re.sub(r'(?<![\w&])(#\w+)', r'<span style="color:#1877f2">\1</span>', str(text)))
            cards = []
            for account in post.account_ids[:4]:
                header_color = {'facebook': '#1877f2', 'instagram': '#c13584', 'youtube': '#ff0000', 'tiktok': '#000000'}[account.platform]
                link_html = Markup('')
                if account.platform == 'facebook' and post.link_url:
                    link_html = Markup('<div class="small px-2 pb-2" style="color:#1877f2">%s</div>') % post.link_url
                body = Markup('<div class="px-2 py-2" style="white-space:normal">%s</div>') % text
                if account.platform == 'tiktok':
                    video = post.video_ids[:1]
                    privacy = dict(TT_PRIVACY).get(post.tiktok_privacy) or _('choose who can view')
                    label = ''
                    if post.tiktok_commercial and post.tiktok_brand_content:
                        label = _('Paid partnership')
                    elif post.tiktok_commercial and post.tiktok_brand_organic:
                        label = _('Promotional content')
                    inner = Markup(
                        '<div style="background:#000;color:#fff;height:220px;display:flex;flex-direction:column;'
                        'justify-content:flex-end;padding:10px">'
                        '<div class="small" style="opacity:.7">%s</div>'
                        '<div class="fw-bold">@%s</div>'
                        '<div class="small" style="white-space:normal">%s</div>'
                        '<div class="small mt-1" style="opacity:.8">%s%s</div></div>'
                    ) % (video.name if video else _('No video yet'), account.username or account.name, text,
                         privacy, Markup(' &middot; %s') % label if label else '')
                elif account.platform == 'youtube':
                    video = post.video_ids[:1]
                    privacy = dict(self._fields['youtube_privacy'].selection).get(post.youtube_privacy) or ''
                    inner = Markup(
                        '<div style="background:#0f0f0f;color:#fff;height:170px;display:flex;flex-direction:column;'
                        'align-items:center;justify-content:center"><div style="font-size:42px;line-height:1">&#9654;</div>'
                        '<div class="small mt-1">%s</div></div>'
                        '<div class="px-2 pt-2 fw-bold">%s</div>'
                        '<div class="px-2 small text-muted">%s</div>'
                        '<div class="px-2 py-2 small" style="white-space:normal">%s</div>'
                    ) % (video.name if video else _('No video yet'), post.youtube_title or _('(title)'), privacy, text)
                elif account.platform == 'instagram':
                    inner = img_html + more_html + Markup('<div class="px-2 py-2"><b>%s</b> %s</div>') % (
                        account.username or account.name, text)
                else:
                    inner = body + img_html + more_html + link_html
                cards.append(Markup(
                    '<div class="border rounded mb-3" style="max-width:360px;background:#fff;overflow:hidden">'
                    '<div class="px-2 py-1 text-white small fw-bold" style="background:%s">%s</div>%s</div>'
                ) % (header_color, account.display_name, inner))
            post.preview_html = Markup('').join(cards) if cards else Markup(
                '<div class="text-muted">Select accounts to see a preview.</div>')

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('post_method', 'scheduled_date', 'state')
    def _check_scheduled_date(self):
        for post in self:
            if post.state == 'scheduled' and not post.scheduled_date:
                raise ValidationError(_('Set the date and time for a scheduled post.'))

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------
    def _ensure_publishable(self):
        for post in self:
            problems = post._get_problems()
            if problems:
                raise UserError(_('"%(name)s" cannot be published yet:\n\n- %(problems)s',
                                  name=post.name, problems='\n- '.join(problems)))

    def action_post_now(self):
        posts = self.filtered(lambda p: p.state in ('draft', 'scheduled', 'failed', 'partial'))
        posts._ensure_publishable()
        posts._publish()
        return True

    def action_schedule(self):
        for post in self:
            if post.state not in ('draft', 'failed'):
                raise UserError(_('Only draft posts can be scheduled.'))
            if not post.scheduled_date:
                raise UserError(_('Set "Scheduled For" first.'))
            if post.scheduled_date <= fields.Datetime.now():
                raise UserError(_('The scheduled time is in the past. Choose a future time or use Post Now.'))
        self._ensure_publishable()
        self.write({'state': 'scheduled'})
        return True

    def action_set_draft(self):
        self.filtered(lambda p: p.state in ('scheduled', 'failed', 'cancel')).write({'state': 'draft'})
        return True

    def action_cancel(self):
        if self.filtered(lambda p: p.state in ('posted', 'partial', 'posting')):
            raise UserError(_('Published posts cannot be cancelled. Delete them on Facebook / Instagram if needed.'))
        self.write({'state': 'cancel'})
        return True

    def action_retry_failed(self):
        for post in self:
            failed = post.live_post_ids.filtered(lambda l: l.state == 'failed')
            if not failed:
                continue
            failed.write({'state': 'ready', 'error_message': False})
            failed._publish()
            post._update_state_from_results()
        return True

    def action_view_results(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Results'),
            'res_model': 'stratos.social.live.post',
            'view_mode': 'list,form',
            'domain': [('post_id', '=', self.id)],
        }

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------
    def _publish(self):
        for post in self:
            post.state = 'posting'
            # one result line per account; reuse lines from an earlier failed attempt
            existing = post.live_post_ids
            to_publish = self.env['stratos.social.live.post']
            for account in post.account_ids:
                line = existing.filtered(lambda l: l.account_id == account)[:1]
                if line and line.state == 'posted':
                    continue
                if line:
                    line.write({'state': 'ready', 'error_message': False})
                else:
                    line = self.env['stratos.social.live.post'].create({'post_id': post.id, 'account_id': account.id})
                to_publish |= line
            to_publish._publish()
            post._update_state_from_results()

    def _update_state_from_results(self):
        for post in self:
            lines = post.live_post_ids.filtered(lambda l: l.account_id in post.account_ids)
            # TikTok accepts the video and finishes it in the background: counts as published
            posted = lines.filtered(lambda l: l.state in ('posted', 'processing'))
            failed = lines.filtered(lambda l: l.state == 'failed')
            if lines and len(posted) == len(lines):
                state = 'posted'
            elif posted:
                state = 'partial'
            else:
                state = 'failed'
            vals = {'state': state}
            if posted and not post.published_date:
                vals['published_date'] = fields.Datetime.now()
            post.write(vals)
            body = Markup('<ul>%s</ul>') % Markup('').join(
                Markup('<li>%s: %s%s</li>') % (
                    line.account_id.display_name,
                    dict(line._fields['state'].selection).get(line.state),
                    Markup(' &mdash; %s') % line.error_message if line.error_message else '',
                ) for line in lines)
            post.message_post(body=Markup('<b>%s</b>') % _('Publishing result') + body)
            if failed and post.user_id:
                post.activity_schedule(
                    'mail.mail_activity_data_todo',
                    summary=_('Social post failed on %s account(s)', len(failed)),
                    note=_('Open the post, fix the problem and press "Retry Failed".'),
                    user_id=post.user_id.id,
                )

    @api.model
    def _cron_publish_scheduled(self, limit=50):
        posts = self.search([
            ('state', '=', 'scheduled'),
            ('scheduled_date', '<=', fields.Datetime.now()),
        ], limit=limit, order='scheduled_date')
        self.env['stratos.social.live.post']._cron_check_tiktok_processing()
        in_cron = bool(self.env.context.get('ir_cron_progress_id'))
        if in_cron:
            self.env['ir.cron']._commit_progress(remaining=len(posts))
        for post in posts:
            problems = post._get_problems()
            if problems:
                post.write({'state': 'failed'})
                post.message_post(body=_('Scheduled publishing stopped: %s', ' '.join(problems)))
            else:
                post.with_company(post.company_id)._publish()
            if in_cron:
                self.env['ir.cron']._commit_progress(1)
