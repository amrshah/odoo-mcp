from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .drug import ROUTES, FREQUENCIES


class HmsDispense(models.Model):
    """Pharmacy verification queue. A signed prescription lands here as a live order.
    The pharmacist verifies each line (allergy blocking is automatic), then dispenses; the
    charge posts to the bill on dispense."""
    _name = "hms.dispense"
    _description = "Pharmacy Dispense Order"
    _inherit = ["mail.thread"]
    _order = "create_date"

    name = fields.Char(readonly=True, copy=False, default="New")
    consult_id = fields.Many2one("hms.consult", ondelete="cascade")
    visit_id = fields.Many2one("hms.visit", required=True, ondelete="cascade")
    patient_id = fields.Many2one(related="visit_id.patient_id", store=True)
    doctor_id = fields.Many2one(related="consult_id.doctor_id", store=True)
    has_allergy = fields.Boolean(related="patient_id.has_allergy")
    allergy_summary = fields.Char(related="visit_id.allergy_summary")
    line_ids = fields.One2many("hms.dispense.line", "dispense_id", string="Lines")
    state = fields.Selection([("to_verify", "To Verify"), ("verified", "Verified"), ("dispensed", "Dispensed"), ("cancelled", "Cancelled")], default="to_verify", tracking=True)
    pharmacist_id = fields.Many2one("hms.practitioner")
    blocked = fields.Boolean(compute="_compute_blocked", store=True, help="At least one line is blocked by an allergy.")
    amount_total = fields.Float(compute="_compute_total")

    @api.depends("line_ids.blocked", "line_ids.state")
    def _compute_blocked(self):
        for rec in self:
            rec.blocked = any(l.blocked and l.state != "rejected" for l in rec.line_ids)

    def _compute_total(self):
        for rec in self:
            rec.amount_total = sum(l.amount for l in rec.line_ids if l.state != "rejected")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("hms.dispense") or "New"
        return super().create(vals_list)

    def action_verify(self):
        for rec in self:
            if rec.blocked:
                raise UserError(_("A line is blocked by an allergy conflict. Reject it or record a documented override before verifying."))
            rec.line_ids.filtered(lambda l: l.state == "pending").write({"state": "verified"})
            rec.write({"state": "verified", "pharmacist_id": self.env["hms.practitioner"].get_current().id})

    def action_dispense(self):
        Charge = self.env["hms.charge"]
        for rec in self:
            if rec.state != "verified":
                raise UserError(_("Verify the prescription first."))
            for line in rec.line_ids.filtered(lambda l: l.state == "verified"):
                line.state = "dispensed"
                Charge.create({
                    "visit_id": rec.visit_id.id, "product_id": line.drug_id.get_or_create_product().id,
                    "description": f"{line.drug_id.name} × {line.quantity}", "quantity": line.quantity,
                    "price_unit": line.drug_id.price, "source": "pharmacy",
                })
            rec.write({"state": "dispensed"})
            rec.visit_id._advance_stage("treatment")
            rec.visit_id.message_post(body=_("Medicines dispensed by %s (%s lines).") % (rec.pharmacist_id.display_name, len(rec.line_ids)))

    def action_cancel(self):
        self.write({"state": "cancelled"})


class HmsDispenseLine(models.Model):
    _name = "hms.dispense.line"
    _description = "Dispense Line"

    dispense_id = fields.Many2one("hms.dispense", required=True, ondelete="cascade")
    prescription_line_id = fields.Many2one("hms.prescription.line", ondelete="set null")
    drug_id = fields.Many2one("hms.drug", required=True)
    dose = fields.Char()
    route = fields.Selection(ROUTES)
    frequency = fields.Selection(FREQUENCIES)
    duration_days = fields.Integer()
    quantity = fields.Integer(default=1)
    blocked = fields.Boolean(compute="_compute_blocked", store=True)
    block_reason = fields.Char(compute="_compute_blocked", store=True)
    override_reason = fields.Char(help="Documented pharmacist/doctor override of an allergy block.")
    state = fields.Selection([("pending", "Pending"), ("verified", "Verified"), ("dispensed", "Dispensed"), ("rejected", "Rejected")], default="pending")
    amount = fields.Float(compute="_compute_amount")

    @api.model_create_multi
    def create(self, vals_list):
        Rx = self.env["hms.prescription.line"]
        for vals in vals_list:
            rx = Rx.browse(vals.get("prescription_line_id")) if vals.get("prescription_line_id") else Rx
            if rx:
                vals.setdefault("drug_id", rx.drug_id.id)
                vals.setdefault("dose", rx.dose)
                vals.setdefault("route", rx.route)
                vals.setdefault("frequency", rx.frequency)
                vals.setdefault("duration_days", rx.duration_days)
                vals.setdefault("quantity", rx.quantity)
        return super().create(vals_list)

    @api.onchange("prescription_line_id")
    def _onchange_rx(self):
        rx = self.prescription_line_id
        if rx:
            self.drug_id, self.dose, self.route, self.frequency, self.duration_days, self.quantity = rx.drug_id, rx.dose, rx.route, rx.frequency, rx.duration_days, rx.quantity

    @api.depends("drug_id", "dispense_id.patient_id", "override_reason")
    def _compute_blocked(self):
        for rec in self:
            warnings = rec.drug_id.check_against_patient(rec.dispense_id.patient_id) if rec.drug_id and rec.dispense_id.patient_id else []
            rec.blocked = bool(warnings) and not rec.override_reason
            rec.block_reason = warnings[0] if warnings else False

    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.quantity * rec.drug_id.price

    def action_reject(self):
        self.write({"state": "rejected"})
