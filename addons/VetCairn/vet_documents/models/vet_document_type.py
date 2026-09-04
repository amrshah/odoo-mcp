from odoo import fields, models


class VetDocumentType(models.Model):
    _name = "vet.document.type"
    _description = "Veterinary Document Type"
    _order = "category, sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    category = fields.Selection(
        [("consent","Consent Form"),("certificate","Certificate"),("clinical","Clinical Document"),
         ("diagnostic","Diagnostic Result"),("client","Client Document"),("other","Other")],
        default="clinical", required=True, index=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    signature_required = fields.Boolean()
    expiry_required = fields.Boolean()
    default_validity_days = fields.Integer(string="Default Validity (Days)", default=0)
    instructions = fields.Text(translate=True)

    _code_company_unique = models.Constraint("UNIQUE(code, company_id)", "Document type codes must be unique within a company.")
    _validity_nonnegative = models.Constraint("CHECK(default_validity_days >= 0)", "Document validity cannot be negative.")
