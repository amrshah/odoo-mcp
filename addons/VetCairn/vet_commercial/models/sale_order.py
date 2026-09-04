from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_vet_estimate = fields.Boolean(string="Veterinary Estimate", default=False, index=True, tracking=True)
    vet_company_id = fields.Many2one(related="company_id", string="Veterinary Company")
    vet_clinic_id = fields.Many2one("vet.clinic", string="Clinic", domain="[('company_id','=',company_id)]", index=True, tracking=True)
    vet_patient_id = fields.Many2one("vet.patient", string="Patient", domain="[('company_id','=',company_id)]", index=True, tracking=True)
    vet_appointment_id = fields.Many2one("vet.appointment", string="Appointment", domain="[('patient_id','=',vet_patient_id)]", index=True)
    vet_encounter_id = fields.Many2one("vet.encounter", string="Clinical Encounter", domain="[('patient_id','=',vet_patient_id)]", index=True)
    vet_treatment_plan_id = fields.Many2one("vet.treatment.plan", string="Treatment Plan", domain="[('patient_id','=',vet_patient_id)]", index=True)
    vet_approval_state = fields.Selection([("pending","Pending Client Decision"),("accepted","Accepted by Client"),("declined","Declined by Client")], default="pending", required=True, index=True, tracking=True)
    vet_approved_at = fields.Datetime(string="Client Decision At", readonly=True, copy=False)
    vet_approved_by_name = fields.Char(string="Client Decision By", tracking=True)
    vet_decline_reason = fields.Text(string="Decline Reason", tracking=True)
    vet_deposit_percent = fields.Float(string="Requested Deposit (%)", default=0.0, tracking=True)
    vet_deposit_amount = fields.Monetary(string="Requested Deposit", compute="_compute_vet_deposit_amount", currency_field="currency_id")
    vet_clinical_notes = fields.Text(string="Clinical / Estimate Notes")

    @api.depends("amount_total", "vet_deposit_percent")
    def _compute_vet_deposit_amount(self):
        for order in self:
            order.vet_deposit_amount = order.amount_total * order.vet_deposit_percent / 100

    @api.onchange("vet_patient_id")
    def _onchange_vet_patient_id(self):
        if self.vet_patient_id:
            self.vet_clinic_id = self.vet_patient_id.clinic_id
            self.partner_id = self.vet_patient_id.primary_owner_id

    @api.constrains("vet_deposit_percent")
    def _check_vet_deposit_percent(self):
        for order in self:
            if not 0 <= order.vet_deposit_percent <= 100:
                raise ValidationError("Requested deposit must be between 0% and 100%.")

    @api.constrains("is_vet_estimate", "vet_patient_id", "partner_id")
    def _check_vet_estimate_patient(self):
        for order in self.filtered("is_vet_estimate"):
            if not order.vet_patient_id:
                raise ValidationError("A veterinary estimate requires a patient.")
            if order.vet_patient_id.primary_owner_id and order.partner_id != order.vet_patient_id.primary_owner_id:
                raise ValidationError("The estimate client must be the patient's primary owner.")

    def action_vet_accept(self):
        invalid = self.filtered(lambda order: not order.is_vet_estimate or order.state not in ("draft", "sent") or order.vet_approval_state != "pending")
        if invalid:
            raise UserError("Only a pending draft or sent veterinary estimate can be accepted.")
        if self.filtered(lambda order: not order.vet_approved_by_name):
            raise ValidationError("Enter the client's name before recording acceptance.")
        self.write({"vet_approval_state":"accepted", "vet_approved_at":fields.Datetime.now(), "vet_decline_reason":False})
        return True

    def action_vet_decline(self):
        invalid = self.filtered(lambda order: not order.is_vet_estimate or order.state not in ("draft", "sent") or order.vet_approval_state != "pending")
        if invalid:
            raise UserError("Only a pending draft or sent veterinary estimate can be declined.")
        if self.filtered(lambda order: not order.vet_decline_reason):
            raise ValidationError("Enter a decline reason before recording the decision.")
        self.write({"vet_approval_state":"declined", "vet_approved_at":fields.Datetime.now()})
        return True

    def action_confirm(self):
        unapproved = self.filtered(lambda order: order.is_vet_estimate and order.vet_approval_state != "accepted")
        if unapproved:
            raise UserError("Record client acceptance before confirming a veterinary estimate.")
        return super().action_confirm()

    def _prepare_invoice(self):
        values = super()._prepare_invoice()
        if self.is_vet_estimate:
            values.update({
                "vet_patient_id": self.vet_patient_id.id,
                "vet_clinic_id": self.vet_clinic_id.id,
                "vet_appointment_id": self.vet_appointment_id.id,
                "vet_encounter_id": self.vet_encounter_id.id,
                "vet_treatment_plan_id": self.vet_treatment_plan_id.id,
                "vet_estimate_id": self.id,
            })
        return values
