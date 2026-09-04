from odoo import fields, models


class VetSpecies(models.Model):
    _name = "vet.species"
    _description = "Animal Species"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    breed_ids = fields.One2many("vet.breed", "species_id", string="Breeds")

    _name_unique = models.Constraint("UNIQUE(name)", "Species names must be unique.")
    _code_unique = models.Constraint("UNIQUE(code)", "Species codes must be unique.")

