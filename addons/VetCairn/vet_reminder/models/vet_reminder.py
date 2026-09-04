from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class VetReminder(models.Model):
    _name = "vet.reminder"
    _description = "Veterinary Reminder"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "due_date, priority desc, id"

    name = fields.Char(string="Reminder Number", required=True, readonly=True, copy=False, default=lambda self: self.env._("New"), index=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    clinic_id = fields.Many2one("vet.clinic", required=True, ondelete="restrict", domain="[('company_id','=',company_id)]", index=True, tracking=True)
    patient_id = fields.Many2one("vet.patient", required=True, ondelete="cascade", domain="[('company_id','=',company_id)]", index=True, tracking=True)
    client_id = fields.Many2one(related="patient_id.primary_owner_id", store=True, index=True)
    client_email = fields.Char(related="client_id.email", string="Client Email")
    client_phone = fields.Char(related="client_id.phone", string="Client Phone")
    reminder_type_id = fields.Many2one("vet.reminder.type", required=True, ondelete="restrict", domain="[('company_id','=',company_id)]", index=True, tracking=True)
    appointment_id = fields.Many2one("vet.appointment", ondelete="set null", domain="[('patient_id','=',patient_id)]")
    vaccination_id = fields.Many2one("vet.vaccination", ondelete="set null", domain="[('patient_id','=',patient_id)]")
    channel = fields.Selection([("email","Email"),("sms","SMS"),("phone","Phone Call"),("mail","Postal Mail"),("internal","Internal")], required=True, default="email", tracking=True)
    priority = fields.Selection([("0","Normal"),("1","Important"),("2","Urgent")], default="0", required=True, index=True)
    state = fields.Selection([("draft","Draft"),("pending","Pending"),("sent","Sent / Completed"),("failed","Failed"),("cancelled","Cancelled")], default="draft", required=True, index=True, tracking=True)
    due_date = fields.Date(required=True, default=fields.Date.context_today, index=True, tracking=True)
    is_overdue = fields.Boolean(compute="_compute_is_overdue", search="_search_is_overdue")
    subject = fields.Char(required=True, tracking=True)
    message = fields.Text(required=True)
    sent_at = fields.Datetime(readonly=True, copy=False)
    completed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    delivery_reference = fields.Char(copy=False, tracking=True)
    failure_reason = fields.Text(tracking=True)
    notes = fields.Text()

    _name_company_unique = models.Constraint("UNIQUE(name, company_id)", "Reminder numbers must be unique within a company.")

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", self.env._("New")) == self.env._("New"):
                values["name"] = self.env["ir.sequence"].next_by_code("vet.reminder") or self.env._("New")
            if values.get("reminder_type_id"):
                reminder_type=self.env["vet.reminder.type"].browse(values["reminder_type_id"])
                values.setdefault("channel",reminder_type.default_channel); values.setdefault("subject",reminder_type.subject_template or reminder_type.name); values.setdefault("message",reminder_type.message_template or reminder_type.name)
        return super().create(vals_list)

    @api.depends("due_date", "state")
    def _compute_is_overdue(self):
        today=fields.Date.context_today(self)
        for rec in self: rec.is_overdue=bool(rec.state=="pending" and rec.due_date<today)
    def _search_is_overdue(self, operator, value):
        domain=[("state","=","pending"),("due_date","<",fields.Date.context_today(self))]
        return domain if ((operator in ("=","==") and value) or (operator=="!=" and not value)) else ["!"]+domain
    @api.onchange("patient_id")
    def _onchange_patient_id(self):
        if self.patient_id: self.clinic_id=self.patient_id.clinic_id; self.company_id=self.patient_id.company_id
    @api.onchange("reminder_type_id")
    def _onchange_reminder_type_id(self):
        if self.reminder_type_id:
            self.channel=self.reminder_type_id.default_channel; self.subject=self.reminder_type_id.subject_template or self.reminder_type_id.name; self.message=self.reminder_type_id.message_template or self.reminder_type_id.name
    def action_schedule(self):
        if self.filtered(lambda r:r.state!="draft"): raise UserError("Only draft reminders can be scheduled.")
        for rec in self:
            if rec.channel=="email" and not rec.client_email: raise ValidationError("The client needs an email address for an email reminder.")
            if rec.channel in ("sms","phone") and not rec.client_phone: raise ValidationError("The client needs a phone number for this reminder channel.")
        self.write({"state":"pending"}); return True
    def action_mark_sent(self):
        if self.filtered(lambda r:r.state not in ("pending","failed")): raise UserError("Only pending or failed reminders can be marked sent.")
        self.write({"state":"sent","sent_at":fields.Datetime.now(),"completed_by_id":self.env.user.id,"failure_reason":False}); return True
    def action_fail(self):
        if self.filtered(lambda r:r.state!="pending"): raise UserError("Only pending reminders can be marked failed.")
        self.write({"state":"failed"}); return True
    def action_cancel(self):
        if self.filtered(lambda r:r.state not in ("draft","pending","failed")): raise UserError("This reminder cannot be cancelled.")
        self.write({"state":"cancelled"}); return True
