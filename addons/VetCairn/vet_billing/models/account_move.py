from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    vet_patient_id = fields.Many2one("vet.patient", string="Patient", index=True, tracking=True)
    vet_clinic_id = fields.Many2one("vet.clinic", string="Clinic", index=True, tracking=True)
    vet_appointment_id = fields.Many2one("vet.appointment", string="Appointment", index=True)
    vet_encounter_id = fields.Many2one("vet.encounter", string="Clinical Encounter", index=True)
    vet_charge_ids = fields.One2many("vet.charge", "invoice_id", string="Veterinary Charges")
