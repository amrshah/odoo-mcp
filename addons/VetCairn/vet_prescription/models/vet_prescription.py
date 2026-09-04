from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class VetPrescription(models.Model):
    _name = "vet.prescription"
    _description = "Veterinary Prescription"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "prescribed_at desc, id desc"

    name = fields.Char(string="Prescription Number", required=True, readonly=True, copy=False, default=lambda self: self.env._("New"), index=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    clinic_id = fields.Many2one("vet.clinic", required=True, ondelete="restrict", domain="[('company_id','=',company_id)]", index=True, tracking=True)
    patient_id = fields.Many2one("vet.patient", required=True, ondelete="restrict", domain="[('company_id','=',company_id),('status','=','active')]", index=True, tracking=True)
    client_id = fields.Many2one(related="patient_id.primary_owner_id", store=True, index=True)
    encounter_id = fields.Many2one("vet.encounter", ondelete="set null", domain="[('patient_id','=',patient_id)]", tracking=True)
    prescriber_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, domain="[('vet_is_provider','=',True)]", tracking=True)
    medication_id = fields.Many2one("vet.medication", required=True, ondelete="restrict", domain="[('company_id','=',company_id)]", tracking=True)
    controlled = fields.Boolean(related="medication_id.controlled", store=True, index=True)
    state = fields.Selection([("draft","Draft"),("pending","Pending Approval"),("approved","Approved"),("dispensed","Dispensed"),("denied","Denied"),("cancelled","Cancelled")], default="draft", required=True, index=True, tracking=True)
    prescribed_at = fields.Datetime(default=fields.Datetime.now, required=True, tracking=True)
    dose = fields.Char(required=True, tracking=True)
    route = fields.Selection([("oral","Oral"),("topical","Topical"),("subcutaneous","Subcutaneous"),("intramuscular","Intramuscular"),("intravenous","Intravenous"),("other","Other")], required=True, tracking=True)
    frequency = fields.Char(required=True, tracking=True)
    duration = fields.Char(tracking=True)
    quantity = fields.Float(required=True, default=1.0, tracking=True)
    quantity_unit = fields.Char(default="unit(s)", required=True)
    refills_authorized = fields.Integer(default=0, tracking=True)
    refills_remaining = fields.Integer(readonly=True, copy=False)
    instructions = fields.Text(required=True, tracking=True)
    clinical_indication = fields.Char(required=True, tracking=True)
    approved_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    dispensed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    dispensed_at = fields.Datetime(readonly=True, copy=False)
    lot_number = fields.Char(copy=False, tracking=True)
    expiry_date = fields.Date(tracking=True)
    denial_reason = fields.Text(tracking=True)

    _name_company_unique = models.Constraint("UNIQUE(name, company_id)", "Prescription numbers must be unique within a company.")

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", self.env._("New")) == self.env._("New"):
                values["name"] = self.env["ir.sequence"].next_by_code("vet.prescription") or self.env._("New")
            values.setdefault("refills_remaining", values.get("refills_authorized", 0))
            if values.get("medication_id") and not values.get("route"):
                values["route"] = self.env["vet.medication"].browse(values["medication_id"]).default_route
        return super().create(vals_list)

    @api.onchange("patient_id")
    def _onchange_patient_id(self):
        if self.patient_id:
            self.clinic_id = self.patient_id.clinic_id; self.company_id = self.patient_id.company_id

    @api.onchange("medication_id")
    def _onchange_medication_id(self):
        if self.medication_id: self.route = self.medication_id.default_route

    @api.constrains("quantity", "refills_authorized")
    def _check_amounts(self):
        for rec in self:
            if rec.quantity <= 0: raise ValidationError("Prescription quantity must be greater than zero.")
            if rec.refills_authorized < 0: raise ValidationError("Authorized refills cannot be negative.")

    def _move(self, target, allowed, extra=None):
        if self.filtered(lambda r: r.state not in allowed): raise UserError("This prescription status change is not allowed.")
        vals={"state":target}; vals.update(extra or {}); self.write(vals); return True

    def action_submit(self): return self._move("pending", ("draft",))
    def action_approve(self):
        if not self.env.user.has_group("vet_prescription.group_vet_controlled_medication"): raise AccessError("Controlled-medication approval permission is required.")
        return self._move("approved", ("pending",), {"approved_by_id":self.env.user.id,"approved_at":fields.Datetime.now()})
    def action_deny(self): return self._move("denied", ("pending",))
    def action_dispense(self):
        today=fields.Date.context_today(self)
        if self.filtered(lambda r: r.expiry_date and r.expiry_date < today): raise ValidationError("An expired medication cannot be dispensed.")
        return self._move("dispensed", ("approved",), {"dispensed_by_id":self.env.user.id,"dispensed_at":fields.Datetime.now()})
    def action_cancel(self): return self._move("cancelled", ("draft","pending","approved"))
