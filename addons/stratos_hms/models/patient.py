from datetime import date

from odoo import api, fields, models


class HmsPatient(models.Model):
    """The single patient record every department reads from and writes to."""
    _name = "hms.patient"
    _description = "Patient"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _rec_names_search = ["name", "mrn", "phone", "cnic"]

    mrn = fields.Char(string="MRN", readonly=True, copy=False, index=True, default="New")
    name = fields.Char(required=True, tracking=True)
    father_husband_name = fields.Char(string="Father / Husband Name")
    partner_id = fields.Many2one(
        "res.partner", string="Billing Contact", ondelete="restrict", copy=False,
        help="Created automatically; used for invoices and payments.",
    )
    sex = fields.Selection([("m", "Male"), ("f", "Female"), ("o", "Other")], required=True, default="m", tracking=True)
    dob = fields.Date(string="Date of Birth", tracking=True)
    age = fields.Integer(compute="_compute_age", store=True, readonly=False, help="Editable when DOB is unknown.")
    age_display = fields.Char(compute="_compute_age_display")
    blood_group = fields.Selection(
        [("a+", "A+"), ("a-", "A−"), ("b+", "B+"), ("b-", "B−"), ("ab+", "AB+"), ("ab-", "AB−"), ("o+", "O+"), ("o-", "O−")],
        tracking=True,
    )
    cnic = fields.Char(string="CNIC", help="13-digit national identity number, e.g. 35202-1234567-1")
    phone = fields.Char(required=True, tracking=True)
    whatsapp = fields.Char(help="If different from phone. Used for one-tap sharing of bills and prescriptions.")
    email = fields.Char()
    address = fields.Char()
    city = fields.Char(default="Lahore")
    occupation = fields.Char()
    emergency_contact = fields.Char()
    emergency_relation = fields.Char()
    emergency_phone = fields.Char()
    allergy_ids = fields.Many2many("hms.allergy", string="Allergies", tracking=True)
    allergy_notes = fields.Char(string="Allergy Notes")
    has_allergy = fields.Boolean(compute="_compute_has_allergy", store=True)
    chronic_conditions = fields.Text(string="Chronic Conditions / Past History")
    current_medicines = fields.Text(string="Current Medicines")
    family_history = fields.Text()
    social_history = fields.Text(help="Smoking, occupation, living situation.")
    tier = fields.Selection([("standard", "Standard"), ("silver", "Silver"), ("gold", "Gold"), ("vip", "VIP")], default="standard")
    panel = fields.Char(string="Panel / Insurer", help="Corporate panel or insurer, if any.")
    image_128 = fields.Image(max_width=128, max_height=128)
    notes = fields.Text()
    active = fields.Boolean(default=True)

    visit_ids = fields.One2many("hms.visit", "patient_id", string="Visits")
    visit_count = fields.Integer(compute="_compute_counts")
    last_visit_date = fields.Datetime(compute="_compute_counts")
    admission_ids = fields.One2many("hms.admission", "patient_id", string="Admissions")
    outstanding_balance = fields.Monetary(compute="_compute_balance", currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    health_score = fields.Integer(compute="_compute_health_score", help="0-100 pulse computed from the latest vitals and open problems.")

    _mrn_uniq = models.Constraint("unique(mrn)", "MRN must be unique.")

    # ------------------------------------------------------------------ computes
    @api.depends("dob")
    def _compute_age(self):
        today = date.today()
        for rec in self:
            if rec.dob:
                rec.age = today.year - rec.dob.year - ((today.month, today.day) < (rec.dob.month, rec.dob.day))

    @api.depends("age", "sex")
    def _compute_age_display(self):
        sex = dict(self._fields["sex"].selection)
        for rec in self:
            rec.age_display = f"{rec.age or '?'}y · {sex.get(rec.sex, '')[:1]}"

    @api.depends("allergy_ids", "allergy_notes")
    def _compute_has_allergy(self):
        for rec in self:
            rec.has_allergy = bool(rec.allergy_ids or rec.allergy_notes)

    @api.depends("visit_ids")
    def _compute_counts(self):
        for rec in self:
            rec.visit_count = len(rec.visit_ids)
            rec.last_visit_date = rec.visit_ids[:1].arrival_time if rec.visit_ids else False

    def _compute_balance(self):
        Move = self.env["account.move"].sudo()
        for rec in self:
            moves = Move.search([("hms_patient_id", "=", rec.id), ("state", "=", "posted"), ("move_type", "=", "out_invoice")])
            rec.outstanding_balance = sum(moves.mapped("amount_residual"))

    def _compute_health_score(self):
        for rec in self:
            score = 85
            last = self.env["hms.vitals"].search([("patient_id", "=", rec.id)], order="create_date desc", limit=1)
            if last:
                score -= min(last.ews_score * 8, 45)
            if rec.chronic_conditions:
                score -= 10
            rec.health_score = max(20, min(100, score))

    # ------------------------------------------------------------------ crud
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("mrn", "New") == "New":
                vals["mrn"] = self.env["ir.sequence"].next_by_code("hms.patient") or "New"
        patients = super().create(vals_list)
        for p in patients:
            if not p.partner_id:
                p.partner_id = self.env["res.partner"].sudo().create({
                    "name": p.name, "phone": p.phone, "email": p.email or False,
                    "street": p.address or False, "city": p.city or False, "ref": p.mrn,
                })
        return patients

    def write(self, vals):
        res = super().write(vals)
        sync = {k: vals[k] for k in ("name", "phone", "email") if k in vals}
        if sync:
            for p in self.filtered("partner_id"):
                p.partner_id.sudo().write(sync)
        return res

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.name} [{rec.mrn}]" if rec.mrn else rec.name

    # ------------------------------------------------------------------ actions
    def action_new_visit(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hms.visit",
            "view_mode": "form",
            "target": "current",
            "context": {"default_patient_id": self.id},
        }

    def action_view_visits(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Visits",
            "res_model": "hms.visit",
            "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {"default_patient_id": self.id},
        }

    def action_view_chart(self):
        """Open the longitudinal chart: every visit, consult, result and payment, one scrolling story."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "hms.patient",
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref("stratos_hms.view_patient_chart_form").id,
            "target": "current",
        }

    def get_chart_context(self):
        """Structured snapshot of the record used by AI prompts and the chart summary."""
        self.ensure_one()
        vitals = self.env["hms.vitals"].search([("patient_id", "=", self.id)], order="create_date desc", limit=1)
        consults = self.env["hms.consult"].search([("patient_id", "=", self.id), ("state", "=", "signed")], order="signed_at desc", limit=5)
        results = self.env["hms.order"].search([("patient_id", "=", self.id), ("state", "in", ("resulted", "verified", "acknowledged"))], order="create_date desc", limit=10)
        return {
            "mrn": self.mrn,
            "name": self.name,
            "age": self.age,
            "sex": dict(self._fields["sex"].selection).get(self.sex),
            "allergies": [a.name for a in self.allergy_ids] + ([self.allergy_notes] if self.allergy_notes else []),
            "chronic_conditions": self.chronic_conditions or "",
            "current_medicines": self.current_medicines or "",
            "family_history": self.family_history or "",
            "social_history": self.social_history or "",
            "latest_vitals": vitals.as_text() if vitals else "",
            "recent_consults": [
                {"date": str(c.signed_at.date()) if c.signed_at else "", "doctor": c.doctor_id.display_name,
                 "diagnosis": ", ".join(c.diagnosis_ids.filtered("confirmed").mapped("name")), "plan": (c.plan or "")[:300]}
                for c in consults
            ],
            "recent_results": [
                {"test": r.test_id.name, "value": r.result_value or "", "unit": r.test_id.unit or "", "flag": r.flag}
                for r in results
            ],
            "outstanding_balance": self.outstanding_balance,
        }
