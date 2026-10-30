from odoo import fields, models


class VetExamTemplate(models.Model):
    _inherit = "vet.exam.template"

    species_ids = fields.Many2many(
        "vet.species", string="Applies to Species",
        help="Leave empty to offer this template for every species.",
    )
