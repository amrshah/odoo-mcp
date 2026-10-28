import re

from odoo import _, fields, models
from odoo.exceptions import UserError

R = "stratos_vet_case_memory."

# Subjective / History fields that are themselves a clinical sign
HISTORY_SIGNS = {
    "Vomiting": "sym_vomiting",
    "Diarrhea": "sym_diarrhoea",
    "Sneezing": "sym_sneezing",
    "Coughing": "sym_cough",
    "Shaking Head": "sym_head_shaking",
    "Scratching Ears": "sym_pruritus",
    "Odor in Ears": "sym_ear_discharge",
    "Lameness": "sym_lameness",
    "Trouble Breathing": "sym_dyspnoea",
    "Tires Easily or Faints": "sym_lethargy",
    "Parasites": "sym_fleas",
}
NEGATIVE = {"no", "none", "nil", "normal", "negative", "absent", "n/a", "na", "-",
            "within normal limits", "wnl", "not seen", "not present"}
# keyword in species text -> vet.cm.species xml id
SPECIES_WORDS = [
    (("canine", "dog"), "sp_dog"), (("feline", "cat"), "sp_cat"),
    (("buffalo",), "sp_buffalo"), (("bovine", "cattle", "cow", "bull", "calf"), "sp_cattle"),
    (("caprine", "goat"), "sp_goat"), (("ovine", "sheep"), "sp_sheep"),
    (("equine", "horse", "donkey"), "sp_horse"), (("rabbit", "lagomorph"), "sp_rabbit"),
    (("poultry", "chicken", "hen"), "sp_poultry"), (("bird", "avian", "parrot"), "sp_bird"),
]
APPROVED_MARK = "— Approved via Clinical Suggestions —"


class VetExam(models.Model):
    _inherit = "vet.exam"

    cm_case_id = fields.Many2one("vet.cm.case", "Clinical case", copy=False, index=True,
                                 ondelete="set null", tracking=True)
    cm_case_state = fields.Selection(related="cm_case_id.state", string="Case status")
    cm_pending_count = fields.Integer("Pending suggestions", compute="_compute_cm_pending")
    cm_diagnosis_id = fields.Many2one(related="cm_case_id.diagnosis_id", string="Case diagnosis")

    def _compute_cm_pending(self):
        for exam in self:
            exam.cm_pending_count = exam.cm_case_id.pending_line_count if exam.cm_case_id else 0

    # ------------------------------------------------------------------
    # Reading the exam
    # ------------------------------------------------------------------
    def _cm_species(self):
        """Map the exam's species (VetCairn species if installed) to our species."""
        self.ensure_one()
        texts = []
        if "species_id" in self._fields and self.species_id:
            texts.append(self.species_id.display_name or "")
            if "code" in self.species_id._fields and self.species_id.code:
                texts.append(self.species_id.code)
        if self.species and self.species != "general":
            texts.append(dict(self._fields["species"].selection).get(self.species, self.species))
        text = " ".join(texts).lower()
        for words, xid in SPECIES_WORDS:
            if any(w in text for w in words):
                return self.env.ref(R + xid, raise_if_not_found=False)
        if text:
            sp = self.env["vet.cm.species"].search([("name", "ilike", text.split()[0])], limit=1)
            if sp:
                return sp
        return self.env["vet.cm.species"]

    @staticmethod
    def _cm_line_positive(line):
        parts = [(line.value or "").strip().lower(), (line.note or "").strip().lower(),
                 (line.status_id.name or "").strip().lower()]
        parts = [p for p in parts if p]
        if not parts:
            return False
        return not all(p in NEGATIVE or p.startswith(("no ", "none", "normal")) for p in parts)

    def _cm_vitals(self):
        self.ensure_one()
        out = {}
        for line in self.line_ids.filtered(
                lambda l: l.section_name == "Objective" and l.group_path == "Vital Signs" and l.value):
            try:
                num = float(line.value.replace(",", "."))
            except ValueError:
                continue
            unit = (line.unit_option_id.name or line.unit or "").lower()
            if line.name == "Temperature":
                out["temperature"] = round((num - 32) * 5 / 9, 1) if (unit == "f" or num > 45) else num
            elif line.name == "Weight":
                out["weight_kg"] = round(num * 0.45359237, 2) if unit == "lb" else num
            elif line.name == "Heartrate":
                out["heart_rate"] = int(round(num))
            elif line.name == "Respiration":
                out["resp_rate"] = int(round(num))
        return out

    def _cm_section_text(self, section):
        self.ensure_one()
        rows = []
        for line in self.line_ids.filtered(lambda l: l.has_data and l.section_name == section):
            if section == "Objective" and line.group_path == "Vital Signs":
                continue
            bits = [b for b in (line.status_id.name, line.value_text, line.note) if b]
            rows.append(f"{line.name}: {' – '.join(bits)}")
        return "\n".join(rows)

    def _cm_symptoms(self, species):
        self.ensure_one()
        Sym = self.env["vet.cm.symptom"]
        found = Sym.browse()
        texts = []
        for line in self.line_ids.filtered("has_data"):
            if line.section_name not in ("Subjective", "Objective", "Diagnostics"):
                continue
            positive = self._cm_line_positive(line)
            if line.section_name == "Subjective" and line.name in HISTORY_SIGNS and positive:
                sym = self.env.ref(R + HISTORY_SIGNS[line.name], raise_if_not_found=False)
                if sym:
                    found |= sym
            if positive:
                texts.append(" ".join(b for b in (line.value, line.note, line.status_id.name) if b))
        found |= Sym._detect_in_text("\n".join(texts), species)
        vit = self._cm_vitals()
        if vit.get("temperature", 0) >= 39.5:
            found |= self.env.ref(R + "sym_fever")
        return found

    def _cm_case_vals(self, species=False):
        self.ensure_one()
        species = species or self._cm_species()
        vals = {
            "animal_name": self.patient_name,
            "owner_id": self.owner_id.id,
            "vet_id": self.vet_id.id or self.env.user.id,
            "species_id": species.id,
            "symptom_ids": self._cm_symptoms(species).ids,
        }
        subj, obj = self._cm_section_text("Subjective"), self._cm_section_text("Objective")
        if subj:
            vals["subjective"] = subj
        if obj:
            vals["objective"] = obj
        vals.update(self._cm_vitals())
        return vals

    # ------------------------------------------------------------------
    # Case link
    # ------------------------------------------------------------------
    def _cm_ensure_case(self):
        """Return the linked case, creating it from the exam if needed.
        Returns False when the species cannot be determined."""
        self.ensure_one()
        if self.cm_case_id:
            if self.cm_case_id.state == "draft":
                self.cm_case_id._sync_from_exam(self)
            return self.cm_case_id
        species = self._cm_species()
        if not species:
            return False
        vals = self._cm_case_vals(species)
        vals["symptom_ids"] = [(6, 0, vals["symptom_ids"])]
        case = self.env["vet.cm.case"].create(vals)
        self.cm_case_id = case
        case.message_post(body=_("Created from SOAP exam %s.", self.name))
        return case

    def _cm_new_case_form(self):
        """Species unknown (e.g. 'General' template for livestock): let the vet pick it."""
        self.ensure_one()
        vals = self._cm_case_vals(species=self.env["vet.cm.species"])
        ctx = {f"default_{k}": v for k, v in vals.items() if k not in ("species_id", "symptom_ids")}
        ctx["default_symptom_ids"] = [(6, 0, vals["symptom_ids"])]
        ctx["vet_cm_link_exam_id"] = self.id
        return {
            "type": "ir.actions.act_window", "name": _("Clinical case – choose species"),
            "res_model": "vet.cm.case", "view_mode": "form", "views": [(False, "form")],
            "target": "current", "context": ctx,
        }

    def action_cm_open_case(self):
        self.ensure_one()
        case = self._cm_ensure_case()
        if not case:
            return self._cm_new_case_form()
        return {"type": "ir.actions.act_window", "res_model": "vet.cm.case", "res_id": case.id,
                "view_mode": "form", "views": [(False, "form")]}

    def action_cm_get_suggestions(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("The exam is completed. Re-open it to run suggestions."))
        case = self._cm_ensure_case()
        if not case:
            return self._cm_new_case_form()
        if case.state != "draft":
            raise UserError(_("Clinical case %s is finalised.", case.name))
        return case.action_get_suggestions()

    def add_voice_note(self, transcript, lang="en-US", duration=0):
        """Voice widget on the exam form: the note is kept in the case history."""
        self.ensure_one()
        case = self._cm_ensure_case()
        if not case:
            raise UserError(_("Set the species on the exam first, or open the clinical case "
                              "and dictate there."))
        note_id = case.add_voice_note(transcript, lang, duration)
        self.message_post(body=_("Voice note recorded (%s). Review it in the clinical case.",
                                 case.name))
        return note_id

    # ------------------------------------------------------------------
    # Writing back: A and P
    # ------------------------------------------------------------------
    def _cm_target_line(self, section, group, name):
        self.ensure_one()
        line = self.line_ids.filtered(
            lambda l: l.section_name == section and (l.group_path or "") == group and l.name == name)[:1]
        if line:
            return line
        node = self.env["vet.exam.node"].search(
            [("complete_name", "=", f"{section} / {group} / {name}"), ("node_type", "=", "field")],
            limit=1)
        return self.env["vet.exam.line"].create({
            "exam_id": self.id, "node_id": node.id, "section_name": section,
            "group_path": group, "name": name, "field_type": "note", "include_note": True,
            "big_note": True, "sequence": 90000,
        })

    @staticmethod
    def _cm_merge(note, block):
        note = note or ""
        if APPROVED_MARK in note:
            note = note[:note.index(APPROVED_MARK)].rstrip()
        return (note + "\n\n" if note else "") + APPROVED_MARK + "\n" + block

    def action_cm_send_plan(self):
        for exam in self:
            case = exam.cm_case_id
            if not case:
                raise UserError(_("No clinical case linked yet. Use 'Clinical Suggestions' first."))
            if exam.state != "draft":
                raise UserError(_("Re-open the exam to update its Assessment and Plan."))
            if not (case.diagnosis_id or case.test_line_ids or case.treatment_line_ids):
                raise UserError(_("Nothing approved yet on case %s.", case.name))
            if case.diagnosis_id:
                diag = case.diagnosis_id.name
                if case.diagnosis_id.zoonotic:
                    diag += " (ZOONOTIC – PPE, inform owner)"
                if case.diagnosis_id.notifiable:
                    diag += " (notifiable)"
                line = exam._cm_target_line("Assessment", "Diagnoses", "Diagnoses")
                line.note = exam._cm_merge(line.note, diag)
            rows = []
            for t in case.test_line_ids:
                rows.append(f"• Test: {t.test_id.name}")
            for tl in case.treatment_line_ids:
                if tl.dose_basis == "per_kg":
                    dose = f"{tl.dose_mgkg:g} mg/kg = {tl.total_mg:.1f} mg"
                else:
                    dose = tl.fixed_dose or ""
                route = dict(tl.drug_id._fields["route"].selection).get(tl.route, "")
                row = f"• {tl.drug_id.name}: {dose}, {route}, {tl.frequency or ''} × {tl.days or 0} d"
                if case.species_id.food_producing and (tl.drug_id.withdrawal_milk_days
                                                       or tl.drug_id.withdrawal_meat_days):
                    row += (f" [withdrawal: milk {tl.drug_id.withdrawal_milk_days} d, "
                            f"meat {tl.drug_id.withdrawal_meat_days} d]")
                rows.append(row)
            if rows:
                line = exam._cm_target_line("Plan", "Notes", "Notes")
                line.note = exam._cm_merge(line.note, "\n".join(rows))
            exam.message_post(body=_("Approved assessment and plan written from case %s.",
                                     case.name))
        return True

    def action_done(self):
        res = super().action_done()
        is_vet = self.env.user.has_group(R + "group_vet_cm_vet")
        for exam in self.filtered(lambda e: e.cm_case_id.state == "draft"):
            case = exam.cm_case_id
            if case.diagnosis_id and is_vet:
                case.action_finalise()
            else:
                case.message_post(body=_(
                    "SOAP exam %s completed. The case stays open until a vet sets the "
                    "diagnosis and finalises it.", exam.name))
        return res
