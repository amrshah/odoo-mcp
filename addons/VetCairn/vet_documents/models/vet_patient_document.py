from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class VetPatientDocument(models.Model):
    _name = "vet.patient.document"
    _description = "Veterinary Patient Document"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "document_date desc, id desc"

    name = fields.Char(string="Document Number", required=True, readonly=True, copy=False, default=lambda self: self.env._("New"), index=True)
    title = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    clinic_id = fields.Many2one("vet.clinic", required=True, ondelete="restrict", domain="[('company_id','=',company_id)]", index=True, tracking=True)
    patient_id = fields.Many2one("vet.patient", required=True, ondelete="cascade", domain="[('company_id','=',company_id)]", index=True, tracking=True)
    client_id = fields.Many2one(related="patient_id.primary_owner_id", store=True, index=True)
    document_type_id = fields.Many2one("vet.document.type", required=True, ondelete="restrict", domain="[('company_id','=',company_id)]", index=True, tracking=True)
    category = fields.Selection(related="document_type_id.category", store=True, index=True)
    encounter_id = fields.Many2one("vet.encounter", ondelete="set null", domain="[('patient_id','=',patient_id)]")
    appointment_id = fields.Many2one("vet.appointment", ondelete="set null", domain="[('patient_id','=',patient_id)]")
    state = fields.Selection([("draft","Draft"),("current","Current"),("signed","Signed"),("expired","Expired"),("void","Void")], default="draft", required=True, index=True, tracking=True)
    document_date = fields.Date(default=fields.Date.context_today, required=True, index=True)
    expiry_date = fields.Date(index=True, tracking=True)
    is_expired = fields.Boolean(compute="_compute_is_expired", search="_search_is_expired")
    file_data = fields.Binary(string="Document File", attachment=True, required=True)
    filename = fields.Char(required=True)
    mime_type = fields.Char(readonly=True)
    signed_by_name = fields.Char(tracking=True)
    signed_at = fields.Datetime(readonly=True, copy=False, tracking=True)
    witnessed_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    description = fields.Text()
    void_reason = fields.Text(tracking=True)

    _name_company_unique = models.Constraint("UNIQUE(name, company_id)", "Document numbers must be unique within a company.")

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", self.env._("New")) == self.env._("New"):
                values["name"] = self.env["ir.sequence"].next_by_code("vet.patient.document") or self.env._("New")
            if values.get("document_type_id") and not values.get("expiry_date"):
                doc_type=self.env["vet.document.type"].browse(values["document_type_id"])
                base=fields.Date.to_date(values.get("document_date") or fields.Date.context_today(self))
                if doc_type.default_validity_days: values["expiry_date"]=base+timedelta(days=doc_type.default_validity_days)
        return super().create(vals_list)

    @api.depends("expiry_date", "state")
    def _compute_is_expired(self):
        today=fields.Date.context_today(self)
        for rec in self: rec.is_expired=bool(rec.expiry_date and rec.expiry_date < today and rec.state != "void")

    def _search_is_expired(self, operator, value):
        domain=[("expiry_date","<",fields.Date.context_today(self)),("state","!=","void")]
        return domain if ((operator in ("=","==") and value) or (operator=="!=" and not value)) else ["!"]+domain

    @api.onchange("patient_id")
    def _onchange_patient_id(self):
        if self.patient_id: self.clinic_id=self.patient_id.clinic_id; self.company_id=self.patient_id.company_id

    @api.constrains("document_date", "expiry_date", "document_type_id")
    def _check_dates(self):
        for rec in self:
            if rec.expiry_date and rec.expiry_date < rec.document_date: raise ValidationError("Document expiry cannot precede its document date.")
            if rec.document_type_id.expiry_required and not rec.expiry_date: raise ValidationError("This document type requires an expiry date.")

    def action_activate(self):
        if self.filtered(lambda r:r.state!="draft"): raise UserError("Only draft documents can be activated.")
        self.write({"state":"current"}); return True
    def action_sign(self):
        if self.filtered(lambda r:r.state not in ("draft","current")): raise UserError("This document cannot be signed in its current status.")
        if self.filtered(lambda r:not r.signed_by_name): raise ValidationError("Enter the signer's name before marking the document signed.")
        self.write({"state":"signed","signed_at":fields.Datetime.now(),"witnessed_by_id":self.env.user.id}); return True
    def action_mark_expired(self):
        if self.filtered(lambda r:r.state not in ("current","signed")): raise UserError("Only current or signed documents can be expired.")
        self.write({"state":"expired"}); return True
    def action_void(self):
        if self.filtered(lambda r:r.state=="void"): raise UserError("The document is already void.")
        self.write({"state":"void"}); return True
