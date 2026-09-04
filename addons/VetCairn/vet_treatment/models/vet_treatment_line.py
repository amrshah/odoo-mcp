from odoo import api, fields, models
from odoo.exceptions import UserError


class VetTreatmentLine(models.Model):
    _name = "vet.treatment.line"
    _description = "Veterinary Treatment Activity"
    _order = "due_datetime, sequence, id"

    sequence = fields.Integer(default=10)
    plan_id = fields.Many2one("vet.treatment.plan", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="plan_id.company_id", store=True, index=True)
    clinic_id = fields.Many2one(related="plan_id.clinic_id", store=True, index=True)
    patient_id = fields.Many2one(related="plan_id.patient_id", store=True, index=True)
    name = fields.Char(string="Activity", required=True)
    category = fields.Selection([("medication","Medication"),("procedure","Procedure"),("monitoring","Monitoring / Vitals"),("nursing","Nursing Care"),("feeding","Feeding"),("diagnostic","Diagnostic"),("other","Other")], default="nursing", required=True, index=True)
    assigned_to_id = fields.Many2one("res.users", string="Assigned To", index=True)
    due_datetime = fields.Datetime(required=True, default=fields.Datetime.now, index=True)
    state = fields.Selection([("planned","Planned"),("in_progress","In Progress"),("completed","Completed"),("skipped","Skipped")], default="planned", required=True, index=True)
    is_overdue = fields.Boolean(compute="_compute_is_overdue", search="_search_is_overdue")
    instructions = fields.Text(required=True)
    completed_at = fields.Datetime(readonly=True, copy=False)
    completed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    result_notes = fields.Text()
    skip_reason = fields.Text()

    @api.depends("due_datetime", "state")
    def _compute_is_overdue(self):
        now=fields.Datetime.now()
        for line in self: line.is_overdue=bool(line.state in ("planned","in_progress") and line.due_datetime < now)
    def _search_is_overdue(self, operator, value):
        domain=[("state","in",("planned","in_progress")),("due_datetime","<",fields.Datetime.now())]
        return domain if ((operator in ("=","==") and value) or (operator=="!=" and not value)) else ["!"]+domain
    def action_start(self):
        if self.filtered(lambda l:l.state!="planned"): raise UserError("Only planned activities can be started.")
        self.write({"state":"in_progress"}); return True
    def action_complete(self):
        if self.filtered(lambda l:l.state not in ("planned","in_progress")): raise UserError("This activity cannot be completed.")
        self.write({"state":"completed","completed_at":fields.Datetime.now(),"completed_by_id":self.env.user.id}); return True
    def action_skip(self):
        if self.filtered(lambda l:l.state not in ("planned","in_progress")): raise UserError("This activity cannot be skipped.")
        self.write({"state":"skipped","completed_at":fields.Datetime.now(),"completed_by_id":self.env.user.id}); return True
