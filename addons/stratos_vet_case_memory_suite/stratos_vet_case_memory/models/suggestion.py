import math
from collections import Counter
from statistics import median

from odoo import _, api, fields, models
from odoo.exceptions import UserError

OUTCOME_WEIGHT = {
    "resolved": 1.0,
    "improved": 0.75,
    "pending": 0.4,
    "not_improved": -0.3,
    "died": -0.5,
}
STAGES = ["young", "adult", "senior"]


def _param(env, key, default):
    val = env["ir.config_parameter"].sudo().get_param("vet_cm." + key)
    try:
        return float(val) if val not in (None, False, "") else default
    except ValueError:
        return default


class VetCmSuggestion(models.Model):
    _name = "vet.cm.suggestion"
    _description = "Suggestion Run"
    _order = "date desc, id desc"

    name = fields.Char(readonly=True, default="/")
    case_id = fields.Many2one("vet.cm.case", required=True, ondelete="cascade", index=True)
    case_state = fields.Selection(related="case_id.state", string="Case status")
    species_id = fields.Many2one(related="case_id.species_id", store=True)
    date = fields.Datetime(default=fields.Datetime.now, readonly=True)
    user_id = fields.Many2one("res.users", "Run by", default=lambda s: s.env.user, readonly=True)
    match_ids = fields.One2many("vet.cm.suggestion.match", "suggestion_id", string="Similar cases")
    match_count = fields.Integer("Similar cases used")
    candidate_count = fields.Integer("Cases searched")
    low_evidence = fields.Boolean(readonly=True)
    suppressed_count = fields.Integer("Hidden (suppressed patterns)", readonly=True)
    summary = fields.Html(readonly=True, sanitize=True)
    ai_explanation = fields.Text("AI explanation", readonly=True)
    line_ids = fields.One2many("vet.cm.suggestion.line", "suggestion_id", string="Suggestions")
    diagnosis_line_ids = fields.One2many("vet.cm.suggestion.line", "suggestion_id",
                                         domain=[("item_type", "=", "diagnosis")])
    test_line_ids = fields.One2many("vet.cm.suggestion.line", "suggestion_id",
                                    domain=[("item_type", "=", "test")])
    drug_line_ids = fields.One2many("vet.cm.suggestion.line", "suggestion_id",
                                    domain=[("item_type", "=", "drug")])
    state = fields.Selection([
        ("pending", "Awaiting vet"), ("partial", "Partly decided"), ("done", "Decided"),
    ], compute="_compute_state", store=True)
    ai_enabled = fields.Boolean(compute="_compute_ai_enabled")

    @api.depends("line_ids.decision")
    def _compute_state(self):
        for s in self:
            lines = s.line_ids.filtered(lambda l: not l.blocked)
            pending = lines.filtered(lambda l: l.decision == "pending")
            if not lines or not pending:
                s.state = "done"
            elif len(pending) == len(lines):
                s.state = "pending"
            else:
                s.state = "partial"

    def _compute_ai_enabled(self):
        enabled = self.env["ir.config_parameter"].sudo().get_param("vet_cm.ai_enabled") == "True"
        for s in self:
            s.ai_enabled = enabled

    def _action_open(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Clinical suggestions"),
            "res_model": "vet.cm.suggestion", "res_id": self.id,
            "view_mode": "form", "views": [(False, "form")], "target": "current",
        }

    # ------------------------------------------------------------------
    # Similarity
    # ------------------------------------------------------------------
    @api.model
    def _similarity(self, a, b):
        """Return dict of component scores (0..1) between two cases."""
        wa = {s.id: int(s.weight) for s in a.symptom_ids}
        wb = {s.id: int(s.weight) for s in b.symptom_ids}
        inter = sum(min(wa[i], wb[i]) for i in set(wa) & set(wb))
        union = sum(max(wa.get(i, 0), wb.get(i, 0)) for i in set(wa) | set(wb))
        sym = inter / union if union else 0.0

        if a.age_months and b.age_months:
            d = abs(STAGES.index(a.life_stage) - STAGES.index(b.life_stage))
            age = {0: 1.0, 1: 0.5}.get(d, 0.0)
        else:
            age = 0.5

        if a.weight_kg and b.weight_kg:
            weight = 1 - min(1.0, abs(math.log(a.weight_kg / b.weight_kg)) / math.log(3))
        else:
            weight = 0.5

        if a.breed and b.breed:
            breed = 1.0 if a.breed.strip().lower() == b.breed.strip().lower() else 0.0
        else:
            breed = 0.5

        parts = []
        if a.temperature and b.temperature:
            parts.append(1 - min(1.0, abs(a.temperature - b.temperature) / 2.0))
        if a.heart_rate and b.heart_rate:
            parts.append(1 - min(1.0, abs(a.heart_rate - b.heart_rate)
                                 / (0.4 * max(a.heart_rate, b.heart_rate))))
        if a.resp_rate and b.resp_rate:
            parts.append(1 - min(1.0, abs(a.resp_rate - b.resp_rate)
                                 / (0.5 * max(a.resp_rate, b.resp_rate))))
        vitals = sum(parts) / len(parts) if parts else 0.5
        return {"sym": sym, "age": age, "weight": weight, "breed": breed, "vitals": vitals}

    @api.model
    def _weights(self):
        w = {
            "sym": _param(self.env, "w_symptoms", 50),
            "age": _param(self.env, "w_age", 15),
            "weight": _param(self.env, "w_weight", 10),
            "breed": _param(self.env, "w_breed", 10),
            "vitals": _param(self.env, "w_vitals", 15),
        }
        total = sum(w.values()) or 1.0
        return {k: v / total for k, v in w.items()}

    # ------------------------------------------------------------------
    # Engine
    # ------------------------------------------------------------------
    @api.model
    def _run_engine(self, case):
        min_cases = int(_param(self.env, "min_cases", 3))
        min_sim = _param(self.env, "min_similarity", 35) / 100.0
        min_conf = _param(self.env, "min_confidence", 40)
        max_matches = int(_param(self.env, "max_matches", 20))
        weights = self._weights()

        Case = self.env["vet.cm.case"].sudo()
        candidates = Case.search([
            ("species_id", "=", case.species_id.id),
            ("state", "=", "final"),
            ("id", "!=", case.id),
        ])
        scored = []
        for cand in candidates:
            comp = self._similarity(case, cand)
            if comp["sym"] <= 0:
                continue
            score = sum(weights[k] * comp[k] for k in weights)
            if score >= min_sim:
                scored.append((score, comp, cand))
        scored.sort(key=lambda x: x[0], reverse=True)
        scored = scored[:max_matches]

        sug = self.create({
            "case_id": case.id,
            "name": f"{case.name} / {len(case.suggestion_ids) + 1}",
            "candidate_count": len(candidates),
            "match_count": len(scored),
            "match_ids": [(0, 0, {
                "matched_case_id": c.id, "score": round(s * 100, 1),
                "sym_score": round(comp["sym"] * 100), "age_score": round(comp["age"] * 100),
                "weight_score": round(comp["weight"] * 100),
                "breed_score": round(comp["breed"] * 100),
                "vitals_score": round(comp["vitals"] * 100),
            }) for s, comp, c in scored],
        })

        Pattern = self.env["vet.cm.pattern"]
        lines, suppressed = [], 0
        if len(scored) >= min_cases:
            total_score = sum(s for s, _c, _x in scored) or 1.0
            buckets = {}  # (type, record) -> data

            def add(itype, rec, s, cand, extra=None):
                b = buckets.setdefault((itype, rec), {"support": 0.0, "cases": [],
                                                      "known": 0, "good": 0, "extra": []})
                # Outcome only judges treatments; a diagnosis or test is evidence
                # by similarity alone.
                b["support"] += s * (OUTCOME_WEIGHT.get(cand.outcome, 0.4)
                                     if itype == "drug" else 1.0)
                b["cases"].append(cand.id)
                if cand.outcome in ("resolved", "improved", "not_improved", "died"):
                    b["known"] += 1
                    if cand.outcome in ("resolved", "improved"):
                        b["good"] += 1
                if extra:
                    b["extra"].append(extra)

            for s, _comp, cand in scored:
                if cand.diagnosis_id:
                    add("diagnosis", cand.diagnosis_id, s, cand)
                for t in cand.test_line_ids.test_id:
                    add("test", t, s, cand)
                for tl in cand.treatment_line_ids:
                    add("drug", tl.drug_id, s, cand, (tl.dose_mgkg, tl.frequency, tl.days))

            diag_lines = []
            for (itype, rec), b in buckets.items():
                pat = Pattern._get(case.species_id, itype, rec)
                conf = max(0.0, b["support"]) / total_score * 100 * pat.factor
                conf = min(conf, 99.0)
                if pat.suppressed:
                    suppressed += 1
                    continue
                if conf < min_conf:
                    continue
                vals = {
                    "item_type": itype,
                    "source": "cases",
                    "confidence": round(conf, 1),
                    "support_count": len(b["cases"]),
                    "success_rate": round(100.0 * b["good"] / b["known"], 1) if b["known"] else 0.0,
                    "evidence_case_ids": [(6, 0, b["cases"])],
                    "pattern_id": pat.id,
                    f"{itype}_id": rec.id,
                }
                if itype == "drug":
                    doses = [e[0] for e in b["extra"] if e[0]]
                    vals["dose_mgkg"] = round(median(doses), 3) if doses else rec.dose_default
                    freq = Counter(e[1] for e in b["extra"] if e[1]).most_common(1)
                    days = Counter(e[2] for e in b["extra"] if e[2]).most_common(1)
                    vals["frequency"] = freq[0][0] if freq else rec.frequency
                    vals["days"] = days[0][0] if days else rec.days
                if itype == "diagnosis":
                    diag_lines.append(vals)
                else:
                    lines.append(vals)
            diag_lines.sort(key=lambda v: v["confidence"], reverse=True)
            lines = diag_lines[:3] + lines
        else:
            lines = self._protocol_lines(case)

        for v in lines:
            v.setdefault("final_mgkg", v.get("dose_mgkg", 0.0))
            v.setdefault("final_frequency", v.get("frequency"))
            v.setdefault("final_days", v.get("days"))
        sug.write({
            "line_ids": [(0, 0, v) for v in lines],
            "low_evidence": len(scored) < min_cases,
            "suppressed_count": suppressed,
        })
        sug.line_ids._compute_safety()
        sug.summary = sug._build_summary(min_cases)
        case.message_post(body=_(
            "Suggestion run %(name)s: %(n)s similar cases, %(l)s suggestions "
            "(pending vet decision).", name=sug.name, n=len(scored), l=len(sug.line_ids)))
        return sug

    @api.model
    def _protocol_lines(self, case):
        """Cold start: use senior-vet protocols that overlap the symptoms."""
        protos = self.env["vet.cm.protocol"].search([("species_id", "=", case.species_id.id)])
        ranked = []
        mine = set(case.symptom_ids.ids)
        for p in protos:
            ps = set(p.symptom_ids.ids)
            if not ps or not (mine & ps):
                continue
            overlap = len(mine & ps) / len(mine | ps)
            ranked.append((overlap, p))
        ranked.sort(key=lambda x: x[0], reverse=True)
        lines = []
        for overlap, p in ranked[:2]:
            conf = round(overlap * 60, 1)  # capped: protocol only, low evidence
            lines.append({"item_type": "diagnosis", "source": "protocol", "protocol_id": p.id,
                          "diagnosis_id": p.diagnosis_id.id, "confidence": conf})
            for t in p.test_ids:
                lines.append({"item_type": "test", "source": "protocol", "protocol_id": p.id,
                              "test_id": t.id, "confidence": conf})
            for pl in p.line_ids:
                lines.append({"item_type": "drug", "source": "protocol", "protocol_id": p.id,
                              "drug_id": pl.drug_id.id, "dose_mgkg": pl.dose_mgkg,
                              "frequency": pl.frequency, "days": pl.days, "confidence": conf})
        return lines

    def _build_summary(self, min_cases):
        self.ensure_one()
        case = self.case_id
        parts = []
        if self.low_evidence:
            parts.append(_(
                "<p><b>Low evidence.</b> Only %(n)s similar finalised %(sp)s case(s) found "
                "(minimum %(m)s). Suggestions below come from senior-vet protocols, "
                "not from case history.</p>",
                n=self.match_count, sp=case.species_id.name, m=min_cases))
        else:
            top = self.match_ids[:3]
            parts.append(_(
                "<p>Searched <b>%(c)s</b> finalised %(sp)s cases; <b>%(n)s</b> are similar "
                "to this patient. Closest matches: %(top)s.</p>",
                c=self.candidate_count, sp=case.species_id.name, n=self.match_count,
                top=", ".join(f"{m.matched_case_id.name} ({m.score:g}%)" for m in top)))
        if self.suppressed_count:
            parts.append(_("<p>%s pattern(s) hidden because vets repeatedly rejected them.</p>",
                           self.suppressed_count))
        warn = self.line_ids.filtered("blocked")
        if warn:
            parts.append(_("<p><b>Safety:</b> %s item(s) blocked for this species.</p>",
                           len(warn)))
        if self.line_ids.filtered(lambda l: l.zoonotic):
            parts.append(_("<p><b>Zoonotic risk</b> in the suggested diagnoses: use PPE "
                           "and inform the owner.</p>"))
        parts.append(_("<p><i>Decision support only. The veterinarian decides; nothing is "
                       "ordered until approved.</i></p>"))
        return "".join(parts)

    def action_explain_ai(self):
        self.ensure_one()
        client = self.env["vet.cm.ai.client"]
        case = self.case_id
        matched = "\n".join(
            f"- {m.matched_case_id.name}: similarity {m.score}%, diagnosis "
            f"{m.matched_case_id.diagnosis_id.name or '-'}, outcome {m.outcome}, symptoms "
            f"{', '.join(m.matched_case_id.symptom_ids.mapped('name'))}"
            for m in self.match_ids[:8])
        sugg = "\n".join(f"- {l.item_type}: {l.item_name} ({l.confidence}% confidence, "
                         f"{l.support_count} cases)" for l in self.line_ids)
        system = ("You are a veterinary clinical decision-SUPPORT assistant inside a clinic "
                  "ERP. Explain briefly (max 150 words) why these past cases match the "
                  "current patient and what the vet should double-check. You never "
                  "prescribe; the veterinarian decides. Use only the data given.")
        user = (f"Current patient: {case.species_id.name}, {case.breed or ''}, "
                f"{case.age_months} months, {case.weight_kg} kg, temp {case.temperature}. "
                f"Symptoms: {', '.join(case.symptom_ids.mapped('name'))}.\n"
                f"Matched cases:\n{matched}\nSuggestions:\n{sugg}")
        self.ai_explanation = client._complete(system, user)
        return True


class VetCmSuggestionMatch(models.Model):
    _name = "vet.cm.suggestion.match"
    _description = "Matched Past Case"
    _order = "score desc"

    suggestion_id = fields.Many2one("vet.cm.suggestion", required=True, ondelete="cascade")
    matched_case_id = fields.Many2one("vet.cm.case", "Past case", required=True)
    score = fields.Float("Similarity %", digits=(16, 1))
    sym_score = fields.Integer("Symptoms %")
    age_score = fields.Integer("Age %")
    weight_score = fields.Integer("Weight %")
    breed_score = fields.Integer("Breed %")
    vitals_score = fields.Integer("Vitals %")
    animal_name = fields.Char(related="matched_case_id.animal_name")
    breed = fields.Char(related="matched_case_id.breed")
    diagnosis_id = fields.Many2one(related="matched_case_id.diagnosis_id")
    outcome = fields.Selection(related="matched_case_id.outcome")
    case_date = fields.Datetime(related="matched_case_id.date")

    def action_open_case(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "vet.cm.case",
                "res_id": self.matched_case_id.id, "view_mode": "form",
                "views": [(False, "form")], "target": "new"}


class VetCmSuggestionLine(models.Model):
    _name = "vet.cm.suggestion.line"
    _description = "Suggested Item"
    _order = "item_type, confidence desc, id"

    suggestion_id = fields.Many2one("vet.cm.suggestion", "Suggestion run", required=True, ondelete="cascade")
    case_id = fields.Many2one(related="suggestion_id.case_id", store=True, index=True)
    case_state = fields.Selection(related="case_id.state", string="Case status")
    vet_id = fields.Many2one(related="case_id.vet_id", store=True)
    species_id = fields.Many2one(related="case_id.species_id", store=True)
    item_type = fields.Selection([
        ("diagnosis", "Diagnosis"), ("test", "Test"), ("drug", "Treatment"),
    ], required=True)
    diagnosis_id = fields.Many2one("vet.cm.diagnosis")
    test_id = fields.Many2one("vet.cm.test")
    drug_id = fields.Many2one("vet.cm.drug")
    item_name = fields.Char("Suggestion", compute="_compute_item_name", store=True)
    source = fields.Selection([("cases", "Similar cases"), ("protocol", "Protocol")],
                              default="cases")
    protocol_id = fields.Many2one("vet.cm.protocol")
    pattern_id = fields.Many2one("vet.cm.pattern")
    confidence = fields.Float("Confidence %", digits=(16, 1))
    support_count = fields.Integer("Cases")
    success_rate = fields.Float("Success %", digits=(16, 1))
    evidence_case_ids = fields.Many2many("vet.cm.case", string="Evidence cases")

    dose_mgkg = fields.Float("Suggested mg/kg", digits=(16, 3))
    frequency = fields.Char("Suggested frequency")
    days = fields.Integer("Suggested days")
    final_mgkg = fields.Float("mg/kg", digits=(16, 3))
    final_frequency = fields.Char("Frequency")
    final_days = fields.Integer("Days")
    total_mg = fields.Float("Dose for this animal (mg)", compute="_compute_total", digits=(16, 2))
    dose_display = fields.Char("Dose", compute="_compute_total")

    blocked = fields.Boolean(readonly=True)
    warning = fields.Char(readonly=True)
    zoonotic = fields.Boolean(related="diagnosis_id.zoonotic")
    withdrawal = fields.Char(compute="_compute_withdrawal")

    decision = fields.Selection([
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("modified", "Modified & approved"),
        ("rejected", "Rejected"),
        ("ignored", "Not used"),
    ], default="pending", required=True, index=True)
    reject_reason = fields.Text()
    decided_by = fields.Many2one("res.users", readonly=True)
    decided_on = fields.Datetime(readonly=True)

    @api.depends("diagnosis_id", "test_id", "drug_id")
    def _compute_item_name(self):
        for l in self:
            rec = l.diagnosis_id or l.test_id or l.drug_id
            l.item_name = rec.display_name if rec else False

    @api.depends("final_mgkg", "final_frequency", "final_days", "case_id.weight_kg", "drug_id")
    def _compute_total(self):
        for l in self:
            if l.item_type != "drug" or not l.drug_id:
                l.total_mg, l.dose_display = 0.0, False
            elif l.drug_id.dose_basis == "fixed":
                l.total_mg = 0.0
                l.dose_display = f"{l.drug_id.fixed_dose or ''} · {l.final_frequency or ''}"
            else:
                l.total_mg = l.final_mgkg * (l.case_id.weight_kg or 0.0)
                l.dose_display = (f"{l.final_mgkg:g} mg/kg → {l.total_mg:.1f} mg · "
                                  f"{l.final_frequency or ''} × {l.final_days or 0} d")

    def _compute_withdrawal(self):
        for l in self:
            if l.drug_id and l.case_id.species_id.food_producing and (
                    l.drug_id.withdrawal_milk_days or l.drug_id.withdrawal_meat_days):
                l.withdrawal = (f"Milk {l.drug_id.withdrawal_milk_days} d / "
                                f"Meat {l.drug_id.withdrawal_meat_days} d")
            else:
                l.withdrawal = False

    def _compute_safety(self):
        for l in self:
            case = l.case_id
            if l.item_type == "drug" and l.drug_id:
                blocked, warns = l.drug_id._safety_check(
                    case.species_id, case.breed, case.repro_status, l.final_mgkg)
                l.write({"blocked": blocked, "warning": " | ".join(warns) or False})
            elif l.item_type == "diagnosis" and l.diagnosis_id.zoonotic:
                note = "Zoonotic – use PPE, inform owner."
                if l.diagnosis_id.notifiable:
                    note += " Notifiable disease."
                l.warning = note

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------
    def _check_can_decide(self):
        if not self.env.user.has_group("stratos_vet_case_memory.group_vet_cm_vet"):
            raise UserError(_("Only a veterinarian can approve or reject suggestions."))
        for l in self:
            if l.case_id.state != "draft":
                raise UserError(_("Case %s is finalised; decisions are closed.", l.case_id.name))
            if l.decision != "pending":
                raise UserError(_("'%s' has already been decided.", l.item_name))
            if l.blocked:
                raise UserError(_("'%s' is blocked for this species and cannot be approved.",
                                  l.item_name))

    def _apply_to_case(self):
        for l in self:
            case = l.case_id
            if l.item_type == "diagnosis":
                case.diagnosis_id = l.diagnosis_id
                if not case.assessment:
                    case.assessment = l.diagnosis_id.name
            elif l.item_type == "test":
                if l.test_id not in case.test_line_ids.test_id:
                    self.env["vet.cm.case.test"].create({
                        "case_id": case.id, "test_id": l.test_id.id, "from_suggestion": True})
            elif l.item_type == "drug":
                self.env["vet.cm.case.treatment"].create({
                    "case_id": case.id, "drug_id": l.drug_id.id,
                    "dose_mgkg": l.final_mgkg, "frequency": l.final_frequency,
                    "days": l.final_days, "from_suggestion": True})

    def _decide(self, decision, reason=False, reason_type=False):
        now = fields.Datetime.now()
        for l in self:
            l.write({"decision": decision, "decided_by": self.env.user.id,
                     "decided_on": now, "reject_reason": reason or False})
            pat = l.pattern_id or (l.case_id.species_id and self.env["vet.cm.pattern"]._get(
                l.case_id.species_id, l.item_type, l.diagnosis_id or l.test_id or l.drug_id))
            pat._register_decision(decision, reason_type)
            label = dict(self._fields["decision"].selection)[decision]
            body = _("%(label)s: %(item)s (%(type)s, %(conf)s%% confidence)",
                     label=label, item=l.item_name,
                     type=dict(self._fields["item_type"].selection)[l.item_type],
                     conf=l.confidence)
            if decision == "modified" and l.item_type == "drug":
                body += _(" – changed to %s", l.dose_display)
            if reason:
                body += _(" – reason: %s", reason)
            l.case_id.message_post(body=body)

    def action_approve(self):
        self._check_can_decide()
        changed = self.filtered(lambda l: l.item_type == "drug" and (
            abs(l.final_mgkg - l.dose_mgkg) > 1e-6 or l.final_frequency != l.frequency
            or l.final_days != l.days))
        self._apply_to_case()
        (self - changed)._decide("approved")
        changed._decide("modified")
        return True

    def action_modify(self):
        self.ensure_one()
        self._check_can_decide()
        return {
            "type": "ir.actions.act_window", "name": _("Modify suggestion"),
            "res_model": self._name, "res_id": self.id, "view_mode": "form",
            "views": [(self.env.ref("stratos_vet_case_memory.view_vet_cm_suggestion_line_modify").id,
                       "form")],
            "target": "new",
        }

    def action_confirm_modify(self):
        self._check_can_decide()
        self._compute_safety()
        if self.filtered("blocked"):
            raise UserError(_("This drug is blocked for this species."))
        self._apply_to_case()
        self._decide("modified")
        return {"type": "ir.actions.act_window_close"}

    def action_reject(self):
        self._check_can_decide()
        return {
            "type": "ir.actions.act_window", "name": _("Reject suggestion"),
            "res_model": "vet.cm.reject.wizard", "view_mode": "form", "target": "new",
            "context": {"default_line_ids": [(6, 0, self.ids)]},
        }

    def action_open_case(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "res_model": "vet.cm.case",
                "res_id": self.case_id.id, "view_mode": "form", "views": [(False, "form")]}
