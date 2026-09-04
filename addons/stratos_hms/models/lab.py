from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class HmsTest(models.Model):
    """Diagnostic catalogue: laboratory tests, imaging studies and procedures."""
    _name = "hms.test"
    _description = "Diagnostic Test / Study"
    _order = "category, name"
    _rec_names_search = ["name", "code"]

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    category = fields.Selection([("lab", "Laboratory"), ("imaging", "Imaging"), ("procedure", "Procedure")], default="lab", required=True)
    section = fields.Char(help="e.g. Haematology, Biochemistry, Microbiology, X-Ray, CT, Ultrasound")
    sample_type = fields.Char(help="e.g. Blood (EDTA), Serum, Urine")
    unit = fields.Char()
    ref_low = fields.Float(string="Reference Low")
    ref_high = fields.Float(string="Reference High")
    ref_text = fields.Char(string="Reference (text)", help="For qualitative results, e.g. 'Negative'")
    critical_low = fields.Float()
    critical_high = fields.Float()
    numeric = fields.Boolean(default=True, help="Untick for qualitative / narrative results (ECG, X-ray report).")
    tat_minutes = fields.Integer(string="Target TAT (min)", default=120)
    price = fields.Float(string="Price (PKR)")
    product_id = fields.Many2one("product.product", ondelete="set null")
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint("unique(code)", "Test code must be unique.")

    def get_or_create_product(self):
        self.ensure_one()
        if not self.product_id:
            self.sudo().product_id = self.env["product.product"].sudo().create({
                "name": self.name, "type": "service", "list_price": self.price or 0.0, "sale_ok": True, "purchase_ok": False,
                "default_code": f"TEST-{self.code}",
            })
        return self.product_id


class HmsOrder(models.Model):
    """A diagnostic order. Lifecycle: ordered → collected → resulted → verified → acknowledged.

    Safety loops:
    * Collection is a gate — the wristband (MRN) and the specimen barcode must both match.
    * A critical flag opens a call-log entry that stays red until the doctor is personally
      informed (read-back recorded), and the result stays in the doctor's inbox until acknowledged.
    """
    _name = "hms.order"
    _description = "Diagnostic Order"
    _inherit = ["mail.thread"]
    _order = "urgency_rank, create_date"

    name = fields.Char(string="Order No.", readonly=True, copy=False, default="New")
    visit_id = fields.Many2one("hms.visit", required=True, ondelete="cascade", index=True)
    patient_id = fields.Many2one(related="visit_id.patient_id", store=True)
    consult_id = fields.Many2one("hms.consult", ondelete="set null")
    admission_id = fields.Many2one("hms.admission", ondelete="set null")
    test_id = fields.Many2one("hms.test", required=True)
    category = fields.Selection(related="test_id.category", store=True)
    ordered_by_id = fields.Many2one("hms.practitioner", string="Ordered By")
    urgency = fields.Selection([("routine", "Routine"), ("urgent", "Urgent"), ("stat", "STAT")], default="routine", required=True, tracking=True)
    urgency_rank = fields.Integer(compute="_compute_urgency_rank", store=True)
    reason = fields.Char(help="Clinical reason — attached by the doctor or the AI proposal.")
    ai_suggested = fields.Boolean(string="AI Proposed", readonly=True)
    state = fields.Selection(
        [("proposed", "Proposed"), ("ordered", "Ordered"), ("collected", "Sample Collected"), ("resulted", "Resulted"),
         ("verified", "Verified & Released"), ("acknowledged", "Acknowledged"), ("cancelled", "Cancelled")],
        default="ordered", tracking=True,
    )
    # sample tracking
    specimen_barcode = fields.Char(readonly=True, copy=False)
    scanned_band = fields.Char(string="Scanned Wristband (MRN)")
    scanned_specimen = fields.Char(string="Scanned Specimen")
    collected_by_id = fields.Many2one("hms.practitioner")
    collected_at = fields.Datetime()
    # result
    result_value = fields.Char()
    result_numeric = fields.Float(compute="_compute_result_numeric", store=True)
    result_text = fields.Text(string="Report / Narrative")
    result_file = fields.Binary(string="Report PDF / Image", attachment=True)
    result_filename = fields.Char()
    flag = fields.Selection([("normal", "Normal"), ("low", "Low"), ("high", "High"), ("abnormal", "Abnormal"), ("critical", "CRITICAL")], tracking=True)
    resulted_by_id = fields.Many2one("hms.practitioner")
    resulted_at = fields.Datetime()
    verified_by_id = fields.Many2one("hms.practitioner")
    verified_at = fields.Datetime()
    acknowledged_by_id = fields.Many2one("hms.practitioner")
    acknowledged_at = fields.Datetime()
    tat_minutes = fields.Integer(string="Turnaround (min)", compute="_compute_tat", store=True)
    tat_breached = fields.Boolean(compute="_compute_tat", store=True)
    # critical value loop
    critical_call_ids = fields.One2many("hms.critical.call", "order_id", string="Critical Calls")
    critical_pending = fields.Boolean(compute="_compute_critical_pending", store=True)
    charge_id = fields.Many2one("hms.charge", readonly=True, copy=False)
    doctor_id = fields.Many2one(related="visit_id.doctor_id", store=True, string="Attending Doctor")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.depends("urgency")
    def _compute_urgency_rank(self):
        rank = {"stat": 0, "urgent": 1, "routine": 2}
        for rec in self:
            rec.urgency_rank = rank.get(rec.urgency, 2)

    @api.depends("result_value")
    def _compute_result_numeric(self):
        for rec in self:
            try:
                rec.result_numeric = float((rec.result_value or "").replace(",", ""))
            except ValueError:
                rec.result_numeric = 0.0

    @api.depends("verified_at", "create_date", "state")
    def _compute_tat(self):
        now = fields.Datetime.now()
        for rec in self:
            start = rec.create_date or now
            end = rec.verified_at if rec.verified_at else now
            rec.tat_minutes = int((end - start).total_seconds() // 60)
            rec.tat_breached = rec.state in ("ordered", "collected", "resulted") and rec.tat_minutes > (rec.test_id.tat_minutes or 120)

    @api.depends("critical_call_ids.state", "flag")
    def _compute_critical_pending(self):
        for rec in self:
            rec.critical_pending = rec.flag == "critical" and any(c.state != "done" for c in rec.critical_call_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("hms.order") or "New"
            vals.setdefault("specimen_barcode", "SPC-" + (self.env["ir.sequence"].next_by_code("hms.specimen") or "0"))
        orders = super().create(vals_list)
        for o in orders.filtered(lambda o: o.state == "ordered"):
            o._post_charge()
        return orders

    def _post_charge(self):
        """Approving an order posts its bill line — no test is done but never billed."""
        for rec in self.filtered(lambda r: not r.charge_id and r.state != "proposed"):
            rec.charge_id = self.env["hms.charge"].create({
                "visit_id": rec.visit_id.id,
                "product_id": rec.test_id.get_or_create_product().id,
                "description": f"{rec.test_id.name} ({rec.urgency.upper()})",
                "quantity": 1,
                "price_unit": rec.test_id.price,
                "source": "order",
                "order_id": rec.id,
            })

    # ---------------------------------------------------------------- actions
    def action_approve(self):
        for rec in self.filtered(lambda r: r.state == "proposed"):
            rec.state = "ordered"
            rec._post_charge()
            rec.visit_id._advance_stage("orders")

    def action_reject(self):
        self.filtered(lambda r: r.state == "proposed").write({"state": "cancelled"})

    def action_collect(self):
        """Scan-verified collection: wristband must equal the patient's MRN and the specimen
        barcode must equal the order's label. Otherwise the system will not proceed."""
        for rec in self:
            if rec.state != "ordered":
                raise UserError(_("Order %s is not awaiting collection.") % rec.name)
            band = (rec.scanned_band or "").strip().upper()
            spec = (rec.scanned_specimen or "").strip().upper()
            if band != (rec.patient_id.mrn or "").upper():
                raise UserError(_("Wristband mismatch. Scanned '%s' but this order belongs to %s. Collection blocked.") % (rec.scanned_band, rec.patient_id.display_name))
            if spec != (rec.specimen_barcode or "").upper():
                raise UserError(_("Specimen barcode mismatch. Expected %s. Collection blocked.") % rec.specimen_barcode)
            rec.write({
                "state": "collected", "collected_at": fields.Datetime.now(),
                "collected_by_id": self.env["hms.practitioner"].get_current().id,
            })
            rec.message_post(body=_("Specimen %s collected & labelled (closed loop: band + tube verified).") % rec.specimen_barcode)

    def _auto_flag(self):
        self.ensure_one()
        t = self.test_id
        if not t.numeric or not self.result_value:
            return self.flag or "normal"
        v = self.result_numeric
        if t.critical_high and v >= t.critical_high:
            return "critical"
        if t.critical_low and v <= t.critical_low:
            return "critical"
        if t.ref_high and v > t.ref_high:
            return "high"
        if t.ref_low and v < t.ref_low:
            return "low"
        return "normal"

    def action_enter_result(self):
        for rec in self:
            if rec.state not in ("collected", "ordered"):
                raise UserError(_("Result can only be entered on a collected order."))
            if not rec.result_value and not rec.result_text and not rec.result_file:
                raise UserError(_("Enter a value, a narrative report or attach a report first."))
            rec.write({
                "state": "resulted", "resulted_at": fields.Datetime.now(),
                "resulted_by_id": self.env["hms.practitioner"].get_current().id,
                "flag": rec.flag or rec._auto_flag(),
            })

    def action_verify_release(self):
        for rec in self:
            if rec.state != "resulted":
                raise UserError(_("Only resulted orders can be verified."))
            flag = rec.flag or rec._auto_flag()
            rec.write({
                "state": "verified", "verified_at": fields.Datetime.now(), "flag": flag,
                "verified_by_id": self.env["hms.practitioner"].get_current().id,
            })
            rec.visit_id._advance_stage("results")
            if flag == "critical" and not rec.critical_call_ids:
                self.env["hms.critical.call"].create({"order_id": rec.id, "doctor_id": rec.doctor_id.id})
            rec.message_post(body=_("Result released: %s %s (%s)") % (rec.result_value or "report", rec.test_id.unit or "", flag or ""))

    def action_acknowledge(self):
        for rec in self:
            if rec.state != "verified":
                raise UserError(_("Only released results can be acknowledged."))
            if rec.critical_pending:
                raise UserError(_("A critical value must be phoned to the doctor and logged before it can be acknowledged."))
            rec.write({
                "state": "acknowledged", "acknowledged_at": fields.Datetime.now(),
                "acknowledged_by_id": self.env["hms.practitioner"].get_current().id,
            })

    def action_cancel(self):
        for rec in self:
            if rec.state in ("verified", "acknowledged"):
                raise UserError(_("Released results cannot be cancelled."))
            rec.state = "cancelled"
            if rec.charge_id and not rec.charge_id.invoice_line_id:
                rec.charge_id.unlink()


class HmsCriticalCall(models.Model):
    """A critical value is never allowed to just sit in a table."""
    _name = "hms.critical.call"
    _description = "Critical Value Call Log"
    _order = "create_date desc"

    order_id = fields.Many2one("hms.order", required=True, ondelete="cascade")
    patient_id = fields.Many2one(related="order_id.patient_id", store=True)
    test_name = fields.Char(related="order_id.test_id.name")
    value = fields.Char(related="order_id.result_value")
    doctor_id = fields.Many2one("hms.practitioner", string="Doctor to Notify")
    state = fields.Selection([("pending", "Pending Call"), ("done", "Doctor Notified")], default="pending")
    called_by_id = fields.Many2one("hms.practitioner")
    called_at = fields.Datetime()
    read_back = fields.Boolean(string="Value Read Back & Confirmed")
    spoke_to = fields.Char(string="Spoke To")
    notes = fields.Char()

    def action_log_call(self):
        for rec in self:
            if not rec.read_back:
                raise ValidationError(_("Tick 'Value read back & confirmed' — the read-back is mandatory for a critical value."))
            rec.write({
                "state": "done", "called_at": fields.Datetime.now(),
                "called_by_id": self.env["hms.practitioner"].get_current().id,
            })
            rec.order_id.message_post(body=_("CRITICAL VALUE phoned to %s by %s; read back confirmed.") % (rec.spoke_to or rec.doctor_id.display_name, rec.called_by_id.display_name))
