from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


STAGES = [
    ("registered", "Registered"),
    ("triaged", "Triaged"),
    ("consult", "In Consult"),
    ("orders", "Orders Placed"),
    ("treatment", "Treatment"),
    ("results", "Results"),
    ("discharged", "Discharged"),
]
STAGE_RANK = {k: i for i, (k, _) in enumerate(STAGES)}


class HmsVisit(models.Model):
    """One encounter (OPD visit, ER attendance or admission episode).

    The `stage` field is the Patient Journey Bar. It moves by itself as other departments
    act on the record, and it is shown at the top of every chart.
    """
    _name = "hms.visit"
    _description = "Patient Visit / Encounter"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "priority_rank, arrival_time"

    name = fields.Char(string="Visit No.", readonly=True, copy=False, default="New")
    patient_id = fields.Many2one("hms.patient", required=True, ondelete="restrict", index=True, tracking=True)
    mrn = fields.Char(related="patient_id.mrn", store=True)
    patient_age = fields.Integer(related="patient_id.age")
    patient_sex = fields.Selection(related="patient_id.sex")
    has_allergy = fields.Boolean(related="patient_id.has_allergy")
    allergy_summary = fields.Char(compute="_compute_allergy_summary")
    visit_type = fields.Selection([("opd", "OPD"), ("er", "Emergency"), ("ipd", "Admission"), ("followup", "Follow-up")], default="opd", required=True, tracking=True)
    department_id = fields.Many2one("hms.department", required=True, tracking=True)
    doctor_id = fields.Many2one("hms.practitioner", string="Doctor", domain="[('is_doctor', '=', True)]", tracking=True)
    referred_by = fields.Char()
    complaint = fields.Char(string="Presenting Complaint", required=True, tracking=True)
    arrival_time = fields.Datetime(default=fields.Datetime.now, required=True)
    appointment_time = fields.Datetime(string="Appointment")
    stage = fields.Selection(STAGES, default="registered", tracking=True, group_expand="_expand_stages")
    held = fields.Boolean(string="Held", compute="_compute_held", store=True, help="File locked: waiting on a payment or an approval.")
    hold_reason = fields.Char(compute="_compute_held", store=True)
    state = fields.Selection([("open", "Open"), ("closed", "Closed"), ("cancelled", "Cancelled")], default="open", tracking=True)
    # triage
    vitals_ids = fields.One2many("hms.vitals", "visit_id", string="Vitals")
    latest_vitals_id = fields.Many2one("hms.vitals", compute="_compute_latest_vitals_id")
    ews_score = fields.Integer(string="EWS", compute="_compute_ews", store=True, help="Early Warning Score from the latest vitals.")
    ews_level = fields.Selection([("low", "Low"), ("lowmed", "Low-Medium"), ("medium", "Medium"), ("high", "High")], compute="_compute_ews", store=True)
    priority_rank = fields.Integer(compute="_compute_ews", store=True, help="Queue ordering: sickest first, then longest wait.")
    waiting_minutes = fields.Integer(compute="_compute_waiting")
    # consult
    consult_ids = fields.One2many("hms.consult", "visit_id", string="Consultations")
    consult_count = fields.Integer(compute="_compute_counts")
    active_consult_id = fields.Many2one("hms.consult", compute="_compute_counts")
    # orders
    order_ids = fields.One2many("hms.order", "visit_id", string="Orders")
    order_count = fields.Integer(compute="_compute_counts")
    pending_results = fields.Integer(compute="_compute_counts")
    unacked_results = fields.Integer(compute="_compute_counts")
    # consents
    consent_ids = fields.One2many("hms.consent", "visit_id", string="Consents")
    consents_complete = fields.Boolean(compute="_compute_consents")
    # money
    charge_ids = fields.One2many("hms.charge", "visit_id", string="Charges")
    discount_request_ids = fields.One2many("hms.discount.request", "visit_id", string="Discount Requests")
    approved_discount = fields.Float(compute="_compute_discount", store=True, string="Approved Discount %")
    discount_pending = fields.Boolean(compute="_compute_discount", store=True)
    invoice_ids = fields.One2many("account.move", "hms_visit_id", string="Bills")
    amount_charged = fields.Monetary(compute="_compute_money", currency_field="currency_id", compute_sudo=True)
    amount_paid = fields.Monetary(compute="_compute_money", currency_field="currency_id", compute_sudo=True)
    amount_due = fields.Monetary(compute="_compute_money", currency_field="currency_id", compute_sudo=True)
    billing_state = fields.Selection([("none", "Nothing Billed"), ("unbilled", "Charges Pending"), ("unpaid", "Unpaid"), ("partial", "Partially Paid"), ("paid", "Paid")], compute="_compute_billing_state", store=True, compute_sudo=True)
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    # admission
    admission_id = fields.Many2one("hms.admission", string="Admission", copy=False)
    # AI
    ai_summary = fields.Text(string="Chart Summary", readonly=True, help="Generated on demand — the story so far in five bullets.")
    ai_summary_at = fields.Datetime(readonly=True)
    notes = fields.Text(string="Front Desk Notes")
    color = fields.Integer(compute="_compute_color")

    # ------------------------------------------------------------- computes
    @api.model
    def _expand_stages(self, stages, domain, **kwargs):
        return [k for k, _ in STAGES]

    @api.depends("patient_id.allergy_ids", "patient_id.allergy_notes")
    def _compute_allergy_summary(self):
        for rec in self:
            p = rec.patient_id
            names = p.allergy_ids.mapped("name") + ([p.allergy_notes] if p.allergy_notes else [])
            rec.allergy_summary = ", ".join(names) if names else ""

    @api.depends("vitals_ids")
    def _compute_latest_vitals_id(self):
        for rec in self:
            rec.latest_vitals_id = rec.vitals_ids.sorted("create_date", reverse=True)[:1]

    @api.depends("vitals_ids.ews_score", "arrival_time", "visit_type")
    def _compute_ews(self):
        for rec in self:
            latest = rec.vitals_ids.sorted("create_date", reverse=True)[:1]
            score = latest.ews_score if latest else 0
            rec.ews_score = score
            rec.ews_level = "high" if score >= 7 else "medium" if score >= 5 else "lowmed" if score >= 3 else "low"
            # lower rank = seen first. ER always ahead; then EWS; then arrival handled by _order
            rec.priority_rank = (0 if rec.visit_type == "er" else 10) - score

    def _compute_waiting(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.waiting_minutes = int((now - rec.arrival_time).total_seconds() // 60) if rec.arrival_time and rec.state == "open" and rec.stage not in ("discharged",) else 0

    @api.depends("consult_ids", "order_ids.state")
    def _compute_counts(self):
        for rec in self:
            rec.consult_count = len(rec.consult_ids)
            rec.active_consult_id = rec.consult_ids.filtered(lambda c: c.state == "draft")[:1] or rec.consult_ids[:1]
            rec.order_count = len(rec.order_ids.filtered(lambda o: o.state != "cancelled"))
            rec.pending_results = len(rec.order_ids.filtered(lambda o: o.state in ("ordered", "collected", "resulted")))
            rec.unacked_results = len(rec.order_ids.filtered(lambda o: o.state == "verified"))

    @api.depends("consent_ids.state")
    def _compute_consents(self):
        for rec in self:
            rec.consents_complete = bool(rec.consent_ids) and all(c.state == "signed" for c in rec.consent_ids)

    @api.depends("discount_request_ids.state", "discount_request_ids.percent")
    def _compute_discount(self):
        for rec in self:
            approved = rec.discount_request_ids.filtered(lambda d: d.state == "approved")
            rec.approved_discount = max(approved.mapped("percent")) if approved else 0.0
            rec.discount_pending = any(d.state == "submitted" for d in rec.discount_request_ids)

    @api.depends("charge_ids.amount", "charge_ids.invoice_line_id", "approved_discount",
                 "invoice_ids.amount_total", "invoice_ids.amount_residual", "invoice_ids.state", "invoice_ids.payment_state")
    def _compute_money(self):
        for rec in self:
            invoices = rec.invoice_ids.filtered(lambda m: m.state == "posted")
            rec.amount_charged = sum(invoices.mapped("amount_total")) + sum(rec.charge_ids.filtered(lambda c: not c.invoice_line_id).mapped("amount"))
            rec.amount_due = sum(invoices.mapped("amount_residual")) + sum(rec.charge_ids.filtered(lambda c: not c.invoice_line_id).mapped("amount")) * (1 - rec.approved_discount / 100.0)
            rec.amount_paid = sum(invoices.mapped("amount_total")) - sum(invoices.mapped("amount_residual"))

    @api.depends("charge_ids.invoice_line_id", "invoice_ids.state", "invoice_ids.payment_state")
    def _compute_billing_state(self):
        for rec in self:
            invoices = rec.invoice_ids.filtered(lambda m: m.state == "posted")
            if not rec.charge_ids and not invoices:
                rec.billing_state = "none"
            elif rec.charge_ids.filtered(lambda c: not c.invoice_line_id):
                rec.billing_state = "unbilled"
            elif all(m.payment_state in ("paid", "in_payment", "reversed") for m in invoices):
                rec.billing_state = "paid"
            elif any(m.payment_state == "partial" for m in invoices):
                rec.billing_state = "partial"
            else:
                rec.billing_state = "unpaid"

    @api.depends("discount_pending", "billing_state", "state")
    def _compute_held(self):
        hold_unpaid = self.env["ir.config_parameter"].sudo().get_param("stratos_hms.hold_unpaid", "True") == "True"
        for rec in self:
            if rec.state != "open":
                rec.held, rec.hold_reason = False, False
            elif rec.discount_pending:
                rec.held, rec.hold_reason = True, "Approval pending"
            elif hold_unpaid and rec.billing_state in ("unbilled", "unpaid", "partial") and rec.stage == "registered":
                rec.held, rec.hold_reason = True, "Payment pending"
            else:
                rec.held, rec.hold_reason = False, False

    def _compute_color(self):
        for rec in self:
            rec.color = 1 if rec.held else (2 if rec.ews_level == "high" else 0)

    # ------------------------------------------------------------- crud
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("hms.visit") or "New"
        visits = super().create(vals_list)
        for v in visits:
            v._post_consult_charge()
            v._create_default_consents()
        return visits

    def _post_consult_charge(self):
        """Registration posts the consultation fee as a charge; billing is deliberately separate from the clinical form."""
        for rec in self:
            if rec.visit_type == "ipd":
                continue
            fee = rec.doctor_id.consult_fee or rec.department_id.consult_fee or 0.0
            product = rec.department_id.consult_product_id or self.env.ref("stratos_hms.product_consult_fee", raise_if_not_found=False)
            if not product:
                product = self.env["product.product"].sudo().create({"name": "OPD Consultation", "type": "service", "list_price": fee})
            reg_product = self.env.ref("stratos_hms.product_registration_fee", raise_if_not_found=False)
            reg_fee = float(self.env["ir.config_parameter"].sudo().get_param("stratos_hms.registration_fee", "200") or 0)
            Charge = self.env["hms.charge"]
            if reg_product and reg_fee and not rec.patient_id.visit_ids.filtered(lambda v: v.id != rec.id):
                Charge.create({"visit_id": rec.id, "product_id": reg_product.id, "description": "Registration", "quantity": 1, "price_unit": reg_fee, "source": "registration"})
            Charge.create({"visit_id": rec.id, "product_id": product.id, "description": f"{rec.department_id.name} consultation — {rec.doctor_id.display_name or ''}", "quantity": 1, "price_unit": fee, "source": "consult"})

    def _create_default_consents(self):
        Consent = self.env["hms.consent"]
        for rec in self:
            for kind in ("billing", "allergy", "treatment"):
                Consent.create({"visit_id": rec.id, "kind": kind})

    # ------------------------------------------------------------- journey
    def _advance_stage(self, stage):
        """Move forward only — a later department's action never drags the bar backwards."""
        for rec in self:
            if rec.state == "open" and STAGE_RANK.get(stage, 0) > STAGE_RANK.get(rec.stage, 0):
                rec.stage = stage

    def action_check_in(self):
        for rec in self:
            rec.stage = "registered"
            rec.arrival_time = fields.Datetime.now()

    def action_take_vitals(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "res_model": "hms.vitals", "view_mode": "form", "target": "new",
            "context": {"default_visit_id": self.id, "default_patient_id": self.patient_id.id},
        }

    def action_start_consult(self):
        """One click from the queue and the consultation opens with the patient's full chart one tab away."""
        self.ensure_one()
        if self.held:
            raise UserError(_("This file is held (%s). Clear it at the front desk before starting the consultation.") % self.hold_reason)
        consult = self.consult_ids.filtered(lambda c: c.state == "draft")[:1]
        if not consult:
            doctor = self.env["hms.practitioner"].get_current()
            consult = self.env["hms.consult"].create({
                "visit_id": self.id,
                "doctor_id": (doctor if doctor.is_doctor else self.doctor_id).id or self.doctor_id.id,
            })
        self._advance_stage("consult")
        return {
            "type": "ir.actions.act_window", "res_model": "hms.consult", "res_id": consult.id,
            "view_mode": "form", "target": "current",
        }

    def action_open_chart(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "hms.visit", "res_id": self.id, "view_mode": "form", "target": "current"}

    def action_discharge(self):
        for rec in self:
            if rec.admission_id and rec.admission_id.state == "admitted":
                raise UserError(_("Discharge the admission from the ward first."))
            rec.stage = "discharged"
            rec.state = "closed"

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_ai_summary(self):
        """Medica-style chart summary: the story so far, in five bullets, on demand."""
        for rec in self:
            text = self.env["hms.ai.service"].summarize_visit(rec)
            rec.write({"ai_summary": text, "ai_summary_at": fields.Datetime.now()})
        return True

    # ------------------------------------------------------------- billing shortcuts
    def action_create_bill(self):
        self.ensure_one()
        return self.env["hms.charge"].create_invoice_for_visit(self)

    def action_register_payment(self):
        self.ensure_one()
        inv = self.invoice_ids.filtered(lambda m: m.state == "posted" and m.payment_state not in ("paid", "in_payment"))
        if not inv:
            inv = self.action_create_bill()
            inv = self.invoice_ids.filtered(lambda m: m.state == "posted" and m.payment_state not in ("paid", "in_payment"))
        if not inv:
            raise UserError(_("Nothing to collect on this visit."))
        return {
            "type": "ir.actions.act_window", "res_model": "account.payment.register", "view_mode": "form", "target": "new",
            "context": {"active_model": "account.move", "active_ids": inv.ids, "default_amount": sum(inv.mapped("amount_residual"))},
        }

    def action_request_discount(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "res_model": "hms.discount.request", "view_mode": "form", "target": "new",
            "context": {"default_visit_id": self.id},
        }

    def action_whatsapp_bill(self):
        self.ensure_one()
        inv = self.invoice_ids.filtered(lambda m: m.state == "posted")[:1]
        msg = _("Assalam o Alaikum %s, your bill %s from %s: total PKR %s, paid PKR %s, outstanding PKR %s. Thank you.") % (
            self.patient_id.name, inv.name if inv else self.name, self.env.company.name,
            f"{self.amount_charged:,.0f}", f"{self.amount_paid:,.0f}", f"{self.amount_due:,.0f}")
        return self.env["hms.whatsapp"].link_action(self.patient_id.whatsapp or self.patient_id.phone, msg)

    def action_view_bills(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": "Bills", "res_model": "account.move", "view_mode": "list,form",
            "domain": [("hms_visit_id", "=", self.id)], "context": {"default_move_type": "out_invoice"},
        }

    def action_admit(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "res_model": "hms.admission", "view_mode": "form", "target": "new",
            "context": {"default_visit_id": self.id, "default_patient_id": self.patient_id.id, "default_doctor_id": self.doctor_id.id, "default_department_id": self.department_id.id},
        }

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.name} · {rec.patient_id.name}"


class HmsVitals(models.Model):
    """Vitals once. Abnormal values flag themselves; the Early Warning Score (NEWS2-style)
    computes as they are typed and re-orders every doctor's queue."""
    _name = "hms.vitals"
    _description = "Vital Signs"
    _order = "create_date desc"

    visit_id = fields.Many2one("hms.visit", required=True, ondelete="cascade", index=True)
    patient_id = fields.Many2one("hms.patient", related="visit_id.patient_id", store=True)
    admission_id = fields.Many2one("hms.admission", ondelete="set null")
    nurse_id = fields.Many2one("hms.practitioner", default=lambda self: self.env["hms.practitioner"].get_current())
    taken_at = fields.Datetime(default=fields.Datetime.now)
    bp_sys = fields.Integer(string="BP Systolic")
    bp_dia = fields.Integer(string="BP Diastolic")
    heart_rate = fields.Integer(string="Heart Rate")
    resp_rate = fields.Integer(string="Resp. Rate")
    temperature = fields.Float(string="Temperature °C", digits=(4, 1))
    spo2 = fields.Integer(string="SpO₂ %")
    on_oxygen = fields.Boolean(string="On Supplemental O₂")
    consciousness = fields.Selection([("alert", "Alert"), ("voice", "Responds to Voice"), ("pain", "Responds to Pain"), ("unresponsive", "Unresponsive"), ("confused", "New Confusion")], default="alert")
    weight = fields.Float(string="Weight (kg)", digits=(5, 1))
    height = fields.Float(string="Height (cm)", digits=(5, 1))
    bmi = fields.Float(compute="_compute_bmi", store=True, digits=(4, 1))
    blood_sugar = fields.Float(string="Blood Sugar (mg/dL)")
    pain_score = fields.Integer(string="Pain (0-10)")
    nurse_note = fields.Char()
    ews_score = fields.Integer(string="EWS", compute="_compute_ews", store=True)
    ews_breakdown = fields.Char(compute="_compute_ews", store=True)
    flags = fields.Char(compute="_compute_ews", store=True, help="Comma-separated abnormal parameters.")
    send_to_doctor_id = fields.Many2one("hms.practitioner", string="Send to Doctor", domain="[('is_doctor','=',True)]")

    @api.depends("weight", "height")
    def _compute_bmi(self):
        for rec in self:
            rec.bmi = rec.weight / ((rec.height / 100) ** 2) if rec.weight and rec.height else 0.0

    @api.depends("bp_sys", "heart_rate", "resp_rate", "temperature", "spo2", "on_oxygen", "consciousness")
    def _compute_ews(self):
        for rec in self:
            score, parts, flags = 0, [], []

            def add(label, pts, flag_when=True):
                nonlocal score
                if pts:
                    score += pts
                    parts.append(f"{label}+{pts}")
                    if flag_when:
                        flags.append(label)

            rr = rec.resp_rate
            if rr:
                add("RR", 3 if rr <= 8 else 1 if rr <= 11 else 0 if rr <= 20 else 2 if rr <= 24 else 3)
            s = rec.spo2
            if s:
                add("SpO2", 3 if s <= 91 else 2 if s <= 93 else 1 if s <= 95 else 0)
            if rec.on_oxygen:
                add("O2", 2, flag_when=False)
            t = rec.temperature
            if t:
                add("Temp", 3 if t <= 35.0 else 1 if t <= 36.0 else 0 if t <= 38.0 else 1 if t <= 39.0 else 2)
            bp = rec.bp_sys
            if bp:
                add("BP", 3 if bp <= 90 else 2 if bp <= 100 else 1 if bp <= 110 else 0 if bp <= 219 else 3)
                if bp >= 140 and not (bp <= 110):
                    flags.append("BP")
            hr = rec.heart_rate
            if hr:
                add("HR", 3 if hr <= 40 else 1 if hr <= 50 else 0 if hr <= 90 else 1 if hr <= 110 else 2 if hr <= 130 else 3)
            if rec.consciousness and rec.consciousness != "alert":
                add("AVPU", 3)
            rec.ews_score = score
            rec.ews_breakdown = " ".join(parts)
            rec.flags = ", ".join(dict.fromkeys(flags))

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            rec.visit_id._advance_stage("triaged")
            if rec.send_to_doctor_id:
                rec.visit_id.doctor_id = rec.send_to_doctor_id
            rec.visit_id.message_post(body=_("Vitals recorded by %s — EWS %s (%s)%s") % (
                rec.nurse_id.display_name or "nurse", rec.ews_score, rec.ews_breakdown or "no points",
                f"; flagged: {rec.flags}" if rec.flags else ""))
        return recs

    def as_text(self):
        self.ensure_one()
        bits = []
        if self.bp_sys:
            bits.append(f"BP {self.bp_sys}/{self.bp_dia}")
        if self.heart_rate:
            bits.append(f"HR {self.heart_rate}")
        if self.resp_rate:
            bits.append(f"RR {self.resp_rate}")
        if self.temperature:
            bits.append(f"Temp {self.temperature}°C")
        if self.spo2:
            bits.append(f"SpO2 {self.spo2}%")
        if self.weight:
            bits.append(f"Wt {self.weight} kg")
        if self.blood_sugar:
            bits.append(f"BSR {self.blood_sugar}")
        bits.append(f"EWS {self.ews_score}")
        return " · ".join(bits)


class HmsConsent(models.Model):
    """Consent captured at the front desk before care begins — signed on screen, stamped with who took it and when."""
    _name = "hms.consent"
    _description = "Patient Consent"
    _order = "id"

    visit_id = fields.Many2one("hms.visit", required=True, ondelete="cascade")
    patient_id = fields.Many2one(related="visit_id.patient_id", store=True)
    kind = fields.Selection([
        ("billing", "Billing & financial responsibility"),
        ("allergy", "Allergy declaration & treatment acknowledgement"),
        ("treatment", "Consent to examination & treatment"),
        ("insurance", "Insurance / cashless authorisation"),
        ("recording", "Consent to consultation recording (AI scribe)"),
        ("surgery", "Surgical / anaesthesia consent"),
        ("blood", "Blood transfusion consent"),
    ], required=True)
    text = fields.Text(compute="_compute_text", store=True, readonly=False)
    state = fields.Selection([("pending", "Not Signed"), ("signed", "Signed"), ("declined", "Declined")], default="pending")
    signature = fields.Binary(attachment=True)
    signed_by_name = fields.Char(string="Signed By (name)")
    signed_on_behalf = fields.Boolean(string="Signed on behalf of patient")
    taken_by_id = fields.Many2one("hms.practitioner", string="Recorded By")
    signed_at = fields.Datetime()

    CONSENT_TEXT = {
        "billing": "I understand that I (the patient or financially responsible party) am responsible for payment of all hospital charges, including any amount not paid by an insurer or panel.",
        "allergy": "I have declared all known allergies to the hospital staff. I acknowledge that treatment will be based on the information I have provided.",
        "treatment": "I consent to examination, investigations and treatment as deemed necessary by the attending physician, and understand I may withdraw consent at any time.",
        "insurance": "I authorise the hospital to bill my insurer or panel directly and to share the medical records required for the claim.",
        "recording": "I consent to the audio of my consultation being transcribed to assist the doctor in writing the medical record. The doctor reviews and signs every note; I may ask for the recording to be switched off at any time.",
        "surgery": "The nature, benefits, risks and alternatives of the proposed procedure and anaesthesia have been explained to me and I consent to it.",
        "blood": "The benefits and risks of blood transfusion have been explained to me and I consent to receive blood or blood products.",
    }

    @api.depends("kind")
    def _compute_text(self):
        for rec in self:
            if not rec.text:
                rec.text = self.CONSENT_TEXT.get(rec.kind, "")

    def action_sign(self):
        for rec in self:
            if not rec.signature:
                raise ValidationError(_("Ask the patient to sign on the screen first."))
            rec.write({
                "state": "signed", "signed_at": fields.Datetime.now(),
                "taken_by_id": self.env["hms.practitioner"].get_current().id,
                "signed_by_name": rec.signed_by_name or rec.patient_id.name,
            })
            rec.visit_id.message_post(body=_("Consent signed: %s (recorded by %s)") % (dict(self._fields["kind"].selection)[rec.kind], rec.taken_by_id.display_name))

    def action_decline(self):
        self.write({"state": "declined"})


class HmsDiscountRequest(models.Model):
    """A discount is a request, not a favour. The desk cannot grant it; the HOD approves by name."""
    _name = "hms.discount.request"
    _description = "Discount Request"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    visit_id = fields.Many2one("hms.visit", required=True, ondelete="cascade")
    patient_id = fields.Many2one(related="visit_id.patient_id", store=True)
    percent = fields.Float(string="Discount %", required=True)
    reason = fields.Selection([
        ("hardship", "Financial hardship / Zakat"), ("staff", "Staff / family"), ("panel", "Panel / corporate rate"),
        ("goodwill", "Goodwill / service recovery"), ("senior", "Senior citizen"), ("other", "Other"),
    ], required=True, default="hardship")
    reason_note = fields.Char(string="Details")
    requested_by_id = fields.Many2one("hms.practitioner", default=lambda self: self.env["hms.practitioner"].get_current(), readonly=True)
    approver_id = fields.Many2one("hms.practitioner", string="Decided By", readonly=True)
    decided_at = fields.Datetime(readonly=True)
    state = fields.Selection([("submitted", "Approval Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="submitted", tracking=True)
    amount_before = fields.Monetary(compute="_compute_amounts", currency_field="currency_id")
    amount_after = fields.Monetary(compute="_compute_amounts", currency_field="currency_id")
    currency_id = fields.Many2one(related="visit_id.currency_id")
    decision_note = fields.Char()

    @api.depends("visit_id.charge_ids.amount", "percent")
    def _compute_amounts(self):
        for rec in self:
            total = sum(rec.visit_id.charge_ids.filtered(lambda c: not c.invoice_line_id).mapped("amount")) or rec.visit_id.amount_charged
            rec.amount_before = total
            rec.amount_after = total * (1 - rec.percent / 100.0)

    @api.constrains("percent")
    def _check_percent(self):
        for rec in self:
            if not 0 < rec.percent <= 100:
                raise ValidationError(_("Discount must be between 0 and 100%."))

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            rec.visit_id.message_post(body=_("Discount of %s%% requested (%s) by %s — file held, approval pending.") % (rec.percent, dict(self._fields['reason'].selection)[rec.reason], rec.requested_by_id.display_name))
        return recs

    def action_approve(self):
        if not self.env.user.has_group("stratos_hms.group_hms_hod"):
            raise UserError(_("Only a Head of Department or Director can approve a discount."))
        me = self.env["hms.practitioner"].get_current()
        for rec in self:
            rec.write({"state": "approved", "approver_id": me.id, "decided_at": fields.Datetime.now()})
            rec.visit_id.message_post(body=_("Discount %s%% APPROVED by %s.") % (rec.percent, me.display_name or self.env.user.name))

    def action_reject(self):
        if not self.env.user.has_group("stratos_hms.group_hms_hod"):
            raise UserError(_("Only a Head of Department or Director can decide a discount."))
        me = self.env["hms.practitioner"].get_current()
        for rec in self:
            rec.write({"state": "rejected", "approver_id": me.id, "decided_at": fields.Datetime.now()})
            rec.visit_id.message_post(body=_("Discount %s%% rejected by %s.") % (rec.percent, me.display_name or self.env.user.name))
