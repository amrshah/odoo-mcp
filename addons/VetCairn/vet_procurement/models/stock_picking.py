from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    is_vet_receipt = fields.Boolean(string="Veterinary Receipt", default=False, index=True)
    vet_clinic_id = fields.Many2one("vet.clinic", string="Clinic", index=True, tracking=True)
