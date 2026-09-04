import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from .drug import ROUTES, FREQUENCIES


class HmsConsult(models.Model):
    """The consulting room.

    * The conversation is the record: `transcript` is filled by the scribe widget (browser
      speech recognition, Urdu or English) or typed; the doctor edits it before anything else happens.
    * Assist proposes; the doctor decides. Every diagnosis, medicine and test the AI proposes is a
      line in state 'proposed' until the doctor approves or rejects it. With `assist_enabled` off the
      form is a plain, fast consult form and nothing is suggested unless he asks.
    * Signing files the note, posts the orders and charges, creates the pharmacy queue entry and the
      referral, and writes the case into hospital memory.
    """
    _name = "hms.consult"
    _description = "Consultation"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(readonly=True, copy=False, default="New")
    visit_id = fields.Many2one("hms.visit", required=True, ondelete="cascade", index=True)
    patient_id = fields.Many2one(related="visit_id.patient_id", store=True)
    patient_age = fields.Integer(related="patient_id.age")
    patient_sex = fields.Selection(related="patient_id.sex")
    has_allergy = fields.Boolean(related="patient_id.has_allergy")
    allergy_summary = fields.Char(related="visit_id.allergy_summary")
    department_id = fields.Many2one(related="visit_id.department_id", store=True)
    doctor_id = fields.Many2one("hms.practitioner", required=True, domain="[('is_doctor','=',True)]", tracking=True)
    complaint = fields.Char(related="visit_id.complaint", readonly=False)
    latest_vitals_text = fields.Char(compute="_compute_vitals_text")
    ews_score = fields.Integer(related="visit_id.ews_score")
    stage = fields.Selection(related="visit_id.stage")
    state = fields.Selection([("draft", "In Progress"), ("signed", "Signed"), ("cancelled", "Cancelled")], default="draft", tracking=True)
    # scribe
    recording_consented = fields.Boolean(string="Patient informed & consented to recording")
    transcript = fields.Text(help="Live transcript from the scribe, or typed. Edit freely before analysing.")
    transcript_lang = fields.Selection([("en-PK", "English"), ("ur-PK", "Urdu"), ("en-US", "English (US)")], default="en-PK", string="Speech Language")
    # assist
    assist_enabled = fields.Boolean(string="AI Assist", default=True, help="Off = plain consult form, nothing suggested unless asked.")
    ai_summary = fields.Text(string="Patient Summary", readonly=True)
    ai_analysis_json = fields.Text(readonly=True)
    ai_analysed_at = fields.Datetime(readonly=True)
    ai_provider_used = fields.Char(readonly=True)
    ai_safety_alerts = fields.Text(string="Safety Check", readonly=True, help="Interaction & allergy conflicts found across proposed and approved medicines.")
    similar_cases_text = fields.Text(string="Hospital Memory", readonly=True, help="What this hospital's doctors prescribed for similar presentations.")
    # history
    hpi = fields.Text(string="History of Presenting Illness")
    past_history = fields.Text(string="Past Medical History")
    medication_history = fields.Text(string="Medication History")
    family_history = fields.Text()
    social_history = fields.Text()
    review_of_systems = fields.Text()
    examination = fields.Text(string="Examination Findings")
    # decision
    diagnosis_ids = fields.One2many("hms.consult.diagnosis", "consult_id", string="Diagnoses")
    working_diagnosis = fields.Char(compute="_compute_working_diagnosis", store=True)
    prescription_ids = fields.One2many("hms.prescription.line", "consult_id", string="Prescription")
    order_ids = fields.One2many("hms.order", "consult_id", string="Investigations")
    plan = fields.Text(string="Plan & Patient Advice")
    follow_up_days = fields.Integer(string="Follow-up in (days)")
    refer_department_id = fields.Many2one("hms.department", string="Refer To Department")
    refer_doctor_id = fields.Many2one("hms.practitioner", string="Refer To Doctor", domain="[('is_doctor','=',True)]")
    refer_reason = fields.Char()
    refer_urgency = fields.Selection([("routine", "Routine"), ("urgent", "Urgent"), ("immediate", "Immediate")], default="routine")
    referral_visit_id = fields.Many2one("hms.visit", string="Referral Visit", readonly=True, copy=False)
    admit = fields.Boolean(string="Request Admission")
    note = fields.Html(string="Signed Consult Note", readonly=True, sanitize=False)
    signed_at = fields.Datetime(readonly=True)
    proposed_count = fields.Integer(compute="_compute_proposed_count")
    referred_from_id = fields.Many2one("hms.consult", string="Referred From", readonly=True)

    # ---------------------------------------------------------------- computes
    @api.depends("visit_id.vitals_ids")
    def _compute_vitals_text(self):
        for rec in self:
            v = rec.visit_id.latest_vitals_id
            rec.latest_vitals_text = v.as_text() if v else ""

    @api.depends("diagnosis_ids.confirmed", "diagnosis_ids.name")
    def _compute_working_diagnosis(self):
        for rec in self:
            confirmed = rec.diagnosis_ids.filtered("confirmed")
            rec.working_diagnosis = ", ".join(confirmed.mapped("name")) if confirmed else ""

    @api.depends("diagnosis_ids.confirmed", "diagnosis_ids.rejected", "prescription_ids.state", "order_ids.state")
    def _compute_proposed_count(self):
        for rec in self:
            rec.proposed_count = (
                len(rec.diagnosis_ids.filtered(lambda d: d.ai_suggested and not d.confirmed and not d.rejected))
                + len(rec.prescription_ids.filtered(lambda p: p.state == "proposed"))
                + len(rec.order_ids.filtered(lambda o: o.state == "proposed"))
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("hms.consult") or "New"
        recs = super().create(vals_list)
        for rec in recs:
            rec.recording_consented = any(c.kind == "recording" and c.state == "signed" for c in rec.visit_id.consent_ids)
            if not rec.past_history and rec.patient_id.chronic_conditions:
                rec.past_history = rec.patient_id.chronic_conditions
            if not rec.medication_history and rec.patient_id.current_medicines:
                rec.medication_history = rec.patient_id.current_medicines
            if not rec.family_history and rec.patient_id.family_history:
                rec.family_history = rec.patient_id.family_history
            if not rec.social_history and rec.patient_id.social_history:
                rec.social_history = rec.patient_id.social_history
        return recs

    # ---------------------------------------------------------------- AI
    def action_summarise(self):
        for rec in self:
            rec.ai_summary = self.env["hms.ai.service"].summarize_visit(rec.visit_id)
            rec.visit_id.write({"ai_summary": rec.ai_summary, "ai_summary_at": fields.Datetime.now()})
        return True

    def action_analyse(self):
        """One click: Medica reads the conversation, vitals and history together and proposes.
        Nothing is final — every proposal waits for the doctor."""
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("The consult is already signed."))
        if not (self.transcript or self.complaint or self.hpi):
            raise UserError(_("Record or type the conversation (or at least the complaint) before analysing."))
        result = self.env["hms.ai.service"].analyse_consult(self)
        self._apply_analysis(result)
        return True

    def _apply_analysis(self, result):
        self.ensure_one()
        Diag = self.env["hms.consult.diagnosis"]
        Rx = self.env["hms.prescription.line"]
        Order = self.env["hms.order"]
        Drug = self.env["hms.drug"]
        Test = self.env["hms.test"]
        Icd = self.env["hms.icd10"]
        # clear previous un-actioned proposals so re-analysis does not duplicate
        self.diagnosis_ids.filtered(lambda d: d.ai_suggested and not d.confirmed and not d.rejected).sudo().unlink()
        self.prescription_ids.filtered(lambda p: p.state == "proposed").sudo().unlink()
        self.order_ids.filtered(lambda o: o.state == "proposed").sudo().unlink()

        existing_names = set(self.diagnosis_ids.mapped("name"))
        for i, d in enumerate(result.get("diagnoses", [])[:5]):
            name = (d.get("name") or "").strip()
            if not name or name in existing_names:
                continue
            icd = Icd.search([("code", "=", d.get("icd10") or "")], limit=1) if d.get("icd10") else Icd.browse()
            if not icd and name:
                icd = Icd.search([("name", "ilike", name[:25])], limit=1)
            Diag.create({
                "consult_id": self.id, "name": name, "icd10_id": icd.id, "sequence": i,
                "reasoning": d.get("reasoning") or "", "ai_suggested": True, "top_match": i == 0,
                "source": d.get("source") or "ai",
            })
        for m in result.get("medicines", [])[:8]:
            drug = Drug.browse(m.get("drug_id")) if m.get("drug_id") else Drug.find_by_text(m.get("drug") or "")
            if not drug:
                continue
            route = m.get("route") if m.get("route") in dict(ROUTES) else drug.default_route
            freq = m.get("frequency") if m.get("frequency") in dict(FREQUENCIES) else drug.default_frequency
            Rx.create({
                "consult_id": self.id, "drug_id": drug.id, "dose": m.get("dose") or drug.default_dose or "1",
                "route": route, "frequency": freq, "duration_days": m.get("duration_days") or drug.default_duration_days,
                "reason": m.get("reason") or "", "state": "proposed", "ai_suggested": True, "source": m.get("source") or "ai",
                "learned": bool(m.get("learned")),
            })
        for t in result.get("investigations", [])[:8]:
            test = Test.browse(t.get("test_id")) if t.get("test_id") else Test.search(["|", ("name", "ilike", t.get("test") or "~"), ("code", "=ilike", t.get("test") or "~")], limit=1)
            if not test:
                continue
            Order.create({
                "visit_id": self.visit_id.id, "consult_id": self.id, "test_id": test.id, "ordered_by_id": self.doctor_id.id,
                "urgency": t.get("urgency") if t.get("urgency") in ("routine", "urgent", "stat") else "routine",
                "reason": t.get("reason") or "", "state": "proposed", "ai_suggested": True,
            })
        ref = result.get("referral") or {}
        if ref.get("department") and not self.refer_department_id:
            dept = self.env["hms.department"].search([("name", "ilike", ref["department"])], limit=1)
            if dept:
                self.refer_department_id = dept
                self.refer_reason = ref.get("reason") or ""
                self.refer_urgency = ref.get("urgency") if ref.get("urgency") in ("routine", "urgent", "immediate") else "routine"
        for k in ("hpi", "past_history", "medication_history", "family_history", "social_history", "review_of_systems"):
            if result.get(k) and not self[k]:
                self[k] = result[k]
        self.write({
            "ai_analysis_json": json.dumps(result, ensure_ascii=False, indent=1),
            "ai_analysed_at": fields.Datetime.now(),
            "ai_provider_used": result.get("_provider", ""),
            "similar_cases_text": result.get("_memory_text", ""),
        })
        self._run_safety_check()

    def _run_safety_check(self):
        """Interactions and allergy conflicts across proposed + approved medicines — flagged before the doctor even asks."""
        for rec in self:
            alerts = []
            lines = rec.prescription_ids.filtered(lambda p: p.state in ("proposed", "approved"))
            drugs = lines.mapped("drug_id")
            for line in lines:
                for w in line.drug_id.check_against_patient(rec.patient_id):
                    alerts.append(w)
                    line.warning = w
            seen = set()
            for d in drugs:
                for other in d.interaction_ids:
                    if other in drugs and (other.id, d.id) not in seen:
                        seen.add((d.id, other.id))
                        alerts.append(f"INTERACTION: {d.generic_name} + {other.generic_name}" + (f" — {d.interaction_note}" if d.interaction_note else ""))
            rec.ai_safety_alerts = "\n".join(dict.fromkeys(alerts)) if alerts else ""
        return True

    def action_recheck_safety(self):
        return self._run_safety_check()

    def action_approve_all_proposals(self):
        for rec in self:
            pending = rec.diagnosis_ids.filtered(lambda d: d.ai_suggested and not d.confirmed and not d.rejected)
            top = pending.filtered("top_match") or pending[:1]
            top.write({"confirmed": True})
            (pending - top).write({"rejected": True})  # considered / ruled out
            rec.prescription_ids.filtered(lambda p: p.state == "proposed").action_approve()
            rec.order_ids.filtered(lambda o: o.state == "proposed").action_approve()
        return True

    def action_reject_all_proposals(self):
        for rec in self:
            rec.diagnosis_ids.filtered(lambda d: d.ai_suggested and not d.confirmed).write({"rejected": True})
            rec.prescription_ids.filtered(lambda p: p.state == "proposed").action_reject()
            rec.order_ids.filtered(lambda o: o.state == "proposed").action_reject()
        return True

    def action_toggle_assist(self):
        for rec in self:
            rec.assist_enabled = not rec.assist_enabled
        return True

    # ---------------------------------------------------------------- sign
    def _build_note_html(self):
        self.ensure_one()
        p = self.patient_id
        dx = self.diagnosis_ids.filtered("confirmed")
        ruled_out = self.diagnosis_ids.filtered(lambda d: d.rejected or (d.ai_suggested and not d.confirmed))
        rx = self.prescription_ids.filtered(lambda l: l.state == "approved")
        orders = self.order_ids.filtered(lambda o: o.state not in ("proposed", "cancelled"))
        freq = dict(FREQUENCIES)
        route = dict(ROUTES)

        def para(label, text):
            return f"<p><b>{label}:</b> {text}</p>" if text else ""

        html = [f"<h3>Consultation — {self.doctor_id.display_name}, {self.department_id.name}</h3>",
                f"<p>{p.name} · {p.age_display} · MRN {p.mrn} · Visit {self.visit_id.name}</p>"]
        if p.has_allergy:
            html.append(f"<p style='color:#b91c1c'><b>ALLERGY ALERT:</b> {self.allergy_summary}</p>")
        html.append(para("Presenting complaint", self.complaint))
        html.append(para("History of presenting illness", self.hpi))
        html.append(para("Past medical history", self.past_history))
        html.append(para("Medication history", self.medication_history))
        html.append(para("Family history", self.family_history))
        html.append(para("Social history", self.social_history))
        html.append(para("Review of systems", self.review_of_systems))
        html.append(para("Vitals", self.latest_vitals_text))
        html.append(para("Examination", self.examination))
        if dx:
            html.append("<p><b>Diagnosis:</b> " + "; ".join(f"{d.name}" + (f" ({d.icd10_id.code})" if d.icd10_id else "") for d in dx) + "</p>")
        if ruled_out:
            html.append("<p><b>Considered / ruled out:</b> " + "; ".join(ruled_out.mapped("name")) + "</p>")
        if rx:
            html.append("<p><b>Prescription:</b></p><ol>" + "".join(
                f"<li>{l.drug_id.name} — {l.dose} {route.get(l.route, l.route)} {freq.get(l.frequency, l.frequency)} × {l.duration_days} days"
                + (f" <i>({l.reason})</i>" if l.reason else "") + "</li>" for l in rx) + "</ol>")
        if orders:
            html.append("<p><b>Investigations:</b> " + "; ".join(f"{o.test_id.name} [{o.urgency.upper()}]" for o in orders) + "</p>")
        html.append(para("Plan & advice", self.plan))
        if self.follow_up_days:
            html.append(f"<p><b>Follow-up:</b> in {self.follow_up_days} days</p>")
        if self.refer_department_id:
            html.append(f"<p><b>Referral:</b> {self.refer_department_id.name}" + (f" — {self.refer_doctor_id.display_name}" if self.refer_doctor_id else "") + f" ({self.refer_urgency}) — {self.refer_reason or ''}</p>")
        if self.transcript:
            html.append(f"<details><summary>Patient's own words (transcript)</summary><p style='white-space:pre-wrap'>{self.transcript}</p></details>")
        html.append(f"<p style='color:#6b7280'><i>Signed electronically by {self.doctor_id.display_name} ({self.doctor_id.pmdc_no or 'PMDC n/a'}) on {fields.Datetime.now():%d %b %Y %H:%M}</i></p>")
        return "".join(h for h in html if h)

    def action_sign(self):
        """End & sign: the note, the orders, the bill lines, the referral and the memory entry all file themselves."""
        for rec in self:
            if rec.state != "draft":
                continue
            if rec.proposed_count:
                raise UserError(_("%s AI proposal(s) are still waiting for your decision. Approve or reject each one before signing.") % rec.proposed_count)
            if not rec.diagnosis_ids.filtered("confirmed"):
                raise UserError(_("Confirm at least one diagnosis before signing."))
            rec._run_safety_check()
            rec.write({"note": rec._build_note_html(), "state": "signed", "signed_at": fields.Datetime.now()})
            # pharmacy queue for approved medicines
            approved = rec.prescription_ids.filtered(lambda l: l.state == "approved")
            if approved:
                self.env["hms.dispense"].create({
                    "consult_id": rec.id, "visit_id": rec.visit_id.id,
                    "line_ids": [(0, 0, {"prescription_line_id": l.id}) for l in approved],
                })
                rec.visit_id._advance_stage("treatment")
            # referral: the case lands with the specialist's own desk, nothing retyped
            if rec.refer_department_id:
                new_visit = self.env["hms.visit"].create({
                    "patient_id": rec.patient_id.id, "visit_type": "er" if rec.refer_urgency == "immediate" else "opd",
                    "department_id": rec.refer_department_id.id, "doctor_id": rec.refer_doctor_id.id,
                    "complaint": rec.working_diagnosis or rec.complaint,
                    "referred_by": f"{rec.doctor_id.display_name} ({rec.department_id.name}) — {rec.refer_reason or ''}",
                    "notes": f"Referral from consult {rec.name}. {rec.refer_reason or ''}",
                })
                new_visit._advance_stage("triaged")  # triage already done on first visit
                new_consult = self.env["hms.consult"].create({"visit_id": new_visit.id, "doctor_id": (rec.refer_doctor_id or rec.refer_department_id.head_id or rec.doctor_id).id, "referred_from_id": rec.id})
                new_consult.action_summarise()
                rec.referral_visit_id = new_visit
            if rec.admit:
                rec.visit_id.message_post(body=_("Admission requested by %s.") % rec.doctor_id.display_name)
            # patient master keeps learning
            if rec.medication_history and rec.medication_history != rec.patient_id.current_medicines:
                rec.patient_id.current_medicines = rec.medication_history
            if rec.past_history and rec.past_history != rec.patient_id.chronic_conditions:
                rec.patient_id.chronic_conditions = rec.past_history
            # hospital memory
            self.env["hms.case.memory"].record_from_consult(rec)
            rec.visit_id.message_post(body=_("Consult %s signed by %s — diagnosis: %s") % (rec.name, rec.doctor_id.display_name, rec.working_diagnosis))
        return True

    def action_cancel(self):
        self.filtered(lambda c: c.state == "draft").write({"state": "cancelled"})

    def action_teach(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "res_model": "hms.ai.rule", "view_mode": "form", "target": "new",
            "context": {"default_doctor_id": self.doctor_id.id, "default_department_id": self.department_id.id,
                        "default_trigger_keywords": self.working_diagnosis or self.complaint},
        }

    def action_print_prescription(self):
        return self.env.ref("stratos_hms.action_report_prescription").report_action(self)

    def action_whatsapp_prescription(self):
        self.ensure_one()
        freq = dict(FREQUENCIES)
        lines = "\n".join(f"• {l.drug_id.name}: {l.dose} {freq.get(l.frequency, l.frequency)} × {l.duration_days}d" for l in self.prescription_ids.filtered(lambda l: l.state == "approved"))
        msg = _("Assalam o Alaikum %s. Prescription from %s (%s):\n%s\n%s") % (self.patient_id.name, self.doctor_id.display_name, self.env.company.name, lines, self.plan or "")
        return self.env["hms.whatsapp"].link_action(self.patient_id.whatsapp or self.patient_id.phone, msg)

    def action_open_visit(self):
        self.ensure_one()
        return self.visit_id.action_open_chart()

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.name} · {rec.patient_id.name}"


class HmsConsultDiagnosis(models.Model):
    _name = "hms.consult.diagnosis"
    _description = "Consult Diagnosis Line"
    _order = "sequence, id"

    consult_id = fields.Many2one("hms.consult", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Diagnosis", required=True)
    icd10_id = fields.Many2one("hms.icd10", string="ICD-10")
    reasoning = fields.Text(help="Why this possibility fits — every AI proposal carries its reasoning.")
    ai_suggested = fields.Boolean(string="AI Proposed", readonly=True)
    top_match = fields.Boolean(readonly=True)
    source = fields.Char(readonly=True, help="ai / memory / protocol / doctor")
    confirmed = fields.Boolean(string="Confirmed by Doctor")
    rejected = fields.Boolean()

    @api.onchange("icd10_id")
    def _onchange_icd(self):
        if self.icd10_id and not self.name:
            self.name = self.icd10_id.name

    def action_confirm(self):
        self.write({"confirmed": True, "rejected": False})

    def action_reject(self):
        self.write({"rejected": True, "confirmed": False})


class HmsPrescriptionLine(models.Model):
    """One medicine on a consult. Proposed lines are the AI's; approved lines are the doctor's."""
    _name = "hms.prescription.line"
    _description = "Prescription Line"
    _order = "sequence, id"

    consult_id = fields.Many2one("hms.consult", required=True, ondelete="cascade")
    patient_id = fields.Many2one(related="consult_id.patient_id", store=True)
    sequence = fields.Integer(default=10)
    drug_id = fields.Many2one("hms.drug", required=True)
    dose = fields.Char(required=True, default="1")
    route = fields.Selection(ROUTES, default="po", required=True)
    frequency = fields.Selection(FREQUENCIES, default="bd", required=True)
    duration_days = fields.Integer(default=5)
    quantity = fields.Integer(compute="_compute_quantity", store=True, readonly=False, help="Units to dispense.")
    instructions = fields.Char(help="e.g. after food, with plenty of water")
    reason = fields.Char(help="Attached to every proposal: why this medicine.")
    state = fields.Selection([("proposed", "AI Proposed"), ("approved", "Approved"), ("rejected", "Rejected")], default="approved", required=True)
    ai_suggested = fields.Boolean(string="AI Proposed", readonly=True)
    source = fields.Char(readonly=True)
    learned = fields.Boolean(string="Learned Rule", readonly=True, help="Came from a rule this doctor taught the system.")
    warning = fields.Char(readonly=True)
    reject_reason = fields.Char()
    route_label = fields.Char(compute="_compute_labels")
    frequency_label = fields.Char(compute="_compute_labels")

    @api.depends("route", "frequency")
    def _compute_labels(self):
        routes, freqs = dict(ROUTES), dict(FREQUENCIES)
        for rec in self:
            rec.route_label = routes.get(rec.route, rec.route or "")
            rec.frequency_label = freqs.get(rec.frequency, rec.frequency or "")

    @api.depends("frequency", "duration_days", "dose")
    def _compute_quantity(self):
        from .drug import FREQ_PER_DAY
        for rec in self:
            per_day = FREQ_PER_DAY.get(rec.frequency, 1)
            rec.quantity = max(1, per_day * (rec.duration_days or 1)) if per_day else 1

    @api.onchange("drug_id")
    def _onchange_drug(self):
        if self.drug_id:
            self.dose = self.drug_id.default_dose or self.dose
            self.route = self.drug_id.default_route or self.route
            self.frequency = self.drug_id.default_frequency or self.frequency
            self.duration_days = self.drug_id.default_duration_days or self.duration_days
            if self.consult_id and self.consult_id.patient_id:
                w = self.drug_id.check_against_patient(self.consult_id.patient_id)
                self.warning = w[0] if w else False

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for rec in recs:
            if rec.drug_id and rec.patient_id and not rec.warning:
                w = rec.drug_id.check_against_patient(rec.patient_id)
                if w:
                    rec.warning = w[0]
        return recs

    def action_approve(self):
        for rec in self:
            if rec.warning and "ALLERGY" in rec.warning and not self.env.context.get("allergy_override"):
                raise UserError(_("%s\nThis medicine conflicts with a recorded allergy. Reject it, or override explicitly with a reason.") % rec.warning)
            rec.state = "approved"
        self.mapped("consult_id")._run_safety_check()
        return True

    def action_approve_override(self):
        return self.with_context(allergy_override=True).action_approve()

    def action_reject(self):
        self.write({"state": "rejected"})
        self.mapped("consult_id")._run_safety_check()
        return True
