import urllib.parse

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HmsCharge(models.Model):
    """Every billable event in the hospital is a charge line the moment it happens —
    consult on registration, test on order approval, medicine on dispense, dose on the MAR,
    bed on discharge, procedure on sign-out, blood on issue. The bill is built from these."""
    _name = "hms.charge"
    _description = "Billable Charge"
    _order = "create_date"

    visit_id = fields.Many2one("hms.visit", required=True, ondelete="cascade", index=True)
    patient_id = fields.Many2one(related="visit_id.patient_id", store=True)
    product_id = fields.Many2one("product.product", required=True)
    description = fields.Char(required=True)
    quantity = fields.Float(default=1.0)
    price_unit = fields.Float(required=True)
    amount = fields.Float(compute="_compute_amount", store=True)
    source = fields.Selection([
        ("registration", "Registration"), ("consult", "Consultation"), ("order", "Investigation"), ("pharmacy", "Pharmacy"),
        ("mar", "Ward Dose"), ("ward", "Bed Charges"), ("surgery", "Surgery"), ("blood", "Blood Bank"), ("other", "Other"),
    ], default="other", required=True)
    order_id = fields.Many2one("hms.order", ondelete="set null")
    invoice_line_id = fields.Many2one("account.move.line", readonly=True, ondelete="set null")
    invoiced = fields.Boolean(compute="_compute_invoiced", store=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.depends("quantity", "price_unit")
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.quantity * rec.price_unit

    @api.depends("invoice_line_id")
    def _compute_invoiced(self):
        for rec in self:
            rec.invoiced = bool(rec.invoice_line_id)

    @api.model
    def create_invoice_for_visit(self, visit):
        """Build (and post) one itemised bill from the visit's un-invoiced charges,
        applying the approved discount to every line. Returns an action to open it."""
        charges = visit.charge_ids.filtered(lambda c: not c.invoice_line_id)
        if not charges:
            raise UserError(_("No new charges to bill."))
        if visit.discount_pending:
            raise UserError(_("A discount request is still pending approval. The bill cannot be raised until the HOD decides."))
        discount = visit.approved_discount
        move = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": visit.patient_id.partner_id.id,
            "invoice_date": fields.Date.today(),
            "hms_visit_id": visit.id,
            "hms_patient_id": visit.patient_id.id,
            "narration": f"Visit {visit.name} · {visit.department_id.name} · {visit.doctor_id.display_name or ''}" + (f" · Discount {discount:g}% approved by {visit.discount_request_ids.filtered(lambda d: d.state == 'approved')[:1].approver_id.display_name}" if discount else ""),
            "invoice_line_ids": [(0, 0, {
                "product_id": c.product_id.id, "name": c.description, "quantity": c.quantity,
                "price_unit": c.price_unit, "discount": discount, "tax_ids": [(5, 0, 0)],
            }) for c in charges],
        })
        for c, line in zip(charges, move.invoice_line_ids):
            c.invoice_line_id = line
        move.action_post()
        return {"type": "ir.actions.act_window", "res_model": "account.move", "res_id": move.id, "view_mode": "form", "target": "current"}


class AccountMove(models.Model):
    _inherit = "account.move"

    hms_visit_id = fields.Many2one("hms.visit", string="Hospital Visit", index=True, copy=False)
    hms_patient_id = fields.Many2one("hms.patient", string="Patient", index=True, copy=False)

    def action_hms_whatsapp(self):
        self.ensure_one()
        p = self.hms_patient_id
        msg = _("Assalam o Alaikum %s, your bill %s from %s: total PKR %s, outstanding PKR %s.") % (
            p.name, self.name, self.company_id.name, f"{self.amount_total:,.0f}", f"{self.amount_residual:,.0f}")
        return self.env["hms.whatsapp"].link_action(p.whatsapp or p.phone, msg)

    def action_hms_print_bill(self):
        return self.env.ref("stratos_hms.action_report_bill").report_action(self)


class HmsWhatsapp(models.AbstractModel):
    """One tap sends any document to the patient's phone. Uses the wa.me deep link so no
    WhatsApp Business API is required; swap `link_action` for an API call when you have one."""
    _name = "hms.whatsapp"
    _description = "WhatsApp helper"

    @api.model
    def normalise(self, phone):
        digits = "".join(ch for ch in (phone or "") if ch.isdigit())
        if digits.startswith("0"):
            digits = "92" + digits[1:]
        return digits

    @api.model
    def link_action(self, phone, message):
        number = self.normalise(phone)
        if not number:
            raise UserError(_("No phone number on the patient record."))
        url = f"https://wa.me/{number}?text={urllib.parse.quote(message)}"
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}
