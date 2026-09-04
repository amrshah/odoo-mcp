from odoo import fields, models


class VetDiagnosis(models.Model):
    _name = "vet.diagnosis"
    _description = "Veterinary Diagnosis"
    _order = "name"

    name = fields.Char(required=True, translate=True, index=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    category = fields.Selection([("infectious","Infectious"),("injury","Injury / Trauma"),("chronic","Chronic"),("congenital","Congenital"),("neoplastic","Neoplastic"),("preventive","Preventive"),("other","Other")], default="other", required=True)
    species_ids = fields.Many2many("vet.species", string="Applicable Species")
    description = fields.Text(translate=True)

    _code_company_unique = models.Constraint("UNIQUE(code, company_id)", "Diagnosis codes must be unique within a company.")
