from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


ACTIVE_BOOKING_STATES = ("scheduled", "confirmed", "arrived", "in_progress")


class VetAppointment(models.Model):
    _name = "vet.appointment"
    _description = "Veterinary Appointment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_datetime, id"

    name = fields.Char(
        string="Appointment Number",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env._("New"),
        index=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    clinic_id = fields.Many2one(
        "vet.clinic",
        required=True,
        ondelete="restrict",
        index=True,
        domain="[('company_id', '=', company_id)]",
        tracking=True,
    )
    patient_id = fields.Many2one(
        "vet.patient",
        required=True,
        ondelete="restrict",
        index=True,
        domain="[('company_id', '=', company_id), ('clinic_id', '=', clinic_id), ('status', '=', 'active')]",
        tracking=True,
    )
    client_id = fields.Many2one(
        "res.partner",
        string="Client",
        related="patient_id.primary_owner_id",
        store=True,
        readonly=True,
        index=True,
    )
    client_phone = fields.Char(related="client_id.phone", string="Client Phone")
    patient_species_id = fields.Many2one(
        related="patient_id.species_id", string="Species", store=True
    )
    patient_breed_id = fields.Many2one(related="patient_id.breed_id", string="Breed")
    patient_age = fields.Char(related="patient_id.age_display", string="Age")
    patient_sex = fields.Selection(related="patient_id.sex", string="Sex")
    patient_microchip = fields.Char(
        related="patient_id.microchip_number", string="Microchip"
    )
    provider_id = fields.Many2one(
        "res.users",
        string="Provider",
        required=True,
        ondelete="restrict",
        index=True,
        domain="[('vet_is_provider', '=', True)]",
        tracking=True,
    )
    appointment_type_id = fields.Many2one(
        "vet.appointment.type",
        string="Appointment Type",
        required=True,
        ondelete="restrict",
        domain="[('company_id', '=', company_id)]",
        tracking=True,
    )
    start_datetime = fields.Datetime(
        string="Start", required=True, default=fields.Datetime.now, index=True, tracking=True
    )
    end_datetime = fields.Datetime(string="End", required=True, index=True, tracking=True)
    duration = fields.Float(
        string="Duration (Hours)", compute="_compute_duration", store=True
    )
    state = fields.Selection(
        [
            ("scheduled", "Scheduled"),
            ("confirmed", "Confirmed"),
            ("arrived", "Arrived"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
            ("no_show", "No Show"),
        ],
        default="scheduled",
        required=True,
        index=True,
        tracking=True,
    )
    priority = fields.Selection(
        [("0", "Routine"), ("1", "Urgent"), ("2", "Emergency")],
        default="0",
        required=True,
        index=True,
        tracking=True,
    )
    booking_source = fields.Selection(
        [
            ("phone", "Phone"),
            ("walk_in", "Walk-in"),
            ("online", "Online"),
            ("email", "Email"),
            ("internal", "Internal"),
            ("other", "Other"),
        ],
        default="phone",
        required=True,
        tracking=True,
    )
    room = fields.Char(string="Room / Resource", tracking=True)
    reason = fields.Char(string="Reason / Complaint", required=True, tracking=True)
    notes = fields.Text()
    cancellation_reason = fields.Text(tracking=True)
    arrived_at = fields.Datetime(readonly=True, copy=False)
    started_at = fields.Datetime(readonly=True, copy=False)
    completed_at = fields.Datetime(readonly=True, copy=False)

    _name_company_unique = models.Constraint(
        "UNIQUE(name, company_id)",
        "Appointment numbers must be unique within a company.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", self.env._("New")) == self.env._("New"):
                values["name"] = self.env["ir.sequence"].next_by_code(
                    "vet.appointment"
                ) or self.env._("New")
            values.setdefault("start_datetime", fields.Datetime.now())
            self._set_default_end(values)
        return super().create(vals_list)

    def write(self, values):
        if "start_datetime" in values and "end_datetime" not in values:
            for appointment in self:
                duration = appointment.duration or appointment.appointment_type_id.duration
                values_for_record = dict(values)
                values_for_record["end_datetime"] = fields.Datetime.to_datetime(
                    values["start_datetime"]
                ) + timedelta(hours=duration)
                super(VetAppointment, appointment).write(values_for_record)
            return True
        return super().write(values)

    @api.model
    def _set_default_end(self, values):
        if values.get("end_datetime") or not values.get("start_datetime"):
            return
        duration = 0.5
        if values.get("appointment_type_id"):
            duration = self.env["vet.appointment.type"].browse(
                values["appointment_type_id"]
            ).duration or duration
        values["end_datetime"] = fields.Datetime.to_datetime(
            values["start_datetime"]
        ) + timedelta(hours=duration)

    @api.depends("start_datetime", "end_datetime")
    def _compute_duration(self):
        for appointment in self:
            if appointment.start_datetime and appointment.end_datetime:
                delta = appointment.end_datetime - appointment.start_datetime
                appointment.duration = delta.total_seconds() / 3600
            else:
                appointment.duration = 0

    @api.depends("name", "patient_id", "provider_id", "start_datetime")
    def _compute_display_name(self):
        for appointment in self:
            parts = [appointment.patient_id.name, appointment.reason]
            appointment.display_name = " — ".join(part for part in parts if part) or appointment.name

    @api.onchange("appointment_type_id", "start_datetime")
    def _onchange_schedule(self):
        if self.start_datetime and self.appointment_type_id:
            self.end_datetime = self.start_datetime + timedelta(
                hours=self.appointment_type_id.duration
            )

    @api.onchange("patient_id")
    def _onchange_patient_id(self):
        if self.patient_id:
            self.clinic_id = self.patient_id.clinic_id
            self.company_id = self.patient_id.company_id

    @api.constrains("start_datetime", "end_datetime")
    def _check_dates(self):
        for appointment in self:
            if appointment.start_datetime and appointment.end_datetime <= appointment.start_datetime:
                raise ValidationError("The appointment end must be after its start.")

    @api.constrains("clinic_id", "patient_id", "appointment_type_id", "company_id")
    def _check_company_consistency(self):
        for appointment in self:
            if appointment.clinic_id.company_id != appointment.company_id:
                raise ValidationError("The clinic and appointment must belong to the same company.")
            if appointment.patient_id.company_id != appointment.company_id:
                raise ValidationError("The patient and appointment must belong to the same company.")
            if appointment.patient_id.clinic_id != appointment.clinic_id:
                raise ValidationError("The patient must belong to the selected clinic.")
            if appointment.appointment_type_id.company_id != appointment.company_id:
                raise ValidationError("The appointment type must belong to the same company.")

    @api.constrains("provider_id", "patient_id", "start_datetime", "end_datetime", "state")
    def _check_schedule_conflicts(self):
        for appointment in self.filtered(lambda item: item.state in ACTIVE_BOOKING_STATES):
            overlap_domain = [
                ("id", "!=", appointment.id),
                ("company_id", "=", appointment.company_id.id),
                ("state", "in", ACTIVE_BOOKING_STATES),
                ("start_datetime", "<", appointment.end_datetime),
                ("end_datetime", ">", appointment.start_datetime),
            ]
            if self.search_count(overlap_domain + [("provider_id", "=", appointment.provider_id.id)]):
                raise ValidationError("The provider already has an overlapping appointment.")
            if self.search_count(overlap_domain + [("patient_id", "=", appointment.patient_id.id)]):
                raise ValidationError("The patient already has an overlapping appointment.")

    def _move_to(self, target_state, allowed_states, timestamp_field=None):
        invalid = self.filtered(lambda appointment: appointment.state not in allowed_states)
        if invalid:
            raise UserError("This status change is not allowed from the current appointment status.")
        values = {"state": target_state}
        if timestamp_field:
            values[timestamp_field] = fields.Datetime.now()
        self.write(values)
        return True

    def action_confirm(self):
        return self._move_to("confirmed", ("scheduled",))

    def action_arrive(self):
        return self._move_to("arrived", ("scheduled", "confirmed"), "arrived_at")

    def action_start(self):
        return self._move_to("in_progress", ("arrived",), "started_at")

    def action_complete(self):
        return self._move_to("completed", ("in_progress",), "completed_at")

    def action_cancel(self):
        return self._move_to("cancelled", ACTIVE_BOOKING_STATES)

    def action_no_show(self):
        return self._move_to("no_show", ("scheduled", "confirmed"))

    def action_reset_scheduled(self):
        return self._move_to("scheduled", ("cancelled", "no_show"))

    def action_open_patient(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.patient_id.display_name,
            "res_model": "vet.patient",
            "res_id": self.patient_id.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_client(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.client_id.display_name,
            "res_model": "res.partner",
            "res_id": self.client_id.id,
            "view_mode": "form",
            "target": "current",
        }
