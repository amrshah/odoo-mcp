from odoo import fields, models


class VetReminderType(models.Model):
    _name = "vet.reminder.type"
    _description = "Veterinary Reminder Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    default_channel = fields.Selection([("email","Email"),("sms","SMS"),("phone","Phone Call"),("mail","Postal Mail"),("internal","Internal")], default="email", required=True)
    default_lead_days = fields.Integer(string="Default Lead Time (Days)", default=7)
    subject_template = fields.Char()
    message_template = fields.Text()

    _code_company_unique = models.Constraint("UNIQUE(code, company_id)", "Reminder type codes must be unique within a company.")
    _lead_nonnegative = models.Constraint("CHECK(default_lead_days >= 0)", "Reminder lead time cannot be negative.")
