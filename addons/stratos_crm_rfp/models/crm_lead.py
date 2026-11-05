from datetime import timedelta

from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_amount, format_date

REMINDER_STAGES = [
    ('none', 'None'),
    ('first', 'First reminder'),
    ('due', 'Due today'),
    ('overdue', 'Overdue'),
]
STAGE_ORDER = {key: index for index, (key, _label) in enumerate(REMINDER_STAGES)}
DEFAULT_REMINDER_DAYS = 3

# (task key, date field, status field, done value, responsible field, stage field, activity xmlid, label)
RFP_TASKS = {
    'questionnaire': ('rfp_questionnaire_date', 'rfp_questionnaire_status', 'sent', 'rfp_questionnaire_user_id',
                      'rfp_q_reminder_stage', 'stratos_crm_rfp.mail_activity_type_rfp_questionnaire'),
    'proposal': ('rfp_submission_date', 'rfp_status', 'submitted', 'rfp_proposal_user_id',
                 'rfp_p_reminder_stage', 'stratos_crm_rfp.mail_activity_type_rfp_proposal'),
}


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    is_international_rfp = fields.Boolean('International RFP', tracking=True)
    rfp_questionnaire_date = fields.Date(
        'Questionnaire Date', tracking=True,
        help='Last date to send the questionnaire / clarification questions to the client.')
    rfp_submission_date = fields.Date(
        'Last Submission Date', tracking=True,
        help='Deadline for submitting the proposal.')
    rfp_document_ids = fields.Many2many(
        'ir.attachment', 'crm_lead_rfp_document_rel', 'lead_id', 'attachment_id',
        string='RFP Documents', help='Initial documents received with the RFP.')
    rfp_questionnaire_ids = fields.Many2many(
        'ir.attachment', 'crm_lead_rfp_questionnaire_rel', 'lead_id', 'attachment_id',
        string='Questionnaire')
    rfp_proposal_ids = fields.Many2many(
        'ir.attachment', 'crm_lead_rfp_proposal_rel', 'lead_id', 'attachment_id',
        string='Proposal')

    # Status
    rfp_questionnaire_status = fields.Selection([
        ('not_sent', 'Not Sent'),
        ('sent', 'Sent'),
    ], string='Questionnaire Status', default='not_sent', tracking=True)
    rfp_questionnaire_sent_on = fields.Date('Questionnaire Sent On', readonly=True, copy=False, tracking=True)
    rfp_status = fields.Selection([
        ('not_submitted', 'Not Submitted'),
        ('submitted', 'Submitted'),
    ], string='Submission Status', default='not_submitted', tracking=True)
    rfp_submitted_on = fields.Date('Submitted On', readonly=True, copy=False, tracking=True)
    rfp_days_left = fields.Integer('Days to Submission', compute='_compute_rfp_days_left')

    # Reminders
    rfp_questionnaire_user_id = fields.Many2one(
        'res.users', 'Questionnaire Responsible', tracking=True, domain=[('share', '=', False)],
        compute='_compute_rfp_responsibles', store=True, readonly=False,
        help='Receives the reminders when the questionnaire has not been sent.')
    rfp_proposal_user_id = fields.Many2one(
        'res.users', 'Proposal Responsible', tracking=True, domain=[('share', '=', False)],
        compute='_compute_rfp_responsibles', store=True, readonly=False,
        help='Receives the reminders when the proposal has not been submitted.')
    rfp_notify_user_ids = fields.Many2many(
        'res.users', 'crm_lead_rfp_notify_user_rel', 'lead_id', 'user_id', string='Also Remind',
        domain=[('share', '=', False)], help='Copied on every reminder of this RFP (e.g. a manager).')
    rfp_q_reminder_stage = fields.Selection(REMINDER_STAGES, default='none', copy=False,
                                            string='Questionnaire Reminder Sent')
    rfp_p_reminder_stage = fields.Selection(REMINDER_STAGES, default='none', copy=False,
                                            string='Proposal Reminder Sent')

    @api.depends('is_international_rfp', 'user_id')
    def _compute_rfp_responsibles(self):
        """Default both responsibles to the salesperson; never overwrite a choice."""
        for lead in self:
            if lead.is_international_rfp and lead.user_id:
                if not lead.rfp_questionnaire_user_id:
                    lead.rfp_questionnaire_user_id = lead.user_id
                if not lead.rfp_proposal_user_id:
                    lead.rfp_proposal_user_id = lead.user_id

    @api.depends('rfp_submission_date', 'rfp_status')
    def _compute_rfp_days_left(self):
        today = fields.Date.context_today(self)
        for lead in self:
            if lead.rfp_submission_date and lead.rfp_status != 'submitted':
                lead.rfp_days_left = (lead.rfp_submission_date - today).days
            else:
                lead.rfp_days_left = 0

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------
    @api.constrains('rfp_status', 'rfp_proposal_ids', 'is_international_rfp')
    def _check_rfp_proposal_before_submitted(self):
        for lead in self:
            if lead.is_international_rfp and lead.rfp_status == 'submitted' and not lead.rfp_proposal_ids:
                raise ValidationError(_(
                    '"%s": attach the proposal before marking the RFP as Submitted.', lead.name))

    @api.constrains('rfp_questionnaire_status', 'rfp_questionnaire_ids', 'is_international_rfp')
    def _check_rfp_questionnaire_before_sent(self):
        for lead in self:
            if lead.is_international_rfp and lead.rfp_questionnaire_status == 'sent' and not lead.rfp_questionnaire_ids:
                raise ValidationError(_(
                    '"%s": attach the questionnaire before marking it as Sent.', lead.name))

    @api.onchange('rfp_questionnaire_date', 'rfp_submission_date')
    def _onchange_rfp_dates(self):
        if self.rfp_questionnaire_date and self.rfp_submission_date \
                and self.rfp_questionnaire_date > self.rfp_submission_date:
            return {'warning': {
                'title': _('Check the RFP dates'),
                'message': _('The questionnaire date is after the last submission date.'),
            }}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        today = fields.Date.context_today(self)
        for vals in vals_list:
            if vals.get('rfp_status') == 'submitted' and not vals.get('rfp_submitted_on'):
                vals['rfp_submitted_on'] = today
            if vals.get('rfp_questionnaire_status') == 'sent' and not vals.get('rfp_questionnaire_sent_on'):
                vals['rfp_questionnaire_sent_on'] = today
        leads = super().create(vals_list)
        leads._rfp_link_attachments()
        return leads

    def write(self, vals):
        today = fields.Date.context_today(self)
        if 'rfp_status' in vals:
            vals['rfp_submitted_on'] = today if vals['rfp_status'] == 'submitted' else False
        if 'rfp_questionnaire_status' in vals:
            vals['rfp_questionnaire_sent_on'] = today if vals['rfp_questionnaire_status'] == 'sent' else False
        # a new date or re-opened task starts the reminder cycle again
        if 'rfp_questionnaire_date' in vals or vals.get('rfp_questionnaire_status') == 'not_sent':
            vals['rfp_q_reminder_stage'] = 'none'
        if 'rfp_submission_date' in vals or vals.get('rfp_status') == 'not_submitted':
            vals['rfp_p_reminder_stage'] = 'none'
        res = super().write(vals)
        if {'rfp_document_ids', 'rfp_questionnaire_ids', 'rfp_proposal_ids'} & set(vals):
            self._rfp_link_attachments()
        if vals.get('rfp_questionnaire_status') == 'sent':
            self._rfp_close_activities('questionnaire')
        if vals.get('rfp_status') == 'submitted':
            self._rfp_close_activities('proposal')
        if 'rfp_questionnaire_date' in vals or 'rfp_questionnaire_user_id' in vals:
            self._rfp_update_open_activities('questionnaire')
        if 'rfp_submission_date' in vals or 'rfp_proposal_user_id' in vals:
            self._rfp_update_open_activities('proposal')
        if 'is_international_rfp' in vals and not vals['is_international_rfp']:
            self._rfp_close_activities('questionnaire')
            self._rfp_close_activities('proposal')
        return res

    def _rfp_link_attachments(self):
        """Attach uploaded files to the lead itself, so they also appear in the
        lead's attachments (paperclip) and follow its access rights."""
        for lead in self:
            files = lead.rfp_document_ids | lead.rfp_questionnaire_ids | lead.rfp_proposal_ids
            unlinked = files.filtered(lambda a: not a.res_id or a.res_model != 'crm.lead')
            if unlinked:
                unlinked.sudo().write({'res_model': 'crm.lead', 'res_id': lead.id})

    # ------------------------------------------------------------------
    # Reminders
    # ------------------------------------------------------------------
    def _rfp_activities(self, task):
        activity_type = self.env.ref(RFP_TASKS[task][5], raise_if_not_found=False)
        return self.activity_ids.filtered(lambda a: activity_type and a.activity_type_id == activity_type)

    def _rfp_close_activities(self, task):
        for lead in self:
            activities = lead._rfp_activities(task)
            if activities:
                done = _('Questionnaire sent.') if task == 'questionnaire' else _('Proposal submitted.')
                activities.action_feedback(feedback=done)

    def _rfp_update_open_activities(self, task):
        date_field, _status, _done, user_field = RFP_TASKS[task][:4]
        for lead in self:
            activities = lead._rfp_activities(task)
            if not activities:
                continue
            vals = {}
            if lead[date_field]:
                vals['date_deadline'] = lead[date_field]
            if lead[user_field]:
                vals['user_id'] = lead[user_field].id
            if vals:
                activities.write(vals)

    @api.model
    def _rfp_reminder_days(self):
        return self.env['ir.config_parameter'].sudo().get_int(
            'stratos_crm_rfp.reminder_days', DEFAULT_REMINDER_DAYS)

    @staticmethod
    def _rfp_target_stage(days_left, reminder_days):
        if days_left < 0:
            return 'overdue'
        if days_left == 0:
            return 'due'
        if days_left <= reminder_days:
            return 'first'
        return 'none'

    def _rfp_send_reminder(self, task, stage, days_left):
        """Create (once) a To-Do for the responsible and notify them + 'Also Remind'."""
        self.ensure_one()
        date_field, _status, _done, user_field, _stage_field, activity_xmlid = RFP_TASKS[task]
        user = self[user_field] or self.user_id
        deadline = self[date_field]
        what = _('send the questionnaire') if task == 'questionnaire' else _('submit the proposal')
        if not self._rfp_activities(task) and user:
            self.activity_schedule(
                activity_xmlid, date_deadline=deadline, user_id=user.id,
                summary=_('RFP: %s', what.capitalize()))
        if stage == 'overdue':
            when = _('was due on %(date)s (%(n)s day(s) overdue)', date=format_date(self.env, deadline), n=-days_left)
        elif stage == 'due':
            when = _('is due today (%s)', format_date(self.env, deadline))
        else:
            when = _('is due on %(date)s (in %(n)s day(s))', date=format_date(self.env, deadline), n=days_left)
        partners = (user | self.rfp_notify_user_ids).partner_id
        body = Markup('<p><b>%s</b></p><p>%s</p>') % (
            _('RFP reminder'),
            _('%(who)s: please %(what)s for "%(rfp)s". It %(when)s.',
              who=user.name if user else _('No responsible set'), what=what, rfp=self.name, when=when))
        self.message_post(body=body, partner_ids=partners.ids,
                          message_type='comment', subtype_xmlid='mail.mt_note')

    @api.model
    def _cron_rfp_reminders(self):
        today = fields.Date.context_today(self)
        reminder_days = self._rfp_reminder_days()
        leads = self.search([('is_international_rfp', '=', True), ('won_status', '!=', 'lost')])
        for lead in leads:
            for task, (date_field, status_field, done_value, _user, stage_field, _xmlid) in RFP_TASKS.items():
                if not lead[date_field] or lead[status_field] == done_value:
                    continue
                if task == 'questionnaire' and lead.rfp_status == 'submitted':
                    continue  # proposal already in: questionnaire no longer matters
                days_left = (lead[date_field] - today).days
                target = self._rfp_target_stage(days_left, reminder_days)
                if STAGE_ORDER[target] > STAGE_ORDER[lead[stage_field] or 'none']:
                    lead._rfp_send_reminder(task, target, days_left)
                    lead[stage_field] = target

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @api.model
    def get_rfp_dashboard_data(self):
        today = fields.Date.context_today(self)
        week = today + timedelta(days=7)
        month_start = today.replace(day=1)
        base = [('is_international_rfp', '=', True)]
        open_ = base + [('rfp_status', '=', 'not_submitted')]
        currency = self.env.company.currency_id

        def kpi(key, label, domain, hint='', tone='primary', icon='description'):
            leads = self.search(domain)
            return {
                'key': key, 'label': label, 'count': len(leads), 'hint': hint, 'tone': tone, 'icon': icon,
                'amount': format_amount(self.env, sum(leads.mapped('expected_revenue')), currency),
                'domain': domain,
            }

        overdue_domain = open_ + ['|', ('rfp_submission_date', '<', today),
                                  '&', ('rfp_questionnaire_status', '=', 'not_sent'),
                                  ('rfp_questionnaire_date', '<', today)]
        kpis = [
            kpi('queue', _('In Queue (Not Submitted)'), open_, _('open RFPs'), 'primary', 'pending_actions'),
            kpi('questionnaire', _('Questionnaire Not Sent'), open_ + [('rfp_questionnaire_status', '=', 'not_sent')],
                _('questions still to send'), 'info', 'help'),
            kpi('due_week', _('Due in 7 Days'), open_ + [('rfp_submission_date', '>=', today),
                                                         ('rfp_submission_date', '<=', week)],
                _('submission deadline this week'), 'warning', 'schedule'),
            kpi('overdue', _('Overdue'), overdue_domain, _('a deadline has passed'), 'danger', 'warning'),
            kpi('submitted', _('Submitted'), base + [('rfp_status', '=', 'submitted')],
                _('%s this month', self.search_count(base + [('rfp_submitted_on', '>=', month_start)])),
                'success', 'task_alt'),
        ]

        upcoming = []
        for lead in self.search(open_):
            deadlines = []
            if lead.rfp_questionnaire_status == 'not_sent' and lead.rfp_questionnaire_date:
                deadlines.append((lead.rfp_questionnaire_date, 'questionnaire', lead.rfp_questionnaire_user_id))
            if lead.rfp_submission_date:
                deadlines.append((lead.rfp_submission_date, 'proposal', lead.rfp_proposal_user_id))
            if not deadlines:
                upcoming.append({'id': lead.id, 'name': lead.name, 'client': lead.partner_id.name or lead.partner_name or '',
                                 'task': _('No deadline set'), 'task_key': 'none', 'date': '', 'days_left': None, 'responsible': '',
                                 'amount': format_amount(self.env, lead.expected_revenue, currency),
                                 'questionnaire': lead.rfp_questionnaire_status, 'sort': (1, today)})
                continue
            date, task_key, user = min(deadlines, key=lambda d: d[0])
            upcoming.append({
                'id': lead.id, 'name': lead.name, 'client': lead.partner_id.name or lead.partner_name or '',
                'task': _('Send questionnaire') if task_key == 'questionnaire' else _('Submit proposal'),
                'task_key': task_key, 'date': format_date(self.env, date), 'days_left': (date - today).days,
                'responsible': (user or lead.user_id).name or '',
                'amount': format_amount(self.env, lead.expected_revenue, currency),
                'questionnaire': lead.rfp_questionnaire_status, 'sort': (0, date),
            })
        upcoming.sort(key=lambda row: row.pop('sort'))

        workload = {}
        for lead in self.search(open_):
            tasks = []
            if lead.rfp_questionnaire_status == 'not_sent' and lead.rfp_questionnaire_date:
                tasks.append(('questionnaire', lead.rfp_questionnaire_user_id or lead.user_id))
            tasks.append(('proposal', lead.rfp_proposal_user_id or lead.user_id))
            for kind, user in tasks:
                row = workload.setdefault(user.id or 0, {
                    'user_id': user.id or False, 'name': user.name or _('Unassigned'),
                    'questionnaire': 0, 'proposal': 0})
                row[kind] += 1
        workload = sorted(workload.values(), key=lambda r: -(r['questionnaire'] + r['proposal']))

        submitted = [{
            'id': lead.id, 'name': lead.name, 'client': lead.partner_id.name or lead.partner_name or '',
            'date': format_date(self.env, lead.rfp_submitted_on) if lead.rfp_submitted_on else '',
        } for lead in self.search(base + [('rfp_status', '=', 'submitted')],
                                  order='rfp_submitted_on desc, id desc', limit=5)]

        return {
            'kpis': kpis,
            'upcoming': upcoming,
            'workload': workload,
            'submitted': submitted,
            'reminder_days': self._rfp_reminder_days(),
            'list_view_id': self.env.ref('stratos_crm_rfp.crm_lead_view_list_rfp').id,
        }
