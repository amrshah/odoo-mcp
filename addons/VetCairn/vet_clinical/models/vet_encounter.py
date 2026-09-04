from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class VetEncounter(models.Model):
    _name = "vet.encounter"
    _description = "Veterinary Clinical Encounter"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_datetime desc, id desc"

    name = fields.Char(
        string="Encounter Number",
        required=True,
        readonly=True,
        copy=False,
        default=lambda self: self.env._("New"),
        index=True,
    )
    active = fields.Boolean(default=True)
    appointment_id = fields.Many2one(
        "vet.appointment", required=True, ondelete="restrict", index=True, tracking=True
    )
    company_id = fields.Many2one(
        related="appointment_id.company_id", store=True, index=True
    )
    clinic_id = fields.Many2one(
        related="appointment_id.clinic_id", store=True, index=True
    )
    patient_id = fields.Many2one(
        related="appointment_id.patient_id", store=True, index=True
    )
    client_id = fields.Many2one(
        related="appointment_id.client_id", store=True, index=True
    )
    provider_id = fields.Many2one(
        related="appointment_id.provider_id", store=True, index=True
    )
    start_datetime = fields.Datetime(
        related="appointment_id.start_datetime", store=True, index=True
    )
    state = fields.Selection(
        [
            ("draft", "Waiting / Triage"),
            ("in_progress", "In Consultation"),
            ("completed", "Completed"),
            ("locked", "Locked"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )
    triage_priority = fields.Selection(
        [("routine", "Routine"), ("urgent", "Urgent"), ("emergency", "Emergency")],
        default="routine",
        required=True,
        tracking=True,
    )
    weight_kg = fields.Float(string="Weight (kg)", tracking=True)
    temperature_c = fields.Float(string="Temperature (°C)", tracking=True)
    heart_rate = fields.Integer(string="Heart Rate (bpm)", tracking=True)
    respiratory_rate = fields.Integer(string="Respiratory Rate (/min)", tracking=True)
    pain_score = fields.Selection([(str(score), str(score)) for score in range(11)], tracking=True)
    chief_complaint = fields.Text(required=True, tracking=True)
    subjective = fields.Html(string="Subjective / History", sanitize=True)
    objective = fields.Html(string="Objective / Examination", sanitize=True)
    assessment = fields.Html(string="Assessment", sanitize=True)
    plan = fields.Html(string="Plan", sanitize=True)
    diagnosis_summary = fields.Char(string="Diagnosis Summary", tracking=True)
    completed_at = fields.Datetime(readonly=True, copy=False)
    locked_at = fields.Datetime(readonly=True, copy=False)
    locked_by_id = fields.Many2one("res.users", readonly=True, copy=False)

    _appointment_unique = models.Constraint(
        "UNIQUE(appointment_id)", "An appointment can only have one clinical encounter."
    )

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", self.env._("New")) == self.env._("New"):
                values["name"] = self.env["ir.sequence"].next_by_code(
                    "vet.encounter"
                ) or self.env._("New")
            if not values.get("chief_complaint") and values.get("appointment_id"):
                values["chief_complaint"] = self.env["vet.appointment"].browse(
                    values["appointment_id"]
                ).reason
        return super().create(vals_list)

    def write(self, values):
        if any(encounter.state == "locked" for encounter in self):
            allowed = {"message_follower_ids", "message_partner_ids", "activity_ids"}
            if set(values) - allowed:
                raise UserError("A locked clinical encounter cannot be edited.")
        return super().write(values)

    @api.constrains("weight_kg", "temperature_c", "heart_rate", "respiratory_rate")
    def _check_vitals(self):
        for encounter in self:
            if encounter.weight_kg < 0:
                raise ValidationError("Weight cannot be negative.")
            if encounter.temperature_c and not 20 <= encounter.temperature_c <= 50:
                raise ValidationError("Temperature must be between 20°C and 50°C.")
            if encounter.heart_rate < 0 or encounter.respiratory_rate < 0:
                raise ValidationError("Heart and respiratory rates cannot be negative.")

    def action_start(self):
        invalid = self.filtered(lambda encounter: encounter.state != "draft")
        if invalid:
            raise UserError("Only a waiting encounter can be started.")
        self.write({"state": "in_progress"})
        return True

    def action_complete(self):
        invalid = self.filtered(lambda encounter: encounter.state not in ("draft", "in_progress"))
        if invalid:
            raise UserError("Only an open encounter can be completed.")
        self.write({"state": "completed", "completed_at": fields.Datetime.now()})
        return True

    def action_reopen(self):
        invalid = self.filtered(lambda encounter: encounter.state != "completed")
        if invalid:
            raise UserError("Only a completed encounter can be reopened.")
        self.write({"state": "in_progress", "completed_at": False})
        return True

    def action_lock(self):
        invalid = self.filtered(lambda encounter: encounter.state != "completed")
        if invalid:
            raise UserError("Complete the encounter before locking it.")
        self.write(
            {
                "state": "locked",
                "locked_at": fields.Datetime.now(),
                "locked_by_id": self.env.user.id,
            }
        )
        return True
