from odoo import fields, models

from .crm_lead import DEFAULT_REMINDER_DAYS


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    rfp_reminder_days = fields.Integer(
        'First RFP Reminder (days before)', config_parameter='stratos_crm_rfp.reminder_days',
        default=DEFAULT_REMINDER_DAYS,
        help='How many days before the questionnaire date / last submission date the first reminder is sent. '
             'Further reminders follow on the due date and the day after if still pending.')
