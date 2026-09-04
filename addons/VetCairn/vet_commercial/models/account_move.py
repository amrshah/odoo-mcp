from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    vet_treatment_plan_id = fields.Many2one("vet.treatment.plan", string="Treatment Plan", index=True)
    vet_estimate_id = fields.Many2one("sale.order", string="Veterinary Estimate", index=True, copy=False)
