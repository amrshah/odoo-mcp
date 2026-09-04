from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class VetTreatmentPlan(models.Model):
    _name = "vet.treatment.plan"
    _description = "Veterinary Treatment Plan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "admitted_at desc, id desc"

    name = fields.Char(string="Plan Number", required=True, readonly=True, copy=False, default=lambda self: self.env._("New"), index=True)
    title = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    clinic_id = fields.Many2one("vet.clinic", required=True, ondelete="restrict", domain="[('company_id','=',company_id)]", index=True, tracking=True)
    patient_id = fields.Many2one("vet.patient", required=True, ondelete="restrict", domain="[('company_id','=',company_id),('status','=','active')]", index=True, tracking=True)
    client_id = fields.Many2one(related="patient_id.primary_owner_id", store=True, index=True)
    appointment_id = fields.Many2one("vet.appointment", ondelete="set null", domain="[('patient_id','=',patient_id)]")
    encounter_id = fields.Many2one("vet.encounter", ondelete="set null", domain="[('patient_id','=',patient_id)]", tracking=True)
    provider_id = fields.Many2one("res.users", required=True, default=lambda self:self.env.user, domain="[('vet_is_provider','=',True)]", tracking=True)
    diagnosis_ids = fields.Many2many("vet.diagnosis", string="Diagnoses", domain="[('company_id','=',company_id)]", tracking=True)
    care_setting = fields.Selection([("outpatient","Outpatient"),("day_patient","Day Patient"),("inpatient","Inpatient / Hospitalized")], default="outpatient", required=True, tracking=True)
    room = fields.Char(string="Ward / Room", tracking=True)
    state = fields.Selection([("draft","Draft"),("active","Active"),("completed","Completed"),("cancelled","Cancelled")], default="draft", required=True, index=True, tracking=True)
    priority = fields.Selection([("routine","Routine"),("urgent","Urgent"),("critical","Critical")], default="routine", required=True, index=True, tracking=True)
    admitted_at = fields.Datetime(default=fields.Datetime.now, required=True, tracking=True)
    expected_discharge_at = fields.Datetime(tracking=True)
    discharged_at = fields.Datetime(readonly=True, copy=False)
    goals = fields.Html(sanitize=True)
    clinical_summary = fields.Html(sanitize=True)
    discharge_instructions = fields.Html(sanitize=True)
    line_ids = fields.One2many("vet.treatment.line", "plan_id", string="Treatment Activities")
    activity_count = fields.Integer(compute="_compute_activity_stats")
    overdue_count = fields.Integer(compute="_compute_activity_stats")

    _name_company_unique = models.Constraint("UNIQUE(name, company_id)", "Treatment plan numbers must be unique within a company.")

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", self.env._("New")) == self.env._("New"):
                values["name"] = self.env["ir.sequence"].next_by_code("vet.treatment.plan") or self.env._("New")
        return super().create(vals_list)

    @api.depends("line_ids.state", "line_ids.is_overdue")
    def _compute_activity_stats(self):
        for plan in self:
            plan.activity_count=len(plan.line_ids)
            plan.overdue_count=len(plan.line_ids.filtered("is_overdue"))

    @api.onchange("patient_id")
    def _onchange_patient_id(self):
        if self.patient_id: self.clinic_id=self.patient_id.clinic_id; self.company_id=self.patient_id.company_id

    @api.constrains("admitted_at", "expected_discharge_at")
    def _check_dates(self):
        for plan in self:
            if plan.expected_discharge_at and plan.expected_discharge_at < plan.admitted_at: raise ValidationError("Expected discharge cannot precede admission.")

    def action_start(self):
        if self.filtered(lambda p:p.state!="draft"): raise UserError("Only draft treatment plans can be started.")
        if self.filtered(lambda p:not p.line_ids): raise ValidationError("Add at least one treatment activity before starting the plan.")
        self.write({"state":"active"}); return True
    def action_complete(self):
        if self.filtered(lambda p:p.state!="active"): raise UserError("Only active treatment plans can be completed.")
        if self.filtered(lambda p:p.line_ids.filtered(lambda l:l.state not in ("completed","skipped"))): raise ValidationError("Complete or skip every treatment activity before completing the plan.")
        self.write({"state":"completed","discharged_at":fields.Datetime.now()}); return True
    def action_cancel(self):
        if self.filtered(lambda p:p.state not in ("draft","active")): raise UserError("This treatment plan cannot be cancelled.")
        self.write({"state":"cancelled"}); return True
