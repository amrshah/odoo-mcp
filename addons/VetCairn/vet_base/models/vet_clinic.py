from odoo import api, fields, models
from odoo.addons.base.models.res_partner import _tz_get
from odoo.exceptions import ValidationError


class VetClinic(models.Model):
    _name = "vet.clinic"
    _description = "Veterinary Clinic"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, index=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Contact Address",
        domain="[('is_company', '=', True)]",
        tracking=True,
    )
    timezone = fields.Selection(
        selection=_tz_get,
        default=lambda self: self.env.user.tz or "UTC",
        required=True,
    )
    notes = fields.Text()
    patient_count = fields.Integer(compute="_compute_patient_count")

    _code_company_unique = models.Constraint(
        "UNIQUE(code, company_id)",
        "Clinic codes must be unique within a company.",
    )

    @api.depends("company_id")
    def _compute_patient_count(self):
        counts = self.env["vet.patient"]._read_group(
            [("clinic_id", "in", self.ids)], ["clinic_id"], ["__count"]
        )
        count_by_clinic = {clinic.id: count for clinic, count in counts}
        for clinic in self:
            clinic.patient_count = count_by_clinic.get(clinic.id, 0)

    @api.constrains("partner_id", "company_id")
    def _check_partner_company(self):
        for clinic in self:
            if (
                clinic.partner_id.company_id
                and clinic.partner_id.company_id != clinic.company_id
            ):
                raise ValidationError(
                    "The clinic contact must belong to the same company as the clinic."
                )
