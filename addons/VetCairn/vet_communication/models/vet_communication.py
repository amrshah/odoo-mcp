from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


CHANNELS = [("phone", "Phone Call"), ("email", "Email"), ("sms", "SMS"), ("postal", "Postal Mail"), ("in_person", "In Person"), ("internal", "Internal Note"), ("other", "Other")]


class VetCommunicationTemplate(models.Model):
    _name = "vet.communication.template"
    _description = "Veterinary Communication Template"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    channel = fields.Selection(CHANNELS, required=True, default="email")
    subject = fields.Char(required=True, translate=True)
    body = fields.Html(required=True, sanitize=True, translate=True)
    direction = fields.Selection([("outbound", "Outbound"), ("internal", "Internal")], default="outbound", required=True)
    category = fields.Selection([("clinical", "Clinical"), ("appointment", "Appointment"), ("billing", "Billing"), ("reminder", "Reminder"), ("general", "General")], default="general", required=True)


class VetCommunication(models.Model):
    _name = "vet.communication"
    _description = "Veterinary Client Communication"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "communication_datetime desc, id desc"

    name = fields.Char(string="Reference", required=True, readonly=True, copy=False, default=lambda self: self.env._("New"), index=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    clinic_id = fields.Many2one("vet.clinic", required=True, ondelete="restrict", domain="[('company_id', '=', company_id)]", tracking=True, index=True)
    client_id = fields.Many2one("res.partner", required=True, ondelete="restrict", domain="[('is_vet_client', '=', True)]", tracking=True, index=True)
    patient_id = fields.Many2one("vet.patient", ondelete="set null", domain="[('company_id', '=', company_id)]", tracking=True, index=True)
    appointment_id = fields.Many2one("vet.appointment", ondelete="set null", domain="[('patient_id', '=', patient_id)]")
    encounter_id = fields.Many2one("vet.encounter", ondelete="set null", domain="[('patient_id', '=', patient_id)]")
    template_id = fields.Many2one("vet.communication.template", domain="[('company_id', '=', company_id), ('channel', '=', channel)]", ondelete="set null")
    direction = fields.Selection([("inbound", "Inbound"), ("outbound", "Outbound"), ("internal", "Internal")], default="outbound", required=True, tracking=True, index=True)
    channel = fields.Selection(CHANNELS, required=True, default="phone", tracking=True, index=True)
    category = fields.Selection([("clinical", "Clinical"), ("appointment", "Appointment"), ("billing", "Billing"), ("reminder", "Reminder"), ("general", "General")], default="general", required=True, tracking=True)
    state = fields.Selection([("draft", "Draft"), ("planned", "Planned"), ("completed", "Completed / Recorded"), ("failed", "Failed"), ("cancelled", "Cancelled")], default="draft", required=True, tracking=True, index=True)
    subject = fields.Char(required=True, tracking=True)
    body = fields.Html(required=True, sanitize=True)
    communication_datetime = fields.Datetime(string="Date & Time", default=fields.Datetime.now, required=True, tracking=True, index=True)
    responsible_user_id = fields.Many2one("res.users", string="Communication Owner", default=lambda self: self.env.user, required=True, ondelete="restrict", tracking=True)
    completed_at = fields.Datetime(readonly=True, copy=False)
    completed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    external_reference = fields.Char(copy=False, help="Optional provider or delivery reference. No provider is connected by this module.")
    failure_reason = fields.Text(tracking=True)
    follow_up_required = fields.Boolean(tracking=True)
    follow_up_datetime = fields.Datetime(tracking=True)
    follow_up_user_id = fields.Many2one("res.users", string="Follow-up Assigned To", ondelete="restrict")
    follow_up_task_id = fields.Many2one("vet.task", readonly=True, copy=False)
    attachment_ids = fields.Many2many("ir.attachment", "vet_communication_attachment_rel", "communication_id", "attachment_id", string="Attachments", copy=False)
    client_email = fields.Char(related="client_id.email", readonly=True)
    client_phone = fields.Char(related="client_id.phone", readonly=True)
    email_allowed = fields.Boolean(related="client_id.vet_transactional_email", readonly=True)
    sms_allowed = fields.Boolean(related="client_id.vet_transactional_sms", readonly=True)

    _name_company_unique = models.Constraint("UNIQUE(name, company_id)", "Communication references must be unique within a company.")

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", self.env._("New")) == self.env._("New"):
                values["name"] = self.env["ir.sequence"].next_by_code("vet.communication") or self.env._("New")
        return super().create(vals_list)

    @api.onchange("patient_id")
    def _onchange_patient_id(self):
        if self.patient_id:
            self.client_id = self.patient_id.primary_owner_id
            self.clinic_id = self.patient_id.clinic_id
            self.company_id = self.patient_id.company_id

    @api.onchange("client_id")
    def _onchange_client_id(self):
        if self.client_id and self.client_id.vet_preferred_clinic_id:
            self.clinic_id = self.client_id.vet_preferred_clinic_id

    @api.onchange("template_id")
    def _onchange_template_id(self):
        if self.template_id:
            self.subject = self.template_id.subject
            self.body = self.template_id.body
            self.channel = self.template_id.channel
            self.direction = self.template_id.direction
            self.category = self.template_id.category

    @api.constrains("patient_id", "client_id")
    def _check_patient_owner(self):
        for communication in self.filtered("patient_id"):
            owners = communication.patient_id.ownership_ids.filtered("active").partner_id
            if communication.client_id not in owners:
                raise ValidationError("The selected client must have an active relationship with this patient.")

    @api.constrains("follow_up_required", "follow_up_datetime", "follow_up_user_id")
    def _check_follow_up(self):
        for communication in self:
            if communication.follow_up_required and (not communication.follow_up_datetime or not communication.follow_up_user_id):
                raise ValidationError("Follow-up date and assigned user are required when follow-up is enabled.")

    def _check_channel_details(self):
        for communication in self.filtered(lambda item: item.direction == "outbound"):
            if communication.channel == "email" and not communication.client_email:
                raise ValidationError("The client needs an email address for email communication.")
            if communication.channel in ("phone", "sms") and not communication.client_phone:
                raise ValidationError("The client needs a phone number for phone or SMS communication.")
            if communication.channel == "email" and not communication.email_allowed:
                raise ValidationError("This client has not allowed transactional email.")
            if communication.channel == "sms" and not communication.sms_allowed:
                raise ValidationError("This client has not allowed transactional SMS.")

    def action_plan(self):
        if self.filtered(lambda item: item.state != "draft"):
            raise UserError("Only draft communications can be planned.")
        self._check_channel_details()
        self.write({"state": "planned"})
        return True

    def action_complete(self):
        if self.filtered(lambda item: item.state not in ("draft", "planned", "failed")):
            raise UserError("Only draft, planned, or failed communications can be completed.")
        self._check_channel_details()
        self.write({"state": "completed", "completed_at": fields.Datetime.now(), "completed_by_id": self.env.user.id, "failure_reason": False})
        self._create_follow_up_tasks()
        return True

    def action_fail(self):
        if self.filtered(lambda item: item.state != "planned"):
            raise UserError("Only planned communications can be marked failed.")
        if self.filtered(lambda item: not item.failure_reason):
            raise ValidationError("Enter the failure reason first.")
        self.write({"state": "failed"})
        return True

    def action_cancel(self):
        if self.filtered(lambda item: item.state in ("completed", "cancelled")):
            raise UserError("Completed or cancelled communications cannot be cancelled.")
        self.write({"state": "cancelled"})
        return True

    def _create_follow_up_tasks(self):
        task_type = self.env.ref("vet_task.task_type_client_call")
        for item in self.filtered(lambda record: record.follow_up_required and not record.follow_up_task_id):
            task = self.env["vet.task"].create({"title": self.env._("Follow up: %s", item.subject), "clinic_id": item.clinic_id.id, "company_id": item.company_id.id, "task_type_id": task_type.id, "assigned_user_id": item.follow_up_user_id.id, "due_datetime": item.follow_up_datetime, "patient_id": item.patient_id.id, "description": item.body})
            task.action_open()
            item.follow_up_task_id = task
