from odoo import fields, models


class VetVaccineProtocol(models.Model):
    _name = "vet.vaccine.protocol"
    _description = "Veterinary Vaccine Protocol"
    _order = "species_id, sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    species_id = fields.Many2one(
        "vet.species", required=True, ondelete="restrict", index=True
    )
    minimum_age_months = fields.Integer(string="Minimum Age (Months)", default=0)
    booster_interval_months = fields.Integer(
        string="Booster Interval (Months)", default=12, required=True
    )
    default_route = fields.Selection(
        [
            ("subcutaneous", "Subcutaneous"),
            ("intramuscular", "Intramuscular"),
            ("intranasal", "Intranasal"),
            ("oral", "Oral"),
            ("other", "Other"),
        ],
        default="subcutaneous",
        required=True,
    )
    default_dose = fields.Float(string="Default Dose", default=1.0)
    dose_unit = fields.Char(default="ml")
    description = fields.Text(translate=True)

    _code_company_unique = models.Constraint(
        "UNIQUE(code, company_id)",
        "Vaccine protocol codes must be unique within a company.",
    )
    _interval_nonnegative = models.Constraint(
        "CHECK(booster_interval_months >= 0 AND minimum_age_months >= 0)",
        "Vaccine ages and intervals cannot be negative.",
    )
