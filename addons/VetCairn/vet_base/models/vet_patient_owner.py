from odoo import api, fields, models
from odoo.exceptions import ValidationError


class VetPatientOwner(models.Model):
    _name = "vet.patient.owner"
    _description = "Patient Ownership"
    _order = "is_primary desc, start_date desc, id"

    patient_id = fields.Many2one(
        "vet.patient", required=True, index=True, ondelete="cascade"
    )
    partner_id = fields.Many2one(
        "res.partner", string="Client", required=True, index=True, ondelete="restrict"
    )
    relationship_type = fields.Selection(
        [
            ("owner", "Owner"),
            ("co_owner", "Co-owner"),
            ("guardian", "Guardian"),
            ("rescue", "Rescue/Shelter"),
            ("other", "Other"),
        ],
        required=True,
        default="owner",
    )
    is_primary = fields.Boolean(string="Primary Owner", default=False)
    start_date = fields.Date(default=fields.Date.context_today)
    end_date = fields.Date()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(related="patient_id.company_id", store=True)

    _patient_partner_unique = models.Constraint(
        "UNIQUE(patient_id, partner_id)",
        "A client can only be linked once to the same patient.",
    )

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for ownership in self:
            if (
                ownership.start_date
                and ownership.end_date
                and ownership.end_date < ownership.start_date
            ):
                raise ValidationError("The ownership end date cannot precede its start date.")

    @api.constrains("is_primary", "patient_id", "active")
    def _check_single_primary_owner(self):
        for ownership in self.filtered(lambda item: item.is_primary and item.active):
            duplicate = self.search_count(
                [
                    ("patient_id", "=", ownership.patient_id.id),
                    ("is_primary", "=", True),
                    ("active", "=", True),
                    ("id", "!=", ownership.id),
                ]
            )
            if duplicate:
                raise ValidationError("A patient can only have one active primary owner.")

