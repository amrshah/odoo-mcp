import json
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

VITAL_PATTERNS = {
    "temperature": r"(?:temperature|temp|bukhar|tapman)\D{0,15}?(\d{2,3}(?:[.,]\d)?)",
    "weight_kg": r"(?:weight|weighs|wazan|wazn)\D{0,15}?(\d{1,4}(?:[.,]\d+)?)\s*(kg|kilo|kilogram|lb|lbs|pound)?",
    "heart_rate": r"(?:heart rate|heartrate|pulse|dhadkan|hr)\D{0,15}?(\d{2,3})",
    "resp_rate": r"(?:respiratory rate|resp rate|respiration|breathing rate|saans|rr)\D{0,15}?(\d{1,3})",
}


class VetCmVoiceNote(models.Model):
    _name = "vet.cm.voice.note"
    _description = "Voice Note (clinical history)"
    _order = "create_date desc, id desc"
    _rec_name = "display_title"

    case_id = fields.Many2one("vet.cm.case", required=True, ondelete="cascade", index=True)
    case_state = fields.Selection(related="case_id.state", string="Case status")
    species_id = fields.Many2one(related="case_id.species_id", store=True)
    user_id = fields.Many2one("res.users", "Spoken by", default=lambda s: s.env.user, readonly=True)
    language = fields.Selection([
        ("en-US", "English"), ("en-GB", "English (UK)"), ("ur-PK", "Urdu"),
    ], default="en-US")
    duration_sec = fields.Integer("Duration (s)", readonly=True)
    transcript = fields.Text(required=True)
    display_title = fields.Char(compute="_compute_title")

    matched_symptom_ids = fields.Many2many("vet.cm.symptom", string="Symptoms heard")
    new_symptom_ids = fields.Many2many("vet.cm.symptom", "vet_cm_voice_new_symptom_rel",
                                       string="New for this case",
                                       compute="_compute_new_symptoms")
    temperature = fields.Float("Temperature heard (°C)", digits=(16, 1))
    weight_kg = fields.Float("Weight heard (kg)", digits=(16, 2))
    heart_rate = fields.Integer("Heart rate heard")
    resp_rate = fields.Integer("Resp. rate heard")

    ai_subjective = fields.Text("AI – Subjective")
    ai_objective = fields.Text("AI – Objective")
    ai_assessment = fields.Text("AI – Assessment")
    ai_plan = fields.Text("AI – Plan")
    ai_done = fields.Boolean(readonly=True)

    state = fields.Selection([
        ("proposed", "To confirm"), ("applied", "Applied to case"), ("kept", "Kept as history"),
    ], default="proposed", readonly=True)
    applied_by = fields.Many2one("res.users", readonly=True)
    applied_on = fields.Datetime(readonly=True)

    def _compute_title(self):
        for n in self:
            when = fields.Datetime.context_timestamp(n, n.create_date).strftime(
                "%d %b %Y %H:%M") if n.create_date else ""
            n.display_title = f"{n.case_id.name or ''} · {when} · {n.user_id.name or ''}"

    @api.depends("matched_symptom_ids", "case_id.symptom_ids")
    def _compute_new_symptoms(self):
        for n in self:
            n.new_symptom_ids = n.matched_symptom_ids - n.case_id.symptom_ids

    def write(self, vals):
        if "transcript" in vals and not self.env.context.get("vet_cm_force_write"):
            raise UserError(_("A voice transcript is part of the clinical record and "
                              "cannot be edited. Record a new note instead."))
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group("stratos_vet_case_memory.group_vet_cm_manager"):
            raise UserError(_("Only a senior vet can delete clinical voice history."))
        return super().unlink()

    # ------------------------------------------------------------------
    def _extract(self):
        """Rule-based extraction: symptoms from keywords, vitals from numbers."""
        for n in self:
            text = " " + (n.transcript or "").lower().replace("\n", " ") + " "
            found = self.env["vet.cm.symptom"]._detect_in_text(text, n.case_id.species_id)
            vals = {"matched_symptom_ids": [(6, 0, found.ids)]}
            for field, pattern in VITAL_PATTERNS.items():
                m = re.search(pattern, text)
                if not m:
                    continue
                num = float(m.group(1).replace(",", "."))
                if field == "temperature":
                    if num > 45:  # spoken in °F
                        num = round((num - 32) * 5 / 9, 1)
                    if not 30 <= num <= 45:
                        continue
                elif field == "weight_kg":
                    unit = (m.group(2) or "").lower()
                    if unit in ("lb", "lbs", "pound"):
                        num = round(num * 0.4536, 2)
                vals[field] = num
            fever = self.env.ref("stratos_vet_case_memory.sym_fever", raise_if_not_found=False)
            if fever and vals.get("temperature", 0) >= 39.5 and fever not in found:
                vals["matched_symptom_ids"] = [(6, 0, (found | fever).ids)]
            n.write(vals)

    def action_apply(self):
        """Vet confirms: heard symptoms and vitals go into the case."""
        if not self.env.user.has_group("stratos_vet_case_memory.group_vet_cm_vet"):
            raise UserError(_("Only a veterinarian can apply dictation to the case."))
        for n in self:
            case = n.case_id
            if case.state != "draft":
                raise UserError(_("The case is finalised; this note stays as history only."))
            vals = {"symptom_ids": [(4, s.id) for s in n.matched_symptom_ids]}
            for f in ("temperature", "weight_kg", "heart_rate", "resp_rate"):
                if n[f]:
                    vals[f] = n[f]
            if n.ai_done:
                for src, dst in (("ai_subjective", "subjective"), ("ai_objective", "objective"),
                                 ("ai_assessment", "assessment"), ("ai_plan", "plan")):
                    if n[src]:
                        vals[dst] = ((case[dst] + "\n") if case[dst] else "") + n[src]
            else:
                vals["subjective"] = ((case.subjective + "\n") if case.subjective else "") + \
                    n.transcript
            case.write(vals)
            n.write({"state": "applied", "applied_by": self.env.user.id,
                     "applied_on": fields.Datetime.now()})
            case.message_post(body=_(
                "Voice note applied by %(user)s: %(n)s symptom(s) added.",
                user=self.env.user.name, n=len(n.matched_symptom_ids)))
        return True

    def action_keep(self):
        self.write({"state": "kept"})
        return True

    def action_structure_ai(self):
        client = self.env["vet.cm.ai.client"]
        names = self.env["vet.cm.symptom"].search([]).mapped("name")
        for n in self:
            system = (
                "You turn a veterinarian's spoken consultation notes into a SOAP record. "
                "Reply ONLY with JSON: {\"subjective\":str,\"objective\":str,"
                "\"assessment\":str,\"plan\":str,\"symptoms\":[str]}. Use only what was "
                "said; do not invent findings. 'symptoms' must be chosen from this list: "
                + ", ".join(names))
            raw = client._complete(system, n.transcript, json_mode=True,
                                   mock_payload=n._mock_soap())
            try:
                data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            except ValueError:
                raise UserError(_("The AI reply could not be read:\n%s", raw[:500]))
            syms = self.env["vet.cm.symptom"].search(
                [("name", "in", data.get("symptoms") or [])])
            n.write({
                "ai_subjective": data.get("subjective"), "ai_objective": data.get("objective"),
                "ai_assessment": data.get("assessment"), "ai_plan": data.get("plan"),
                "ai_done": True,
                "matched_symptom_ids": [(4, s.id) for s in syms],
            })
        return True

    def _mock_soap(self):
        """Deterministic SOAP split used in mock mode (demos without an API key)."""
        self.ensure_one()
        sentences = [s.strip() for s in re.split(r"[.!?\n]+", self.transcript or "") if s.strip()]
        subj, obj, ass, plan = [], [], [], []
        for s in sentences:
            low = s.lower()
            if any(k in low for k in ("temperature", "temp", "heart", "pulse", "weight",
                                      "gums", "palpation", "on exam", "examination")):
                obj.append(s)
            elif any(k in low for k in ("suspect", "likely", "diagnos", "rule out", "looks like")):
                ass.append(s)
            elif any(k in low for k in ("give", "start", "plan", "test", "recheck", "fluids",
                                        "prescribe", "advise")):
                plan.append(s)
            else:
                subj.append(s)
        return json.dumps({
            "subjective": ". ".join(subj), "objective": ". ".join(obj),
            "assessment": ". ".join(ass), "plan": ". ".join(plan),
            "symptoms": self.matched_symptom_ids.mapped("name"),
        })
