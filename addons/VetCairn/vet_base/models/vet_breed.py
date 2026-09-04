from odoo import fields, models


class VetBreed(models.Model):
    _name = "vet.breed"
    _description = "Animal Breed"
    _order = "species_id, name"

    name = fields.Char(required=True, translate=True)
    species_id = fields.Many2one(
        "vet.species", required=True, index=True, ondelete="cascade"
    )
    active = fields.Boolean(default=True)

    _name_species_unique = models.Constraint(
        "UNIQUE(name, species_id)",
        "Breed names must be unique within a species.",
    )

