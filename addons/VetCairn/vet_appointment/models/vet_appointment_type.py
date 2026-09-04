from odoo import fields, models


class VetAppointmentType(models.Model):
    _name = "vet.appointment.type"
    _description = "Veterinary Appointment Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    duration = fields.Float(
        string="Default Duration (Hours)", default=0.5, required=True
    )
    color = fields.Integer(default=0)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    description = fields.Text(translate=True)

    _code_company_unique = models.Constraint(
        "UNIQUE(code, company_id)",
        "Appointment type codes must be unique within a company.",
    )
    _duration_positive = models.Constraint(
        "CHECK(duration > 0)", "The default duration must be greater than zero."
    )
