from odoo import api, fields, models
from odoo.exceptions import ValidationError


class VetClinic(models.Model):
    _inherit = "vet.clinic"

    opening_hour = fields.Float(default=8.0, tracking=True)
    closing_hour = fields.Float(default=18.0, tracking=True)
    appointment_buffer_minutes = fields.Integer(default=0, tracking=True)
    accepts_emergencies = fields.Boolean(default=True, tracking=True)
    emergency_phone = fields.Char(tracking=True)
    prescription_footer = fields.Text(help="Clinic-specific guidance printed or displayed with prescription information.")
    invoice_footer = fields.Text(help="Clinic-specific billing and payment guidance.")

    @api.constrains("opening_hour", "closing_hour", "appointment_buffer_minutes")
    def _check_operating_settings(self):
        for clinic in self:
            if not 0 <= clinic.opening_hour < clinic.closing_hour <= 24:
                raise ValidationError("Clinic opening time must be before closing time and within a 24-hour day.")
            if clinic.appointment_buffer_minutes < 0:
                raise ValidationError("Appointment buffer cannot be negative.")
