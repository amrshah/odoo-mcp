from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class VetPatient(models.Model):
    _name = "vet.patient"
    _description = "Veterinary Patient"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name, identifier"

    name = fields.Char(required=True, index="trigram", tracking=True)
    identifier = fields.Char(
        string="Patient ID",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env._("New"),
        index=True,
        tracking=True,
    )
    active = fields.Boolean(default=True)
    status = fields.Selection(
        [
            ("active", "Active"),
            ("inactive", "Inactive"),
            ("deceased", "Deceased"),
        ],
        default="active",
        required=True,
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    clinic_id = fields.Many2one(
        "vet.clinic",
        required=True,
        index=True,
        ondelete="restrict",
        domain="[('company_id', '=', company_id)]",
        tracking=True,
    )
    species_id = fields.Many2one(
        "vet.species", required=True, index=True, ondelete="restrict", tracking=True
    )
    breed_id = fields.Many2one(
        "vet.breed",
        index=True,
        ondelete="restrict",
        domain="[('species_id', '=', species_id)]",
        tracking=True,
    )
    birthdate = fields.Date(tracking=True)
    approximate_birthdate = fields.Boolean()
    age_display = fields.Char(string="Age", compute="_compute_age_display")
    sex = fields.Selection(
        [("female", "Female"), ("male", "Male"), ("unknown", "Unknown")],
        default="unknown",
        required=True,
        tracking=True,
    )
    reproductive_status = fields.Selection(
        [
            ("intact", "Intact"),
            ("spayed", "Spayed"),
            ("neutered", "Neutered"),
            ("unknown", "Unknown"),
        ],
        default="unknown",
        required=True,
        tracking=True,
    )
    color = fields.Char()
    microchip_number = fields.Char(copy=False, index=True, tracking=True)
    deceased_date = fields.Date(tracking=True)
    notes = fields.Text()
    ownership_ids = fields.One2many(
        "vet.patient.owner", "patient_id", string="Owners"
    )
    primary_owner_id = fields.Many2one(
        "res.partner", compute="_compute_primary_owner", store=True, index=True
    )

    _identifier_company_unique = models.Constraint(
        "UNIQUE(identifier, company_id)",
        "Patient IDs must be unique within a company.",
    )
    _microchip_unique = models.Constraint(
        "UNIQUE(microchip_number)",
        "Microchip numbers must be unique.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("identifier", self.env._("New")) == self.env._("New"):
                values["identifier"] = self.env["ir.sequence"].next_by_code(
                    "vet.patient"
                ) or self.env._("New")
        return super().create(vals_list)

    @api.depends("ownership_ids.is_primary", "ownership_ids.active", "ownership_ids.partner_id")
    def _compute_primary_owner(self):
        for patient in self:
            primary = patient.ownership_ids.filtered(
                lambda ownership: ownership.is_primary and ownership.active
            )[:1]
            patient.primary_owner_id = primary.partner_id

    @api.depends("birthdate")
    def _compute_age_display(self):
        today = fields.Date.context_today(self)
        for patient in self:
            if not patient.birthdate or patient.birthdate > today:
                patient.age_display = False
                continue
            age = relativedelta(today, patient.birthdate)
            patient.age_display = self.env._("%(years)s y %(months)s m", years=age.years, months=age.months)

    @api.onchange("species_id")
    def _onchange_species_id(self):
        if self.breed_id.species_id != self.species_id:
            self.breed_id = False

    @api.onchange("status")
    def _onchange_status(self):
        if self.status != "deceased":
            self.deceased_date = False

    @api.constrains("birthdate", "deceased_date", "status")
    def _check_lifecycle_dates(self):
        today = fields.Date.context_today(self)
        for patient in self:
            if patient.birthdate and patient.birthdate > today:
                raise ValidationError("A patient's birthdate cannot be in the future.")
            if patient.deceased_date and patient.birthdate and patient.deceased_date < patient.birthdate:
                raise ValidationError("The deceased date cannot precede the birthdate.")
            if patient.status == "deceased" and not patient.deceased_date:
                raise ValidationError("A deceased patient must have a deceased date.")

    @api.constrains("breed_id", "species_id")
    def _check_breed_species(self):
        for patient in self:
            if patient.breed_id and patient.breed_id.species_id != patient.species_id:
                raise ValidationError("The selected breed does not belong to this species.")

    @api.constrains("clinic_id", "company_id")
    def _check_clinic_company(self):
        for patient in self:
            if patient.clinic_id.company_id != patient.company_id:
                raise ValidationError("The patient and clinic must belong to the same company.")

