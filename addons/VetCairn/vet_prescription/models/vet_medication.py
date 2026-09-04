from odoo import fields, models


class VetMedication(models.Model):
    _name = "vet.medication"
    _description = "Veterinary Medication"
    _order = "name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    strength = fields.Char()
    dosage_form = fields.Selection([("tablet","Tablet"),("capsule","Capsule"),("liquid","Liquid"),("injection","Injection"),("topical","Topical"),("other","Other")], default="tablet", required=True)
    controlled = fields.Boolean(string="Controlled Medication")
    default_route = fields.Selection([("oral","Oral"),("topical","Topical"),("subcutaneous","Subcutaneous"),("intramuscular","Intramuscular"),("intravenous","Intravenous"),("other","Other")], default="oral", required=True)
    notes = fields.Text()

    _code_company_unique = models.Constraint("UNIQUE(code, company_id)", "Medication codes must be unique within a company.")
