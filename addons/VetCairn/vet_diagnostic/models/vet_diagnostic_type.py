from odoo import fields, models


class VetDiagnosticType(models.Model):
    _name = "vet.diagnostic.type"
    _description = "Veterinary Diagnostic Type"
    _order = "category, sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    category = fields.Selection(
        [("laboratory", "Laboratory"), ("imaging", "Imaging"), ("other", "Other")],
        required=True,
        default="laboratory",
        index=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    specimen_required = fields.Boolean(default=False)
    default_specimen = fields.Char()
    instructions = fields.Text(translate=True)

    _code_company_unique = models.Constraint(
        "UNIQUE(code, company_id)",
        "Diagnostic type codes must be unique within a company.",
    )
