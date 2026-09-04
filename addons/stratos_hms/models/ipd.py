from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .drug import ROUTES, FREQUENCIES, FREQ_PER_DAY


class HmsWard(models.Model):
    _name = "hms.ward"
    _description = "Ward"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    department_id = fields.Many2one("hms.department")
    ward_type = fields.Selection([("general", "General"), ("private", "Private"), ("icu", "ICU / CCU"), ("hdu", "HDU"), ("maternity", "Maternity"), ("paeds", "Paediatric")], default="general")
    bed_ids = fields.One2many("hms.bed", "ward_id", string="Beds")
    bed_count = fields.Integer(compute="_compute_occupancy")
    occupied_count = fields.Integer(compute="_compute_occupancy")
    occupancy_pct = fields.Float(compute="_compute_occupancy")
    daily_rate = fields.Float(string="Bed Charge / Day (PKR)")
    product_id = fields.Many2one("product.product")

    def _compute_occupancy(self):
        for rec in self:
            rec.bed_count = len(rec.bed_ids)
            rec.occupied_count = len(rec.bed_ids.filtered(lambda b: b.state == "occupied"))
            rec.occupancy_pct = (rec.occupied_count / rec.bed_count * 100) if rec.bed_count else 0.0

    def get_or_create_product(self):
        self.ensure_one()
        if not self.product_id:
            self.sudo().product_id = self.env["product.product"].sudo().create({"name": f"Bed charge — {self.name}", "type": "service", "list_price": self.daily_rate})
        return self.product_id


class HmsBed(models.Model):
    _name = "hms.bed"
    _description = "Bed"
    _order = "ward_id, name"

    name = fields.Char(required=True)
    ward_id = fields.Many2one("hms.ward", required=True, ondelete="cascade")
    state = fields.Selection([("free", "Free"), ("occupied", "Occupied"), ("cleaning", "Cleaning"), ("blocked", "Out of Service")], default="free")
    admission_id = fields.Many2one("hms.admission", string="Current Admission", readonly=True)
    patient_id = fields.Many2one(related="admission_id.patient_id")
    color = fields.Integer(compute="_compute_color")

    def _compute_color(self):
        m = {"free": 10, "occupied": 1, "cleaning": 3, "blocked": 8}
        for rec in self:
            rec.color = m.get(rec.state, 0)

    def action_mark_clean(self):
        self.filtered(lambda b: b.state == "cleaning").write({"state": "free"})

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.ward_id.code}-{rec.name}"


class HmsAdmission(models.Model):
    """Inpatient episode: bed, rounds, ward orders, MAR and handoffs, all on the same chart."""
    _name = "hms.admission"
    _description = "Admission"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "admitted_at desc"

    name = fields.Char(readonly=True, copy=False, default="New")
    visit_id = fields.Many2one("hms.visit", required=True, ondelete="restrict")
    patient_id = fields.Many2one("hms.patient", required=True)
    has_allergy = fields.Boolean(related="patient_id.has_allergy")
    allergy_summary = fields.Char(related="visit_id.allergy_summary")
    doctor_id = fields.Many2one("hms.practitioner", string="Admitting Doctor", domain="[('is_doctor','=',True)]", required=True)
    department_id = fields.Many2one("hms.department", required=True)
    ward_id = fields.Many2one("hms.ward", required=True)
    bed_id = fields.Many2one("hms.bed", domain="[('ward_id','=',ward_id),('state','=','free')]", required=True)
    diagnosis = fields.Char(required=True)
    admitted_at = fields.Datetime(default=fields.Datetime.now)
    discharged_at = fields.Datetime(readonly=True)
    length_of_stay = fields.Integer(compute="_compute_los", string="LOS (days)")
    state = fields.Selection([("admitted", "Admitted"), ("discharged", "Discharged")], default="admitted", tracking=True)
    ews_score = fields.Integer(related="visit_id.ews_score")
    vitals_ids = fields.One2many("hms.vitals", "admission_id")
    ward_order_ids = fields.One2many("hms.ward.order", "admission_id", string="Ward Orders")
    mar_ids = fields.One2many("hms.mar", "admission_id", string="MAR")
    mar_due_count = fields.Integer(compute="_compute_mar_counts")
    order_ids = fields.One2many("hms.order", "admission_id", string="Investigations")
    progress_note_ids = fields.One2many("hms.progress.note", "admission_id")
    handoff_ids = fields.One2many("hms.handoff", "admission_id")
    surgery_ids = fields.One2many("hms.surgery", "admission_id")
    discharge_summary = fields.Html(readonly=True)
    amount_due = fields.Monetary(related="visit_id.amount_due")
    currency_id = fields.Many2one(related="visit_id.currency_id")
    escalation_note = fields.Char(string="Escalation Thresholds", default="Call doctor if EWS ≥ 5, SBP < 90, SpO₂ < 92, chest pain or new confusion. EWS ≥ 7 → rapid response.")

    @api.depends("admitted_at", "discharged_at")
    def _compute_los(self):
        for rec in self:
            end = rec.discharged_at or fields.Datetime.now()
            rec.length_of_stay = max(1, (end - rec.admitted_at).days + 1) if rec.admitted_at else 0

    def _compute_mar_counts(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.mar_due_count = len(rec.mar_ids.filtered(lambda m: m.state == "due" and m.scheduled_at <= now + timedelta(hours=1)))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("hms.admission") or "New"
        recs = super().create(vals_list)
        for rec in recs:
            if rec.bed_id.state != "free":
                raise ValidationError(_("Bed %s is not free.") % rec.bed_id.display_name)
            rec.bed_id.sudo().write({"state": "occupied", "admission_id": rec.id})
            rec.visit_id.write({"admission_id": rec.id, "visit_type": "ipd"})
            rec.visit_id._advance_stage("treatment")
            rec.visit_id.message_post(body=_("Admitted to %s under %s.") % (rec.bed_id.display_name, rec.doctor_id.display_name))
        return recs

    def action_discharge(self):
        Charge = self.env["hms.charge"]
        for rec in self:
            if rec.state != "admitted":
                continue
            rec.write({"state": "discharged", "discharged_at": fields.Datetime.now()})
            Charge.create({
                "visit_id": rec.visit_id.id, "product_id": rec.ward_id.get_or_create_product().id,
                "description": f"Bed charges {rec.ward_id.name} × {rec.length_of_stay} day(s)",
                "quantity": rec.length_of_stay, "price_unit": rec.ward_id.daily_rate, "source": "ward",
            })
            rec.bed_id.sudo().write({"state": "cleaning", "admission_id": False})
            rec.discharge_summary = self.env["hms.ai.service"].draft_discharge_summary(rec)
            rec.visit_id.write({"stage": "discharged", "state": "closed"})
        return True

    def action_draft_handoff(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "res_model": "hms.handoff", "view_mode": "form", "target": "new",
            "context": {"default_admission_id": self.id},
        }

    def action_print_discharge(self):
        return self.env.ref("stratos_hms.action_report_discharge").report_action(self)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.name} · {rec.patient_id.name} · {rec.bed_id.display_name}"


class HmsProgressNote(models.Model):
    _name = "hms.progress.note"
    _description = "Ward Round Progress Note"
    _order = "create_date desc"

    admission_id = fields.Many2one("hms.admission", required=True, ondelete="cascade")
    doctor_id = fields.Many2one("hms.practitioner", default=lambda self: self.env["hms.practitioner"].get_current())
    note = fields.Text(required=True)
    plan = fields.Char()


class HmsWardOrder(models.Model):
    """An order from rounds: priced the moment it is picked, on the nurse's board as soon as it is placed."""
    _name = "hms.ward.order"
    _description = "Ward Order"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    admission_id = fields.Many2one("hms.admission", required=True, ondelete="cascade")
    patient_id = fields.Many2one(related="admission_id.patient_id", store=True)
    visit_id = fields.Many2one(related="admission_id.visit_id", store=True)
    doctor_id = fields.Many2one("hms.practitioner", default=lambda self: self.env["hms.practitioner"].get_current())
    order_type = fields.Selection([("medication", "Medication"), ("iv_fluid", "IV Fluids"), ("procedure", "Procedure"), ("nursing", "Nursing Instruction"), ("diet", "Diet")], default="medication", required=True)
    drug_id = fields.Many2one("hms.drug")
    dose = fields.Char()
    route = fields.Selection(ROUTES, default="po")
    frequency = fields.Selection(FREQUENCIES, default="bd")
    duration_days = fields.Integer(default=3)
    prn = fields.Boolean(string="PRN (as needed)")
    instruction = fields.Char()
    price_unit = fields.Float(compute="_compute_price", store=True, readonly=False, string="Unit Charge (PKR)")
    state = fields.Selection([("active", "Active"), ("stopped", "Stopped"), ("completed", "Completed")], default="active", tracking=True)
    mar_ids = fields.One2many("hms.mar", "ward_order_id")
    warning = fields.Char(compute="_compute_warning")

    @api.depends("drug_id")
    def _compute_price(self):
        for rec in self:
            rec.price_unit = rec.drug_id.price if rec.drug_id else rec.price_unit

    def _compute_warning(self):
        for rec in self:
            w = rec.drug_id.check_against_patient(rec.patient_id) if rec.drug_id and rec.patient_id else []
            rec.warning = w[0] if w else False

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            if rec.order_type in ("medication", "iv_fluid") and rec.drug_id:
                w = rec.drug_id.check_against_patient(rec.patient_id)
                if w:
                    raise UserError(w[0] + _("\nOrder blocked. Choose another medicine or document an allergy override on the chart."))
                rec._generate_mar()
            rec.admission_id.message_post(body=_("Ward order placed by %s: %s") % (rec.doctor_id.display_name, rec.display_name))
        return recs

    def _generate_mar(self):
        """Scheduled doses: one MAR row per due time for the whole course."""
        Mar = self.env["hms.mar"]
        for rec in self:
            if rec.prn or rec.frequency in ("prn",):
                continue
            per_day = FREQ_PER_DAY.get(rec.frequency, 1)
            if rec.frequency == "stat":
                Mar.create({"ward_order_id": rec.id, "admission_id": rec.admission_id.id, "scheduled_at": fields.Datetime.now()})
                continue
            if not per_day:
                continue
            start = fields.Datetime.now().replace(minute=0, second=0, microsecond=0)
            step = timedelta(hours=24 / per_day)
            slots = per_day * max(1, rec.duration_days)
            for i in range(slots):
                Mar.create({"ward_order_id": rec.id, "admission_id": rec.admission_id.id, "scheduled_at": start + step * i})

    def action_stop(self):
        for rec in self:
            rec.state = "stopped"
            rec.mar_ids.filtered(lambda m: m.state == "due").write({"state": "held"})

    def action_give_prn(self):
        self.ensure_one()
        mar = self.env["hms.mar"].create({"ward_order_id": self.id, "admission_id": self.admission_id.id, "scheduled_at": fields.Datetime.now()})
        return {"type": "ir.actions.act_window", "res_model": "hms.mar", "res_id": mar.id, "view_mode": "form", "target": "new"}

    def _compute_display_name(self):
        freq = dict(FREQUENCIES)
        for rec in self:
            if rec.drug_id:
                rec.display_name = f"{rec.drug_id.name} {rec.dose or ''} {rec.route or ''} {freq.get(rec.frequency, '')}".strip()
            else:
                rec.display_name = rec.instruction or dict(self._fields["order_type"].selection)[rec.order_type]


class HmsMar(models.Model):
    """Medication Administration Record. The MAR will not record a dose until the nurse scans the
    patient's band and the medicine itself — five rights checked by the system. One tap records the
    dose and the charge posts to the bill by itself."""
    _name = "hms.mar"
    _description = "Medication Administration Record"
    _order = "scheduled_at"

    ward_order_id = fields.Many2one("hms.ward.order", required=True, ondelete="cascade")
    admission_id = fields.Many2one("hms.admission", required=True, ondelete="cascade")
    patient_id = fields.Many2one(related="admission_id.patient_id", store=True)
    drug_id = fields.Many2one(related="ward_order_id.drug_id", store=True)
    dose = fields.Char(related="ward_order_id.dose")
    route = fields.Selection(related="ward_order_id.route")
    scheduled_at = fields.Datetime(required=True)
    given_at = fields.Datetime(readonly=True)
    nurse_id = fields.Many2one("hms.practitioner", readonly=True)
    scanned_band = fields.Char(string="Scan Patient Band")
    scanned_medicine = fields.Char(string="Scan Medicine")
    state = fields.Selection([("due", "Due"), ("given", "Given"), ("held", "Held"), ("refused", "Refused"), ("missed", "Missed")], default="due")
    note = fields.Char()
    overdue = fields.Boolean(compute="_compute_overdue")

    def _compute_overdue(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.overdue = rec.state == "due" and rec.scheduled_at < now - timedelta(minutes=60)

    def action_give(self):
        Charge = self.env["hms.charge"]
        for rec in self:
            if rec.state != "due":
                raise UserError(_("This dose is not due."))
            band = (rec.scanned_band or "").strip().upper()
            med = (rec.scanned_medicine or "").strip()
            if band != (rec.patient_id.mrn or "").upper():
                raise UserError(_("Wrong patient: scanned band '%s' does not match %s (%s). Dose NOT recorded.") % (rec.scanned_band, rec.patient_id.name, rec.patient_id.mrn))
            expected = rec.drug_id.barcode or rec.drug_id.name
            if med.lower() not in (expected or "").lower() and (expected or "").lower() not in med.lower():
                raise UserError(_("Wrong medicine: scanned '%s' but the order is for %s. Dose NOT recorded.") % (rec.scanned_medicine, rec.drug_id.name))
            rec.write({"state": "given", "given_at": fields.Datetime.now(), "nurse_id": self.env["hms.practitioner"].get_current().id})
            Charge.create({
                "visit_id": rec.admission_id.visit_id.id, "product_id": rec.drug_id.get_or_create_product().id,
                "description": f"{rec.drug_id.name} {rec.dose or ''} (ward dose)", "quantity": 1,
                "price_unit": rec.ward_order_id.price_unit or rec.drug_id.price, "source": "mar",
            })
            if all(m.state != "due" for m in rec.ward_order_id.mar_ids):
                rec.ward_order_id.state = "completed"
        return True

    def action_hold(self):
        self.write({"state": "held"})

    def action_refused(self):
        self.write({"state": "refused"})


class HmsHandoff(models.Model):
    """Shift change. One tap and the SBAR is drafted from the chart itself; the incoming nurse acknowledges."""
    _name = "hms.handoff"
    _description = "Nursing Handoff (SBAR)"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    admission_id = fields.Many2one("hms.admission", required=True, ondelete="cascade")
    patient_id = fields.Many2one(related="admission_id.patient_id", store=True)
    from_nurse_id = fields.Many2one("hms.practitioner", default=lambda self: self.env["hms.practitioner"].get_current(), readonly=True)
    to_nurse_id = fields.Many2one("hms.practitioner", string="Incoming Nurse", domain="[('role','=','nurse')]")
    shift = fields.Selection([("morning", "Morning"), ("evening", "Evening"), ("night", "Night")], default="morning")
    situation = fields.Text()
    background = fields.Text()
    assessment = fields.Text()
    recommendation = fields.Text()
    state = fields.Selection([("draft", "Draft"), ("sent", "Sent"), ("acknowledged", "Acknowledged")], default="draft", tracking=True)
    acknowledged_at = fields.Datetime(readonly=True)

    def action_ai_draft(self):
        for rec in self:
            data = self.env["hms.ai.service"].draft_sbar(rec.admission_id)
            rec.write({k: data.get(k, "") for k in ("situation", "background", "assessment", "recommendation")})
        return True

    def action_send(self):
        for rec in self:
            if not rec.to_nurse_id:
                raise UserError(_("Pick the incoming nurse."))
            if not (rec.situation and rec.recommendation):
                raise UserError(_("Situation and Recommendation are required."))
            rec.state = "sent"
            rec.admission_id.message_post(body=_("Shift handoff sent from %s to %s.") % (rec.from_nurse_id.display_name, rec.to_nurse_id.display_name))

    def action_acknowledge(self):
        for rec in self:
            rec.write({"state": "acknowledged", "acknowledged_at": fields.Datetime.now()})
            rec.admission_id.message_post(body=_("Handoff acknowledged by %s — loop closed.") % self.env.user.name)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"SBAR · {rec.patient_id.name} · {rec.create_date:%d %b %H:%M}" if rec.create_date else "SBAR"
