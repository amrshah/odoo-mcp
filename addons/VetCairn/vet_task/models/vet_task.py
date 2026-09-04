from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class VetTaskType(models.Model):
    _name = "vet.task.type"
    _description = "Veterinary Task Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer(default=0)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    default_priority = fields.Selection([("0", "Normal"), ("1", "Important"), ("2", "Urgent"), ("3", "Critical")], default="0", required=True)
    default_due_days = fields.Integer(string="Default Due In (Days)", default=0)
    clinical = fields.Boolean(string="Clinical Task")
    description = fields.Text()

    _code_company_unique = models.Constraint("UNIQUE(code, company_id)", "Task type codes must be unique within a company.")

    @api.constrains("default_due_days")
    def _check_due_days(self):
        if any(record.default_due_days < 0 for record in self):
            raise ValidationError("Default due days cannot be negative.")


class VetTask(models.Model):
    _name = "vet.task"
    _description = "Veterinary Task"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority desc, due_datetime, id desc"

    name = fields.Char(string="Task Number", required=True, readonly=True, copy=False, default=lambda self: self.env._("New"), index=True)
    title = fields.Char(required=True, tracking=True, index=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    clinic_id = fields.Many2one("vet.clinic", required=True, ondelete="restrict", domain="[('company_id', '=', company_id)]", index=True, tracking=True)
    task_type_id = fields.Many2one("vet.task.type", string="Task Type", required=True, ondelete="restrict", domain="[('company_id', '=', company_id)]", tracking=True)
    priority = fields.Selection([("0", "Normal"), ("1", "Important"), ("2", "Urgent"), ("3", "Critical")], default="0", required=True, tracking=True, index=True)
    state = fields.Selection([("draft", "Draft"), ("open", "Open"), ("in_progress", "In Progress"), ("blocked", "Blocked"), ("done", "Completed"), ("cancelled", "Cancelled")], default="draft", required=True, tracking=True, index=True)
    assigned_user_id = fields.Many2one("res.users", string="Assigned To", required=True, default=lambda self: self.env.user, ondelete="restrict", tracking=True, index=True, domain="[('share', '=', False)]")
    created_by_id = fields.Many2one("res.users", string="Created By", default=lambda self: self.env.user, readonly=True, copy=False)
    due_datetime = fields.Datetime(required=True, default=fields.Datetime.now, tracking=True, index=True)
    started_at = fields.Datetime(readonly=True, copy=False)
    completed_at = fields.Datetime(readonly=True, copy=False)
    completed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    patient_id = fields.Many2one("vet.patient", ondelete="set null", domain="[('company_id', '=', company_id), ('clinic_id', '=', clinic_id)]", tracking=True, index=True)
    client_id = fields.Many2one("res.partner", related="patient_id.primary_owner_id", store=True, readonly=True)
    appointment_id = fields.Many2one("vet.appointment", ondelete="set null", domain="[('patient_id', '=', patient_id)]", tracking=True)
    encounter_id = fields.Many2one("vet.encounter", ondelete="set null", domain="[('patient_id', '=', patient_id)]", tracking=True)
    description = fields.Html(sanitize=True)
    blocking_reason = fields.Text(tracking=True)
    outcome = fields.Text(tracking=True)
    checklist_line_ids = fields.One2many("vet.task.checklist", "task_id", string="Checklist", copy=True)
    checklist_progress = fields.Float(compute="_compute_checklist_progress")
    checklist_label = fields.Char(compute="_compute_checklist_progress")
    is_overdue = fields.Boolean(compute="_compute_is_overdue", search="_search_is_overdue")

    _name_company_unique = models.Constraint("UNIQUE(name, company_id)", "Task numbers must be unique within a company.")

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", self.env._("New")) == self.env._("New"):
                values["name"] = self.env["ir.sequence"].next_by_code("vet.task") or self.env._("New")
            task_type = self.env["vet.task.type"].browse(values.get("task_type_id"))
            if task_type:
                values.setdefault("priority", task_type.default_priority)
                if not values.get("due_datetime"):
                    values["due_datetime"] = fields.Datetime.now() + timedelta(days=task_type.default_due_days)
        return super().create(vals_list)

    @api.depends("checklist_line_ids", "checklist_line_ids.is_done")
    def _compute_checklist_progress(self):
        for task in self:
            total = len(task.checklist_line_ids)
            done = len(task.checklist_line_ids.filtered("is_done"))
            task.checklist_progress = done * 100 / total if total else 0
            task.checklist_label = self.env._("%(done)s of %(total)s complete", done=done, total=total)

    @api.depends("due_datetime", "state")
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for task in self:
            task.is_overdue = bool(task.due_datetime and task.due_datetime < now and task.state in ("open", "in_progress", "blocked"))

    def _search_is_overdue(self, operator, value):
        domain = [("state", "in", ("open", "in_progress", "blocked")), ("due_datetime", "<", fields.Datetime.now())]
        return domain if ((operator in ("=", "==") and value) or (operator == "!=" and not value)) else ["!"] + domain

    @api.onchange("patient_id")
    def _onchange_patient_id(self):
        if self.patient_id:
            self.clinic_id = self.patient_id.clinic_id
            self.company_id = self.patient_id.company_id

    @api.onchange("task_type_id")
    def _onchange_task_type_id(self):
        if self.task_type_id:
            self.priority = self.task_type_id.default_priority
            self.due_datetime = fields.Datetime.now() + timedelta(days=self.task_type_id.default_due_days)

    @api.constrains("company_id", "clinic_id", "patient_id", "task_type_id")
    def _check_company(self):
        for task in self:
            records = task.clinic_id.company_id | task.task_type_id.company_id | task.patient_id.company_id
            if records and records != task.company_id:
                raise ValidationError("The task, clinic, type, and patient must belong to the same company.")

    def action_open(self):
        if self.filtered(lambda task: task.state != "draft"):
            raise UserError("Only draft tasks can be opened.")
        self.write({"state": "open"})
        return True

    def action_start(self):
        if self.filtered(lambda task: task.state not in ("open", "blocked")):
            raise UserError("Only open or blocked tasks can be started.")
        self.write({"state": "in_progress", "started_at": fields.Datetime.now(), "blocking_reason": False})
        return True

    def action_block(self):
        if self.filtered(lambda task: task.state not in ("open", "in_progress")):
            raise UserError("Only active tasks can be blocked.")
        if self.filtered(lambda task: not task.blocking_reason):
            raise ValidationError("Enter a blocking reason before blocking the task.")
        self.write({"state": "blocked"})
        return True

    def action_done(self):
        if self.filtered(lambda task: task.state not in ("open", "in_progress")):
            raise UserError("Only open or in-progress tasks can be completed.")
        pending_required = self.mapped("checklist_line_ids").filtered(lambda line: line.is_required and not line.is_done)
        if pending_required:
            raise ValidationError("Complete every required checklist item before finishing the task.")
        self.write({"state": "done", "completed_at": fields.Datetime.now(), "completed_by_id": self.env.user.id})
        return True

    def action_cancel(self):
        if self.filtered(lambda task: task.state in ("done", "cancelled")):
            raise UserError("Completed or cancelled tasks cannot be cancelled again.")
        self.write({"state": "cancelled"})
        return True

    def action_reset(self):
        if self.filtered(lambda task: task.state not in ("done", "cancelled")):
            raise UserError("Only completed or cancelled tasks can be reopened.")
        self.write({"state": "open", "completed_at": False, "completed_by_id": False})
        return True


class VetTaskChecklist(models.Model):
    _name = "vet.task.checklist"
    _description = "Veterinary Task Checklist Item"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    task_id = fields.Many2one("vet.task", required=True, ondelete="cascade", index=True)
    name = fields.Char(required=True)
    is_required = fields.Boolean(default=True)
    is_done = fields.Boolean(string="Done")
    completed_at = fields.Datetime(readonly=True, copy=False)
    completed_by_id = fields.Many2one("res.users", readonly=True, copy=False)

    def write(self, values):
        if "is_done" in values:
            values.update({"completed_at": fields.Datetime.now() if values["is_done"] else False, "completed_by_id": self.env.user.id if values["is_done"] else False})
        return super().write(values)
