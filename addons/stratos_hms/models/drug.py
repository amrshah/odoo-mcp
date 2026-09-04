from odoo import api, fields, models


ROUTES = [
    ("po", "Oral (PO)"), ("iv", "Intravenous (IV)"), ("im", "Intramuscular (IM)"), ("sc", "Subcutaneous (SC)"),
    ("sl", "Sublingual (SL)"), ("top", "Topical"), ("inh", "Inhalation / Nebulised"), ("pr", "Rectal (PR)"),
    ("neb", "Nebuliser"), ("eye", "Ophthalmic"), ("ear", "Otic"),
]
FREQUENCIES = [
    ("stat", "STAT (once now)"), ("od", "Once daily (OD)"), ("bd", "Twice daily (BD)"), ("tds", "Three times daily (TDS)"),
    ("qid", "Four times daily (QID)"), ("hs", "At night (HS)"), ("prn", "When required (PRN)"),
    ("q4h", "Every 4 hours"), ("q6h", "Every 6 hours"), ("q8h", "Every 8 hours"), ("q12h", "Every 12 hours"), ("weekly", "Weekly"),
]
FREQ_PER_DAY = {"stat": 0, "od": 1, "bd": 2, "tds": 3, "qid": 4, "hs": 1, "prn": 0, "q4h": 6, "q6h": 4, "q8h": 3, "q12h": 2, "weekly": 0}


class HmsDrug(models.Model):
    """Hospital formulary. Every medicine the AI may propose or a doctor may prescribe
    must exist here so that dose ranges, allergy classes and interactions can be checked."""
    _name = "hms.drug"
    _description = "Drug / Formulary Item"
    _order = "name"
    _rec_names_search = ["name", "generic_name", "brand"]

    name = fields.Char(required=True, help="Display name, e.g. 'Amoxicillin-Clavulanate 625 mg tab'")
    generic_name = fields.Char(required=True)
    brand = fields.Char(help="Common Pakistani brand, e.g. Augmentin, Panadol, Flagyl.")
    strength = fields.Char(help="e.g. 500 mg, 5 mg/5 ml")
    form = fields.Selection(
        [("tab", "Tablet"), ("cap", "Capsule"), ("syr", "Syrup / Suspension"), ("inj", "Injection"), ("drops", "Drops"),
         ("cream", "Cream / Ointment"), ("neb", "Nebule"), ("sachet", "Sachet"), ("inh", "Inhaler"), ("other", "Other")],
        default="tab", required=True,
    )
    default_route = fields.Selection(ROUTES, default="po")
    default_dose = fields.Char(help="Typical adult dose, e.g. '1 tab', '500 mg', '10 ml'")
    default_frequency = fields.Selection(FREQUENCIES, default="bd")
    default_duration_days = fields.Integer(default=5)
    drug_class = fields.Char(help="Therapeutic class, e.g. 'antibiotic', 'nsaid', 'antiplatelet', 'ors'.")
    allergen_class = fields.Char(help="Matches hms.allergy.allergen_class to block dispensing.")
    max_daily_dose_text = fields.Char(string="Max Daily Dose", help="Free text guard the AI and pharmacist see, e.g. '4 g paracetamol'.")
    paediatric_dose_text = fields.Char(string="Paediatric Dosing", help="e.g. '15 mg/kg/dose TDS'")
    renal_caution = fields.Boolean()
    pregnancy_caution = fields.Boolean()
    interaction_ids = fields.Many2many("hms.drug", "hms_drug_interaction_rel", "drug_id", "other_id", string="Interacts With")
    interaction_note = fields.Char(help="Shown when an interacting pair is prescribed together.")
    controlled = fields.Boolean(string="Controlled Substance")
    barcode = fields.Char(help="Scanned by the ward nurse before a dose is recorded on the MAR.")
    product_id = fields.Many2one("product.product", string="Product (for billing/stock)", ondelete="set null")
    price = fields.Float(string="Unit Price (PKR)")
    active = fields.Boolean(default=True)

    _barcode_uniq = models.Constraint("unique(barcode)", "Drug barcode must be unique.")

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name + (f" ({rec.brand})" if rec.brand else "")

    def check_against_patient(self, patient):
        """Return a list of warning strings for this drug on this patient (allergy classes, cautions)."""
        self.ensure_one()
        warnings = []
        if self.allergen_class:
            hit = patient.allergy_ids.filtered(lambda a: (a.allergen_class or "").lower() == self.allergen_class.lower())
            if hit:
                warnings.append(f"ALLERGY CONFLICT: patient is allergic to {', '.join(hit.mapped('name'))} — {self.name} belongs to class '{self.allergen_class}'.")
        if patient.allergy_notes and self.allergen_class and self.allergen_class.lower() in patient.allergy_notes.lower():
            warnings.append(f"ALLERGY CONFLICT (notes): '{patient.allergy_notes}' vs class '{self.allergen_class}'.")
        return warnings

    @api.model
    def find_by_text(self, text):
        """Best-effort lookup of a formulary item from free text the AI returned."""
        if not text:
            return self.browse()
        text_l = text.lower()
        for rec in self.search([]):
            for cand in (rec.generic_name, rec.name, rec.brand):
                if cand and cand.lower() in text_l:
                    return rec
        # token fallback
        tokens = [t for t in text_l.replace("(", " ").replace(")", " ").split() if len(t) > 3]
        for tok in tokens:
            rec = self.search(["|", "|", ("generic_name", "ilike", tok), ("name", "ilike", tok), ("brand", "ilike", tok)], limit=1)
            if rec:
                return rec
        return self.browse()

    def get_or_create_product(self):
        self.ensure_one()
        if not self.product_id:
            self.sudo().product_id = self.env["product.product"].sudo().create({
                "name": self.name, "type": "consu", "list_price": self.price or 0.0, "sale_ok": True, "purchase_ok": False,
                "default_code": f"DRUG-{self.id}",
            })
        return self.product_id


class HmsProtocol(models.Model):
    """Guideline / protocol table. Two jobs:
    1. The second voice next to hospital memory — the AI is told what the guideline says so the
       doctor can see when the hospital's habit diverges from it.
    2. Offline fallback: when no AI key is configured, proposals are generated from these rows."""
    _name = "hms.protocol"
    _description = "Clinical Protocol / Guideline"
    _order = "name"

    name = fields.Char(required=True, help="Condition, e.g. 'Acute watery diarrhoea (adult)'")
    department_id = fields.Many2one("hms.department")
    icd10_id = fields.Many2one("hms.icd10", string="ICD-10")
    trigger_keywords = fields.Char(required=True, help="Comma-separated words that suggest this condition, e.g. 'diarrhoea, loose motions, loose stools'")
    age_group = fields.Selection([("any", "Any"), ("adult", "Adult"), ("paed", "Paediatric")], default="any")
    reasoning = fields.Text(help="Why this diagnosis fits — shown to the doctor as the guideline's reasoning.")
    red_flags = fields.Text(help="Signs that should change management / trigger referral.")
    source = fields.Char(help="e.g. 'WHO 2023', 'National Guidelines Pakistan'")
    line_ids = fields.One2many("hms.protocol.line", "protocol_id", string="Suggested Medicines")
    investigation_ids = fields.Many2many("hms.test", string="Suggested Investigations")
    refer_department_id = fields.Many2one("hms.department", string="Refer To")
    active = fields.Boolean(default=True)

    def keyword_list(self):
        self.ensure_one()
        return [k.strip().lower() for k in (self.trigger_keywords or "").split(",") if k.strip()]

    @api.model
    def match_text(self, text, age=None):
        """Return protocols whose keywords appear in the text, best match first."""
        text_l = (text or "").lower()
        scored = []
        for p in self.search([]):
            if age is not None and p.age_group != "any":
                if p.age_group == "paed" and age >= 14:
                    continue
                if p.age_group == "adult" and age < 14:
                    continue
            hits = sum(1 for k in p.keyword_list() if k and k in text_l)
            if hits:
                scored.append((hits, p))
        scored.sort(key=lambda t: -t[0])
        return [p for _, p in scored]


class HmsProtocolLine(models.Model):
    _name = "hms.protocol.line"
    _description = "Protocol Medicine Line"
    _order = "sequence, id"

    protocol_id = fields.Many2one("hms.protocol", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    drug_id = fields.Many2one("hms.drug", required=True)
    dose = fields.Char(required=True)
    route = fields.Selection(ROUTES, default="po", required=True)
    frequency = fields.Selection(FREQUENCIES, default="bd", required=True)
    duration_days = fields.Integer(default=5)
    reason = fields.Char(help="Why — attached to every proposal the doctor sees.")
