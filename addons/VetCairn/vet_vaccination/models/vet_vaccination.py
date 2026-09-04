from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class VetVaccination(models.Model):
    _name = "vet.vaccination"
    _description = "Veterinary Vaccination"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "planned_date desc, id desc"

    name = fields.Char(
        string="Vaccination Number",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env._("New"),
        index=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    clinic_id = fields.Many2one(
        "vet.clinic",
        required=True,
        ondelete="restrict",
        domain="[('company_id', '=', company_id)]",
        index=True,
        tracking=True,
    )
    patient_id = fields.Many2one(
        "vet.patient",
        required=True,
        ondelete="restrict",
        domain="[('company_id', '=', company_id), ('status', '=', 'active')]",
        index=True,
        tracking=True,
    )
    client_id = fields.Many2one(
        related="patient_id.primary_owner_id", string="Client", store=True, index=True
    )
    species_id = fields.Many2one(related="patient_id.species_id", store=True)
    protocol_id = fields.Many2one(
        "vet.vaccine.protocol",
        required=True,
        ondelete="restrict",
        domain="[('company_id', '=', company_id), ('species_id', '=', species_id)]",
        index=True,
        tracking=True,
    )
    appointment_id = fields.Many2one(
        "vet.appointment",
        ondelete="set null",
        domain="[('patient_id', '=', patient_id)]",
        tracking=True,
    )
    encounter_id = fields.Many2one(
        "vet.encounter",
        ondelete="set null",
        domain="[('patient_id', '=', patient_id)]",
        tracking=True,
    )
    state = fields.Selection(
        [("planned", "Planned"), ("administered", "Administered"), ("cancelled", "Cancelled")],
        default="planned",
        required=True,
        index=True,
        tracking=True,
    )
    planned_date = fields.Date(
        required=True, default=fields.Date.context_today, index=True, tracking=True
    )
    administered_date = fields.Date(readonly=True, copy=False, tracking=True)
    administered_by_id = fields.Many2one(
        "res.users", string="Administered By", readonly=True, copy=False, tracking=True
    )
    next_due_date = fields.Date(readonly=True, copy=False, index=True, tracking=True)
    is_overdue = fields.Boolean(compute="_compute_is_overdue", search="_search_is_overdue")
    manufacturer = fields.Char(tracking=True)
    product_name = fields.Char(string="Vaccine Product", tracking=True)
    batch_number = fields.Char(string="Batch / Lot Number", tracking=True)
    expiry_date = fields.Date(tracking=True)
    route = fields.Selection(
        [
            ("subcutaneous", "Subcutaneous"),
            ("intramuscular", "Intramuscular"),
            ("intranasal", "Intranasal"),
            ("oral", "Oral"),
            ("other", "Other"),
        ],
        tracking=True,
    )
    administration_site = fields.Char(string="Administration Site", tracking=True)
    dose = fields.Float(default=1.0, tracking=True)
    dose_unit = fields.Char(default="ml", tracking=True)
    certificate_number = fields.Char(copy=False, index=True, tracking=True)
    adverse_reaction = fields.Text(tracking=True)
    notes = fields.Text()
    cancellation_reason = fields.Text(tracking=True)

    _name_company_unique = models.Constraint(
        "UNIQUE(name, company_id)",
        "Vaccination numbers must be unique within a company.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", self.env._("New")) == self.env._("New"):
                values["name"] = self.env["ir.sequence"].next_by_code(
                    "vet.vaccination"
                ) or self.env._("New")
            self._apply_protocol_defaults(values)
        return super().create(vals_list)

    @api.model
    def _apply_protocol_defaults(self, values):
        if not values.get("protocol_id"):
            return
        protocol = self.env["vet.vaccine.protocol"].browse(values["protocol_id"])
        values.setdefault("route", protocol.default_route)
        values.setdefault("dose", protocol.default_dose)
        values.setdefault("dose_unit", protocol.dose_unit)

    @api.depends("planned_date", "state")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for vaccination in self:
            vaccination.is_overdue = (
                vaccination.state == "planned"
                and vaccination.planned_date
                and vaccination.planned_date < today
            )

    def _search_is_overdue(self, operator, value):
        overdue_domain = [
            ("state", "=", "planned"),
            ("planned_date", "<", fields.Date.context_today(self)),
        ]
        if (operator in ("=", "==") and value) or (operator == "!=" and not value):
            return overdue_domain
        return ["!"] + overdue_domain

    @api.onchange("patient_id")
    def _onchange_patient_id(self):
        if self.patient_id:
            self.clinic_id = self.patient_id.clinic_id
            self.company_id = self.patient_id.company_id
            if self.protocol_id.species_id != self.patient_id.species_id:
                self.protocol_id = False

    @api.onchange("protocol_id")
    def _onchange_protocol_id(self):
        if self.protocol_id:
            self.route = self.protocol_id.default_route
            self.dose = self.protocol_id.default_dose
            self.dose_unit = self.protocol_id.dose_unit

    @api.constrains("clinic_id", "patient_id", "protocol_id", "company_id")
    def _check_consistency(self):
        for vaccination in self:
            if vaccination.clinic_id.company_id != vaccination.company_id:
                raise ValidationError("The clinic and vaccination must belong to the same company.")
            if vaccination.patient_id.company_id != vaccination.company_id:
                raise ValidationError("The patient and vaccination must belong to the same company.")
            if vaccination.protocol_id.company_id != vaccination.company_id:
                raise ValidationError("The protocol and vaccination must belong to the same company.")
            if vaccination.protocol_id.species_id != vaccination.patient_id.species_id:
                raise ValidationError("The vaccine protocol does not apply to this patient's species.")

    @api.constrains("expiry_date", "administered_date", "dose")
    def _check_administration_values(self):
        for vaccination in self:
            if vaccination.dose < 0:
                raise ValidationError("The vaccine dose cannot be negative.")
            if (
                vaccination.expiry_date
                and vaccination.administered_date
                and vaccination.expiry_date < vaccination.administered_date
            ):
                raise ValidationError("An expired vaccine cannot be recorded as administered.")

    def action_administer(self):
        invalid = self.filtered(lambda vaccination: vaccination.state != "planned")
        if invalid:
            raise UserError("Only a planned vaccination can be administered.")
        today = fields.Date.context_today(self)
        for vaccination in self:
            next_due = False
            if vaccination.protocol_id.booster_interval_months:
                next_due = today + relativedelta(
                    months=vaccination.protocol_id.booster_interval_months
                )
            vaccination.write(
                {
                    "state": "administered",
                    "administered_date": today,
                    "administered_by_id": self.env.user.id,
                    "next_due_date": next_due,
                }
            )
        return True

    def action_cancel(self):
        invalid = self.filtered(lambda vaccination: vaccination.state != "planned")
        if invalid:
            raise UserError("Only a planned vaccination can be cancelled.")
        self.write({"state": "cancelled"})
        return True

    def action_reset_planned(self):
        invalid = self.filtered(lambda vaccination: vaccination.state != "cancelled")
        if invalid:
            raise UserError("Only a cancelled vaccination can be reset.")
        self.write({"state": "planned", "cancellation_reason": False})
        return True
