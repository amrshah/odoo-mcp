from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    vet_is_provider = fields.Boolean(string="Veterinary Provider")
    vet_provider_code = fields.Char(string="Provider Code", copy=False)
    vet_clinic_ids = fields.Many2many(
        "vet.clinic",
        "vet_clinic_user_rel",
        "user_id",
        "clinic_id",
        string="Vet Clinics",
    )

