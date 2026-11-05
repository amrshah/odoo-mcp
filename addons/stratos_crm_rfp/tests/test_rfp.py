from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, Form, tagged


@tagged('post_install', '-at_install')
class TestInternationalRfp(TransactionCase):

    def _file(self, name):
        return self.env['ir.attachment'].create({'name': name, 'raw': b'%PDF-1.4 test', 'mimetype': 'application/pdf'})

    def test_rfp_flow(self):
        today = fields.Date.context_today(self.env['crm.lead'])
        lead = self.env['crm.lead'].create({
            'name': 'Harlandale ISD ERP RFP', 'type': 'opportunity', 'is_international_rfp': True,
            'rfp_questionnaire_date': today + timedelta(days=3),
            'rfp_submission_date': today + timedelta(days=10),
            'rfp_document_ids': [(6, 0, self._file('RFP 270005.pdf').ids)],
        })
        self.assertEqual(lead.rfp_status, 'not_submitted')
        self.assertEqual(lead.rfp_days_left, 10)
        # files are linked to the lead itself (show in its attachments)
        self.assertEqual(lead.rfp_document_ids.res_model, 'crm.lead')
        self.assertEqual(lead.rfp_document_ids.res_id, lead.id)

        lead.rfp_questionnaire_ids = [(6, 0, self._file('Questions.docx').ids)]
        self.assertEqual(lead.rfp_questionnaire_ids.res_id, lead.id)

        # cannot be submitted without a proposal
        with self.assertRaises(ValidationError):
            lead.rfp_status = 'submitted'

        lead.rfp_proposal_ids = [(6, 0, self._file('Proposal.pdf').ids)]
        lead.rfp_status = 'submitted'
        self.assertEqual(lead.rfp_submitted_on, today)
        self.assertEqual(lead.rfp_days_left, 0)

        lead.rfp_status = 'not_submitted'
        self.assertFalse(lead.rfp_submitted_on)

    def test_three_separate_slots(self):
        doc, q, prop = self._file('rfp.pdf'), self._file('q.pdf'), self._file('p.pdf')
        lead = self.env['crm.lead'].create({
            'name': 'X', 'is_international_rfp': True,
            'rfp_document_ids': [(6, 0, doc.ids)], 'rfp_questionnaire_ids': [(6, 0, q.ids)],
            'rfp_proposal_ids': [(6, 0, prop.ids)], 'rfp_status': 'submitted'})
        self.assertEqual(lead.rfp_document_ids, doc)
        self.assertEqual(lead.rfp_questionnaire_ids, q)
        self.assertEqual(lead.rfp_proposal_ids, prop)
        self.assertTrue(lead.rfp_submitted_on)

    def test_normal_lead_unaffected(self):
        lead = self.env['crm.lead'].create({'name': 'Local lead', 'rfp_status': 'submitted'})
        self.assertFalse(lead.is_international_rfp)  # no proposal needed when not an RFP

    def test_date_warning_onchange(self):
        today = fields.Date.context_today(self.env['crm.lead'])
        lead = self.env['crm.lead'].new({
            'name': 'Y', 'is_international_rfp': True,
            'rfp_questionnaire_date': today + timedelta(days=9), 'rfp_submission_date': today + timedelta(days=2)})
        result = lead._onchange_rfp_dates()
        self.assertIn('warning', result)

    def test_form_and_menu_action(self):
        action = self.env.ref('stratos_crm_rfp.action_crm_international_rfp')
        lead = self.env['crm.lead'].with_context(**{'default_is_international_rfp': True,
                                                    'default_type': 'opportunity'}).create({'name': 'From menu'})
        self.assertTrue(lead.is_international_rfp)
        self.assertIn(lead, self.env['crm.lead'].search(eval(action.domain)))
        with Form(self.env['crm.lead'].with_context(default_type='opportunity')) as f:
            f.name = 'Form RFP'
            f.is_international_rfp = True
            f.rfp_submission_date = fields.Date.context_today(self.env['crm.lead'])
        self.assertTrue(f.record.is_international_rfp)


@tagged('post_install', '-at_install')
class TestRfpReminders(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.context_today(cls.env['crm.lead'])
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        grp = cls.env.ref('sales_team.group_sale_salesman')
        cls.sales = Users.create({'name': 'Sara Sales', 'login': 'sara', 'email': 'sara@example.com',
                                  'group_ids': [(6, 0, grp.ids)]})
        cls.writer = Users.create({'name': 'Wasi Writer', 'login': 'wasi', 'email': 'wasi@example.com',
                                   'group_ids': [(6, 0, grp.ids)]})
        cls.boss = Users.create({'name': 'Boss Manager', 'login': 'boss', 'email': 'boss@example.com',
                                 'group_ids': [(6, 0, grp.ids)]})
        cls.env['ir.config_parameter'].sudo().set_int('stratos_crm_rfp.reminder_days', 3)

    def _file(self, name):
        return self.env['ir.attachment'].create({'name': name, 'raw': b'%PDF-1.4', 'mimetype': 'application/pdf'})

    def _lead(self, q_days, s_days, **vals):
        base = {'name': 'RFP %s/%s' % (q_days, s_days), 'type': 'opportunity', 'is_international_rfp': True,
                'user_id': self.sales.id,
                'rfp_questionnaire_date': self.today + timedelta(days=q_days),
                'rfp_submission_date': self.today + timedelta(days=s_days)}
        base.update(vals)
        return self.env['crm.lead'].create(base)

    def _rfp_activity(self, lead, xmlid):
        return lead.activity_ids.filtered(lambda a: a.activity_type_id == self.env.ref(xmlid))

    def test_responsibles_default_to_salesperson(self):
        lead = self._lead(10, 20)
        self.assertEqual(lead.rfp_questionnaire_user_id, self.sales)
        self.assertEqual(lead.rfp_proposal_user_id, self.sales)
        lead.user_id = self.boss  # does not overwrite a set responsible
        self.assertEqual(lead.rfp_proposal_user_id, self.sales)

    def test_first_reminder_goes_to_right_people(self):
        lead = self._lead(2, 20, rfp_questionnaire_user_id=self.writer.id,
                          rfp_notify_user_ids=[(6, 0, self.boss.ids)])
        self.env['crm.lead']._cron_rfp_reminders()
        q_act = self._rfp_activity(lead, 'stratos_crm_rfp.mail_activity_type_rfp_questionnaire')
        self.assertEqual(q_act.user_id, self.writer)
        self.assertEqual(q_act.date_deadline, lead.rfp_questionnaire_date)
        self.assertEqual(lead.rfp_q_reminder_stage, 'first')
        # proposal is 20 days away: no reminder yet
        self.assertFalse(self._rfp_activity(lead, 'stratos_crm_rfp.mail_activity_type_rfp_proposal'))
        self.assertEqual(lead.rfp_p_reminder_stage, 'none')
        msg = lead.message_ids.filtered(lambda m: 'RFP reminder' in (m.body or ''))
        self.assertEqual(len(msg), 1)
        self.assertEqual(set(msg.partner_ids.ids), {self.writer.partner_id.id, self.boss.partner_id.id})
        self.assertIn('send the questionnaire', msg.body)

    def test_no_duplicate_then_due_and_overdue(self):
        lead = self._lead(2, 1)  # questionnaire after submission, proposal due tomorrow
        Lead = self.env['crm.lead']
        Lead._cron_rfp_reminders()
        Lead._cron_rfp_reminders()  # second run same day: nothing new
        msgs = lead.message_ids.filtered(lambda m: 'RFP reminder' in (m.body or ''))
        self.assertEqual(len(msgs), 2)  # one questionnaire + one proposal
        self.assertEqual(len(lead.activity_ids), 2)
        # deadline reached
        lead.write({'rfp_submission_date': self.today})
        self.assertEqual(lead.rfp_p_reminder_stage, 'none')  # date change restarts the cycle
        Lead._cron_rfp_reminders()
        self.assertEqual(lead.rfp_p_reminder_stage, 'due')
        p_act = self._rfp_activity(lead, 'stratos_crm_rfp.mail_activity_type_rfp_proposal')
        self.assertEqual(len(p_act), 1)
        self.assertEqual(p_act.date_deadline, self.today)  # activity follows the new date
        lead.write({'rfp_submission_date': self.today - timedelta(days=1)})
        Lead._cron_rfp_reminders()
        self.assertEqual(lead.rfp_p_reminder_stage, 'overdue')
        last = lead.message_ids.filtered(lambda m: 'RFP reminder' in (m.body or ''))[:1]
        self.assertIn('overdue', last.body)

    def test_done_closes_activities_and_stops_reminders(self):
        lead = self._lead(1, 2)
        Lead = self.env['crm.lead']
        Lead._cron_rfp_reminders()
        self.assertEqual(len(lead.activity_ids), 2)
        with self.assertRaises(ValidationError):
            lead.rfp_questionnaire_status = 'sent'  # questionnaire file needed first
        lead.write({'rfp_questionnaire_ids': [(6, 0, self._file('q.pdf').ids)], 'rfp_questionnaire_status': 'sent'})
        self.assertTrue(lead.rfp_questionnaire_sent_on)
        self.assertFalse(self._rfp_activity(lead, 'stratos_crm_rfp.mail_activity_type_rfp_questionnaire'))
        lead.write({'rfp_proposal_ids': [(6, 0, self._file('p.pdf').ids)], 'rfp_status': 'submitted'})
        self.assertFalse(lead.activity_ids)
        before = len(lead.message_ids)
        lead.write({'rfp_submission_date': self.today - timedelta(days=3)})
        Lead._cron_rfp_reminders()
        self.assertFalse(lead.message_ids.filtered(
            lambda m: 'RFP reminder' in (m.body or '') and m.id > max(lead.message_ids.ids[-before:] or [0])))
        self.assertFalse(lead.activity_ids)

    def test_responsible_change_moves_open_activity(self):
        lead = self._lead(1, 30)
        self.env['crm.lead']._cron_rfp_reminders()
        lead.rfp_questionnaire_user_id = self.writer
        act = self._rfp_activity(lead, 'stratos_crm_rfp.mail_activity_type_rfp_questionnaire')
        self.assertEqual(act.user_id, self.writer)

    def test_lost_and_normal_leads_ignored(self):
        lost = self._lead(0, 0)
        lost.action_set_lost()
        normal = self.env['crm.lead'].create({'name': 'Normal', 'type': 'opportunity',
                                              'rfp_submission_date': self.today})
        self.env['crm.lead']._cron_rfp_reminders()
        self.assertFalse(lost.with_context(active_test=False).activity_ids)
        self.assertFalse(normal.activity_ids)

    def test_dashboard_data(self):
        self.env['crm.lead'].search([('is_international_rfp', '=', True)]).write({'is_international_rfp': False})
        self._lead(2, 5, expected_revenue=1000)                      # due this week
        self._lead(-2, 20, expected_revenue=500)                     # questionnaire overdue
        self._lead(-10, -1)                                           # submission overdue
        self._lead(-30, -20, rfp_proposal_ids=[(6, 0, self._file('p.pdf').ids)], rfp_status='submitted')
        data = self.env['crm.lead'].get_rfp_dashboard_data()
        kpis = {k['key']: k['count'] for k in data['kpis']}
        self.assertEqual(kpis, {'queue': 3, 'questionnaire': 3, 'due_week': 1, 'overdue': 2, 'submitted': 1})
        self.assertEqual(len(data['upcoming']), 3)
        self.assertEqual(data['upcoming'][0]['days_left'], -10)  # earliest deadline first
        self.assertEqual(data['upcoming'][0]['task_key'], 'questionnaire')
        self.assertEqual(data['workload'][0]['name'], 'Sara Sales')
        self.assertEqual(data['workload'][0]['proposal'], 3)
        self.assertEqual(len(data['submitted']), 1)
        # every KPI domain is a valid search
        for k in data['kpis']:
            self.assertEqual(self.env['crm.lead'].search_count(k['domain']), k['count'])
