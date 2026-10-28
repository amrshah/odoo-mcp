from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

OUTCOMES = [
    ("pending", "Awaiting follow-up"),
    ("resolved", "Resolved"),
    ("improved", "Improved"),
    ("not_improved", "Not improved"),
    ("died", "Died / Euthanised"),
]

# Fields that may still change after a case is finalised.
POST_FINAL_FIELDS = {
    "outcome", "outcome_date", "outcome_note", "state", "superseded_by_id",
}


class VetCmCase(models.Model):
    _name = "vet.cm.case"
    _description = "Clinical Case"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char("Case No.", default=lambda s: _("New"), readonly=True, copy=False)
    date = fields.Datetime(default=fields.Datetime.now, required=True, tracking=True)
    vet_id = fields.Many2one("res.users", "Veterinarian", default=lambda s: s.env.user,
                             tracking=True)
    state = fields.Selection([
        ("draft", "In consultation"),
        ("final", "Finalised"),
        ("superseded", "Superseded"),
    ], default="draft", required=True, tracking=True, copy=False)

    # ---- Animal -------------------------------------------------------
    animal_name = fields.Char("Animal / Tag", required=True, tracking=True)
    owner_id = fields.Many2one("res.partner", "Owner")
    owner_phone = fields.Char(related="owner_id.phone", string="Owner phone")
    species_id = fields.Many2one("vet.cm.species", required=True, tracking=True)
    food_producing = fields.Boolean(related="species_id.food_producing")
    breed = fields.Char()
    sex = fields.Selection([("male", "Male"), ("female", "Female")])
    repro_status = fields.Selection([
        ("intact", "Intact"),
        ("neutered", "Neutered / Spayed"),
        ("pregnant", "Pregnant"),
        ("lactating", "Lactating"),
    ], string="Reproductive status", default="intact")
    age_months = fields.Integer("Age (months)")
    life_stage = fields.Selection([
        ("young", "Young"),
        ("adult", "Adult"),
        ("senior", "Senior"),
    ], compute="_compute_life_stage", store=True)
    weight_kg = fields.Float("Weight (kg)", digits=(16, 2), tracking=True)

    # ---- Vitals -------------------------------------------------------
    temperature = fields.Float("Temperature (°C)", digits=(16, 1))
    heart_rate = fields.Integer("Heart rate (bpm)")
    resp_rate = fields.Integer("Respiratory rate (/min)")

    # ---- SOAP notes ---------------------------------------------------
    complaint = fields.Text("Presenting complaint")
    subjective = fields.Text("S – Subjective")
    objective = fields.Text("O – Objective")
    assessment = fields.Text("A – Assessment")
    plan = fields.Text("P – Plan")

    symptom_ids = fields.Many2many("vet.cm.symptom", string="Symptoms / signs", tracking=True)
    diagnosis_id = fields.Many2one("vet.cm.diagnosis", tracking=True)
    zoonotic = fields.Boolean(related="diagnosis_id.zoonotic")
    test_line_ids = fields.One2many("vet.cm.case.test", "case_id", string="Tests")
    treatment_line_ids = fields.One2many("vet.cm.case.treatment", "case_id", string="Treatment")

    # ---- Outcome (learning signal) ------------------------------------
    outcome = fields.Selection(OUTCOMES, default="pending", required=True, tracking=True)
    outcome_date = fields.Date()
    outcome_note = fields.Text("Follow-up note")

    # ---- Links --------------------------------------------------------
    suggestion_ids = fields.One2many("vet.cm.suggestion", "case_id", string="Suggestion runs")
    suggestion_count = fields.Integer(compute="_compute_counts")
    pending_line_count = fields.Integer("Pending decisions", compute="_compute_counts")
    voice_note_ids = fields.One2many("vet.cm.voice.note", "case_id", string="Voice history")
    voice_count = fields.Integer(compute="_compute_counts")
    amended_from_id = fields.Many2one("vet.cm.case", "Amendment of", readonly=True, copy=False)
    superseded_by_id = fields.Many2one("vet.cm.case", "Superseded by", readonly=True, copy=False)
    is_demo = fields.Boolean(copy=False)
    estimate_total = fields.Float("Owner estimate", compute="_compute_estimate")

    # ------------------------------------------------------------------
    @api.depends("age_months", "species_id.food_producing")
    def _compute_life_stage(self):
        for case in self:
            m = case.age_months or 0
            senior = 96 if case.species_id.food_producing else 84
            if m and m < 12:
                case.life_stage = "young"
            elif m >= senior:
                case.life_stage = "senior"
            else:
                case.life_stage = "adult"

    def _compute_counts(self):
        for case in self:
            case.suggestion_count = len(case.suggestion_ids)
            case.pending_line_count = len(case.suggestion_ids.line_ids.filtered(
                lambda l: l.decision == "pending" and not l.blocked))
            case.voice_count = len(case.voice_note_ids)

    @api.depends("test_line_ids.test_id.price", "treatment_line_ids.total_mg",
                 "treatment_line_ids.drug_id.price_per_mg")
    def _compute_estimate(self):
        for case in self:
            case.estimate_total = sum(case.test_line_ids.test_id.mapped("price")) + sum(
                l.total_mg * (l.days or 1) * l.drug_id.price_per_mg for l in case.treatment_line_ids)

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("vet.cm.case") or _("New")
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get("vet_cm_force_write"):
            locked = self.filtered(lambda c: c.state in ("final", "superseded"))
            blocked = {f for f in vals if f not in POST_FINAL_FIELDS
                       and not f.startswith(("message_", "activity_"))}
            if locked and blocked:
                raise UserError(_(
                    "Case %(case)s is finalised and locked. Use 'Amend' to create a "
                    "corrected version.", case=", ".join(locked.mapped("name"))))
        res = super().write(vals)
        if {"outcome", "state"} & set(vals):
            for species in self.mapped("species_id"):
                self.env["vet.cm.pattern"]._rebuild_for_species(species)
        return res

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _check_vet(self):
        if not self.env.user.has_group("stratos_vet_case_memory.group_vet_cm_vet"):
            raise UserError(_("Only a veterinarian can do this."))

    def action_get_suggestions(self):
        self.ensure_one()
        self._check_vet()
        if self.state != "draft":
            raise UserError(_("Suggestions can only be run on a case in consultation."))
        if not self.symptom_ids:
            raise UserError(_("Add at least one symptom (typed or from voice) first."))
        suggestion = self.env["vet.cm.suggestion"]._run_engine(self)
        return suggestion._action_open()

    def action_open_suggestions(self):
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "stratos_vet_case_memory.action_vet_cm_suggestion")
        action["domain"] = [("case_id", "=", self.id)]
        action["context"] = {"default_case_id": self.id}
        if len(self.suggestion_ids) == 1:
            action.update(view_mode="form", res_id=self.suggestion_ids.id,
                          views=[(False, "form")])
        return action

    def action_open_voice(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Voice history"),
            "res_model": "vet.cm.voice.note",
            "view_mode": "list,form",
            "domain": [("case_id", "=", self.id)],
            "context": {"default_case_id": self.id},
        }

    def action_finalise(self):
        self._check_vet()
        for case in self:
            if case.state != "draft":
                continue
            if not case.diagnosis_id:
                raise UserError(_("Set a diagnosis before finalising %s.", case.name))
            pending = case.suggestion_ids.line_ids.filtered(
                lambda l: l.decision == "pending" and not l.blocked)
            if pending:
                pending.write({"decision": "ignored"})
            case.state = "final"
            case.message_post(body=_("Case finalised by %s. It now feeds the knowledge base.",
                                     self.env.user.name))
        return True

    def action_amend(self):
        """Signed records are immutable: corrections create a new version."""
        self.ensure_one()
        self._check_vet()
        if self.state != "final":
            raise UserError(_("Only a finalised case can be amended."))
        new = self.with_context(vet_cm_force_write=True).copy({
            "amended_from_id": self.id,
            "state": "draft",
            "date": self.date,
            "outcome": self.outcome,
            "outcome_date": self.outcome_date,
            "outcome_note": self.outcome_note,
            "test_line_ids": [(0, 0, self._line_vals(l)) for l in self.test_line_ids],
            "treatment_line_ids": [(0, 0, self._line_vals(l)) for l in self.treatment_line_ids],
        })
        self.write({"state": "superseded", "superseded_by_id": new.id})
        self.message_post(body=_("Superseded by amendment %s.", new.name))
        return {
            "type": "ir.actions.act_window", "res_model": "vet.cm.case",
            "res_id": new.id, "view_mode": "form", "views": [(False, "form")],
        }

    @staticmethod
    def _line_vals(line):
        vals = line.copy_data()[0]
        vals.pop("case_id", None)
        return vals

    def action_print(self):
        return self.env.ref("stratos_vet_case_memory.action_report_vet_cm_case").report_action(self)

    # Called by the voice widget ----------------------------------------
    @api.model
    def get_voice_config(self):
        return {"lang": self.env["ir.config_parameter"].sudo().get_param(
            "vet_cm.voice_lang", "en-US")}

    def add_voice_note(self, transcript, lang="en-US", duration=0):
        self.ensure_one()
        transcript = (transcript or "").strip()
        if not transcript:
            return False
        note = self.env["vet.cm.voice.note"].create({
            "case_id": self.id,
            "transcript": transcript,
            "language": lang,
            "duration_sec": int(duration or 0),
        })
        note._extract()
        return note.id


class VetCmCaseLineLock(models.AbstractModel):
    _name = "vet.cm.case.line.lock"
    _description = "Lock lines of finalised cases"

    def _check_case_open(self, cases):
        if self.env.context.get("vet_cm_force_write"):
            return
        if cases.filtered(lambda c: c.state != "draft"):
            raise UserError(_("The case is finalised and locked. Use 'Amend' to correct it."))

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        self._check_case_open(recs.mapped("case_id"))
        return recs

    def write(self, vals):
        self._check_case_open(self.mapped("case_id"))
        return super().write(vals)

    def unlink(self):
        self._check_case_open(self.mapped("case_id"))
        return super().unlink()


class VetCmCaseTest(models.Model):
    _name = "vet.cm.case.test"
    _inherit = ["vet.cm.case.line.lock"]
    _description = "Case Test"

    case_id = fields.Many2one("vet.cm.case", required=True, ondelete="cascade")
    test_id = fields.Many2one("vet.cm.test", required=True)
    state = fields.Selection([
        ("draft", "Draft order"), ("done", "Result received"),
    ], default="draft")
    result = fields.Char()
    from_suggestion = fields.Boolean(readonly=True)


class VetCmCaseTreatment(models.Model):
    _name = "vet.cm.case.treatment"
    _inherit = ["vet.cm.case.line.lock"]
    _description = "Case Treatment / Prescription Line"

    case_id = fields.Many2one("vet.cm.case", required=True, ondelete="cascade")
    drug_id = fields.Many2one("vet.cm.drug", required=True)
    dose_basis = fields.Selection(related="drug_id.dose_basis")
    dose_mgkg = fields.Float("mg/kg", digits=(16, 3))
    total_mg = fields.Float("Dose (mg)", digits=(16, 2), compute="_compute_total", store=True)
    fixed_dose = fields.Char(related="drug_id.fixed_dose")
    route = fields.Selection(related="drug_id.route")
    frequency = fields.Char()
    days = fields.Integer()
    warning = fields.Char(compute="_compute_total", store=True)
    from_suggestion = fields.Boolean(readonly=True)
    state = fields.Selection([("draft", "Draft"), ("confirmed", "Confirmed")], default="draft")
    outcome = fields.Selection(related="case_id.outcome", store=True)
    species_id = fields.Many2one(related="case_id.species_id", store=True)

    @api.depends("dose_mgkg", "case_id.weight_kg", "drug_id", "case_id.species_id",
                 "case_id.breed", "case_id.repro_status")
    def _compute_total(self):
        for line in self:
            line.total_mg = (line.dose_mgkg * line.case_id.weight_kg
                             if line.drug_id.dose_basis == "per_kg" else 0.0)
            if line.drug_id:
                _b, warns = line.drug_id._safety_check(
                    line.case_id.species_id, line.case_id.breed,
                    line.case_id.repro_status, line.dose_mgkg)
                line.warning = " | ".join(warns) or False
            else:
                line.warning = False

    @api.onchange("drug_id")
    def _onchange_drug(self):
        for line in self:
            if line.drug_id:
                line.dose_mgkg = line.drug_id.dose_default
                line.frequency = line.drug_id.frequency
                line.days = line.drug_id.days

    @api.constrains("drug_id", "case_id")
    def _check_blocked(self):
        for line in self:
            if line.case_id.species_id and line.case_id.species_id in line.drug_id.blocked_species_ids:
                raise ValidationError(_(
                    "%(drug)s is blocked for %(species)s (species toxicity). "
                    "It cannot be prescribed.",
                    drug=line.drug_id.name, species=line.case_id.species_id.name))
