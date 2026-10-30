from odoo import fields, models


class VetPatient(models.Model):
    _inherit = "vet.patient"

    exam_ids = fields.One2many("vet.exam", "patient_id", "Structured Exams")
