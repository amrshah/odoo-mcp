from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    is_vet_client = fields.Boolean(string="Veterinary Client", index=True)
    vet_client_status = fields.Selection(
        [("active", "Active"), ("inactive", "Inactive")],
        default="active",
        string="Vet Client Status",
        tracking=True,
    )
    vet_preferred_clinic_id = fields.Many2one(
        "vet.clinic",
        string="Preferred Clinic",
        domain="[('company_id', 'in', [company_id, False])]",
    )
    vet_transactional_email = fields.Boolean(string="Transactional Email", default=True)
    vet_transactional_sms = fields.Boolean(string="Transactional SMS", default=False)
    vet_marketing_email = fields.Boolean(string="Marketing Email", default=False)
    vet_marketing_sms = fields.Boolean(string="Marketing SMS", default=False)
    vet_ownership_ids = fields.One2many(
        "vet.patient.owner", "partner_id", string="Patient Relationships"
    )
    vet_patient_count = fields.Integer(compute="_compute_vet_patient_count")

    @api.depends("vet_ownership_ids.active")
    def _compute_vet_patient_count(self):
        for partner in self:
            partner.vet_patient_count = len(
                partner.vet_ownership_ids.filtered("active").patient_id
            )

    def action_view_vet_patients(self):
        self.ensure_one()
        patient_ids = self.vet_ownership_ids.filtered("active").patient_id.ids
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Patients"),
            "res_model": "vet.patient",
            "view_mode": "list,form",
            "domain": [("id", "in", patient_ids)],
        }
