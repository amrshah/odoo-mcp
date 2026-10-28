import re

from odoo import api, fields, models

NEGATIONS = ("no ", "not ", "without ", "denies ", "nahi", "nahin", "absent ")


class VetCmSpecies(models.Model):
    _name = "vet.cm.species"
    _description = "Species"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    code = fields.Char()
    sequence = fields.Integer(default=10)
    food_producing = fields.Boolean(
        help="Milk / meat animal: withdrawal periods are shown on every "
             "suggested drug.")
    active = fields.Boolean(default=True)


class VetCmSymptom(models.Model):
    _name = "vet.cm.symptom"
    _description = "Symptom / Clinical Sign"
    _order = "category, name"

    name = fields.Char(required=True, translate=True)
    category = fields.Selection([
        ("general", "General"),
        ("gi", "Gastro-intestinal"),
        ("resp", "Respiratory"),
        ("skin", "Skin & Ear"),
        ("urinary", "Urinary"),
        ("repro", "Reproductive / Udder"),
        ("neuro", "Neurological / Musculoskeletal"),
        ("blood", "Blood / Circulation"),
    ], default="general", required=True)
    weight = fields.Selection([
        ("1", "Normal"),
        ("2", "Important"),
        ("3", "Key sign"),
    ], default="1", required=True,
        help="Key signs count more when similar cases are matched.")
    keywords = fields.Char(
        help="Comma-separated words or phrases (English or Urdu) that point "
             "to this symptom in voice dictation, e.g. 'vomit, ulti, qay'.")
    species_ids = fields.Many2many(
        "vet.cm.species", string="Species",
        help="Leave empty if the sign applies to every species.")
    active = fields.Boolean(default=True)

    _name_uniq = models.Constraint("UNIQUE(name)", "Symptom already exists.")

    @api.model
    def _detect_in_text(self, text, species=False):
        """Symptoms whose name or keywords appear in free text (not negated)."""
        text = " " + (text or "").lower().replace("\n", " ") + " "
        found = self.browse()
        for s in self.search([]):
            if s.species_ids and species and species not in s.species_ids:
                continue
            for kw in s._keyword_list():
                if re.search(r"[a-z]", kw):
                    m = re.search(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])", text)
                    pos = m.start() if m else -1
                else:  # Urdu script: plain substring
                    pos = text.find(kw)
                if pos >= 0 and not any(n in text[max(0, pos - 14):pos] for n in NEGATIONS):
                    found |= s
                    break
        return found

    def _keyword_list(self):
        self.ensure_one()
        words = [self.name.lower()]
        if self.keywords:
            words += [w.strip().lower() for w in self.keywords.split(",") if w.strip()]
        return words


class VetCmDiagnosis(models.Model):
    _name = "vet.cm.diagnosis"
    _description = "Diagnosis"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    species_ids = fields.Many2many("vet.cm.species", string="Species")
    zoonotic = fields.Boolean(
        help="Can pass to humans: staff and owner are alerted.")
    notifiable = fields.Boolean(help="Must be reported to the livestock / health authority.")
    note = fields.Text()
    active = fields.Boolean(default=True)


class VetCmTest(models.Model):
    _name = "vet.cm.test"
    _description = "Diagnostic Test"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    test_type = fields.Selection([
        ("lab", "Laboratory"),
        ("rapid", "Rapid / In-house kit"),
        ("imaging", "Imaging"),
        ("other", "Other"),
    ], default="lab")
    price = fields.Float(help="Used for the owner estimate.")
    active = fields.Boolean(default=True)


class VetCmDrug(models.Model):
    _name = "vet.cm.drug"
    _description = "Drug & Dosing Rule"
    _order = "name"

    name = fields.Char(required=True)
    active_ingredient = fields.Char()
    dose_basis = fields.Selection([
        ("per_kg", "mg per kg body weight"),
        ("fixed", "Fixed dose"),
    ], default="per_kg", required=True)
    dose_min = fields.Float("Min mg/kg", digits=(16, 3))
    dose_max = fields.Float("Max mg/kg", digits=(16, 3))
    dose_default = fields.Float("Default mg/kg", digits=(16, 3))
    fixed_dose = fields.Char("Fixed dose", help="e.g. '2 drops each ear'")
    route = fields.Selection([
        ("po", "Oral (PO)"),
        ("iv", "Intravenous (IV)"),
        ("im", "Intramuscular (IM)"),
        ("sc", "Subcutaneous (SC)"),
        ("topical", "Topical"),
        ("intramammary", "Intramammary"),
        ("otic", "Ear (otic)"),
    ], default="po")
    frequency = fields.Char(default="Once daily")
    days = fields.Integer("Default days", default=5)
    blocked_species_ids = fields.Many2many(
        "vet.cm.species", "vet_cm_drug_blocked_species_rel", "drug_id", "species_id",
        string="Blocked for species",
        help="Toxic / contraindicated: never suggested and cannot be "
             "prescribed for these species.")
    caution_breeds = fields.Char(
        help="Comma-separated breeds with a known sensitivity "
             "(e.g. 'Collie, Australian Shepherd').")
    avoid_pregnant = fields.Boolean("Caution in pregnancy / lactation")
    withdrawal_milk_days = fields.Integer("Milk withdrawal (days)")
    withdrawal_meat_days = fields.Integer("Meat withdrawal (days)")
    price_per_mg = fields.Float(digits=(16, 4), help="Optional, for the owner estimate.")
    note = fields.Text()
    active = fields.Boolean(default=True)

    def _safety_check(self, species, breed=False, repro_status=False, mgkg=0.0):
        """Return (blocked, warnings list) for this drug and animal."""
        self.ensure_one()
        warnings = []
        blocked = bool(species and species in self.blocked_species_ids)
        if blocked:
            warnings.append(f"BLOCKED: {self.name} is contraindicated in {species.name}.")
        if breed and self.caution_breeds:
            b = breed.lower()
            for cb in self.caution_breeds.split(","):
                cb = cb.strip().lower()
                if cb and (cb in b or b in cb):
                    warnings.append(f"Breed caution: {self.name} in {breed}.")
                    break
        if self.avoid_pregnant and repro_status in ("pregnant", "lactating"):
            warnings.append(f"Caution: {self.name} in a {repro_status} animal.")
        if self.dose_basis == "per_kg" and mgkg and (self.dose_min or self.dose_max):
            if (self.dose_min and mgkg < self.dose_min) or (self.dose_max and mgkg > self.dose_max):
                warnings.append(
                    f"Dose {mgkg:g} mg/kg is outside the range "
                    f"{self.dose_min:g}-{self.dose_max:g} mg/kg.")
        if species and species.food_producing and (self.withdrawal_milk_days or self.withdrawal_meat_days):
            warnings.append(
                f"Withdrawal: milk {self.withdrawal_milk_days} d, "
                f"meat {self.withdrawal_meat_days} d.")
        return blocked, warnings


class VetCmProtocol(models.Model):
    _name = "vet.cm.protocol"
    _description = "Clinical Protocol (starter knowledge)"
    _order = "species_id, name"

    name = fields.Char(required=True)
    species_id = fields.Many2one("vet.cm.species", required=True)
    diagnosis_id = fields.Many2one("vet.cm.diagnosis", required=True)
    symptom_ids = fields.Many2many("vet.cm.symptom", string="Typical signs")
    test_ids = fields.Many2many("vet.cm.test", string="Tests")
    line_ids = fields.One2many("vet.cm.protocol.line", "protocol_id", string="Treatment")
    author_id = fields.Many2one("res.users", default=lambda s: s.env.user, string="Senior vet")
    active = fields.Boolean(default=True)


class VetCmProtocolLine(models.Model):
    _name = "vet.cm.protocol.line"
    _description = "Protocol Treatment Line"

    protocol_id = fields.Many2one("vet.cm.protocol", required=True, ondelete="cascade")
    drug_id = fields.Many2one("vet.cm.drug", required=True)
    dose_mgkg = fields.Float("mg/kg", digits=(16, 3))
    frequency = fields.Char()
    days = fields.Integer()

    @api.onchange("drug_id")
    def _onchange_drug(self):
        for line in self:
            if line.drug_id:
                line.dose_mgkg = line.drug_id.dose_default
                line.frequency = line.drug_id.frequency
                line.days = line.drug_id.days
