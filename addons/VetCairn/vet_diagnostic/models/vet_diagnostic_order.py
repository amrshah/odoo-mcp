from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class VetDiagnosticOrder(models.Model):
    _name = "vet.diagnostic.order"
    _description = "Veterinary Diagnostic Order"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "ordered_at desc, id desc"

    name = fields.Char(
        string="Order Number", required=True, readonly=True, copy=False,
        default=lambda self: self.env._("New"), index=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True
    )
    clinic_id = fields.Many2one(
        "vet.clinic", required=True, ondelete="restrict", index=True,
        domain="[('company_id', '=', company_id)]", tracking=True,
    )
    patient_id = fields.Many2one(
        "vet.patient", required=True, ondelete="restrict", index=True,
        domain="[('company_id', '=', company_id), ('status', '=', 'active')]", tracking=True,
    )
    client_id = fields.Many2one(related="patient_id.primary_owner_id", store=True, index=True)
    species_id = fields.Many2one(related="patient_id.species_id", store=True)
    encounter_id = fields.Many2one(
        "vet.encounter", ondelete="set null", domain="[('patient_id', '=', patient_id)]", tracking=True
    )
    requested_by_id = fields.Many2one(
        "res.users", required=True, default=lambda self: self.env.user, index=True, tracking=True
    )
    diagnostic_type_id = fields.Many2one(
        "vet.diagnostic.type", required=True, ondelete="restrict", index=True,
        domain="[('company_id', '=', company_id)]", tracking=True,
    )
    category = fields.Selection(related="diagnostic_type_id.category", store=True, index=True)
    priority = fields.Selection(
        [("routine", "Routine"), ("urgent", "Urgent"), ("stat", "STAT")],
        default="routine", required=True, index=True, tracking=True,
    )
    state = fields.Selection(
        [("draft", "Draft"), ("ordered", "Ordered"), ("collected", "Collected"),
         ("in_progress", "In Progress"), ("completed", "Completed"), ("cancelled", "Cancelled")],
        default="draft", required=True, index=True, tracking=True,
    )
    clinical_question = fields.Text(required=True, tracking=True)
    ordered_at = fields.Datetime(default=fields.Datetime.now, required=True, index=True, tracking=True)
    specimen = fields.Char(tracking=True)
    specimen_identifier = fields.Char(copy=False, index=True, tracking=True)
    collected_at = fields.Datetime(readonly=True, copy=False)
    collected_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    external_reference = fields.Char(copy=False, index=True, tracking=True)
    result_summary = fields.Char(tracking=True)
    result_details = fields.Html(sanitize=True)
    result_file = fields.Binary(attachment=True)
    result_filename = fields.Char()
    resulted_at = fields.Datetime(readonly=True, copy=False)
    resulted_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    abnormal = fields.Boolean(tracking=True)
    cancellation_reason = fields.Text(tracking=True)

    _name_company_unique = models.Constraint(
        "UNIQUE(name, company_id)", "Diagnostic order numbers must be unique within a company."
    )

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", self.env._("New")) == self.env._("New"):
                values["name"] = self.env["ir.sequence"].next_by_code("vet.diagnostic.order") or self.env._("New")
            if values.get("diagnostic_type_id") and not values.get("specimen"):
                values["specimen"] = self.env["vet.diagnostic.type"].browse(values["diagnostic_type_id"]).default_specimen
        return super().create(vals_list)

    @api.onchange("patient_id")
    def _onchange_patient_id(self):
        if self.patient_id:
            self.clinic_id = self.patient_id.clinic_id
            self.company_id = self.patient_id.company_id

    @api.onchange("diagnostic_type_id")
    def _onchange_diagnostic_type_id(self):
        if self.diagnostic_type_id:
            self.specimen = self.diagnostic_type_id.default_specimen

    @api.constrains("patient_id", "clinic_id", "diagnostic_type_id", "company_id")
    def _check_consistency(self):
        for order in self:
            if order.patient_id.company_id != order.company_id or order.clinic_id.company_id != order.company_id:
                raise ValidationError("The diagnostic order, patient, and clinic must belong to the same company.")
            if order.diagnostic_type_id.company_id != order.company_id:
                raise ValidationError("The diagnostic type must belong to the same company.")

    def _transition(self, target, allowed, extra=None):
        if self.filtered(lambda order: order.state not in allowed):
            raise UserError("This diagnostic status change is not allowed.")
        values = {"state": target}
        values.update(extra or {})
        self.write(values)
        return True

    def action_order(self):
        for order in self:
            if order.diagnostic_type_id.specimen_required and not order.specimen:
                raise ValidationError("A specimen is required for this diagnostic order.")
        return self._transition("ordered", ("draft",))

    def action_collect(self):
        return self._transition("collected", ("ordered",), {
            "collected_at": fields.Datetime.now(), "collected_by_id": self.env.user.id,
        })

    def action_start(self):
        return self._transition("in_progress", ("ordered", "collected"))

    def action_complete(self):
        if self.filtered(lambda order: not order.result_summary):
            raise ValidationError("Enter a result summary before completing the order.")
        return self._transition("completed", ("ordered", "collected", "in_progress"), {
            "resulted_at": fields.Datetime.now(), "resulted_by_id": self.env.user.id,
        })

    def action_cancel(self):
        return self._transition("cancelled", ("draft", "ordered", "collected", "in_progress"))

    def action_reset_draft(self):
        return self._transition("draft", ("cancelled",))
