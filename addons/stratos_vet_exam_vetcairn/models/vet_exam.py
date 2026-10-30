from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError

# exam main heading -> encounter SOAP field (anything else goes to Objective)
SOAP_TARGET = {
    "Subjective": "subjective",
    "Objective": "objective",
    "Diagnostics": "objective",
    "Holistic": "objective",
    "Assessment": "assessment",
    "Plan": "plan",
    "Client Communication": "plan",
}
SOAP_ORDER = ["subjective", "objective", "assessment", "plan"]

# Objective / Vital Signs field -> (encounter field, unit choice)
VITALS = {
    "Heartrate": ("heart_rate", None),
    "Respiration": ("respiratory_rate", None),
    "Temperature": ("temperature_c", "°C"),
    "Weight": ("weight_kg", "Kg"),
}


class VetExam(models.Model):
    _inherit = "vet.exam"

    species = fields.Selection(string="Species (generic)")
    patient_id = fields.Many2one("vet.patient", "Patient", index=True, tracking=True,
                                 ondelete="restrict")
    patient_identifier = fields.Char(related="patient_id.identifier", string="Patient ID")
    encounter_id = fields.Many2one(
        "vet.encounter", "Clinical Encounter", index=True, tracking=True, ondelete="set null",
        domain="[('patient_id', '=', patient_id)] if patient_id else []",
    )
    encounter_state = fields.Selection(related="encounter_id.state", string="Encounter Status")
    species_id = fields.Many2one("vet.species", "Species", compute="_compute_from_patient",
                                 store=True, readonly=False, precompute=True)
    clinic_id = fields.Many2one("vet.clinic", "Clinic", compute="_compute_from_patient",
                                store=True, readonly=False, precompute=True)
    patient_name = fields.Char(compute="_compute_from_patient", store=True, readonly=False,
                               precompute=True)
    owner_id = fields.Many2one(compute="_compute_from_patient", store=True, readonly=False,
                               precompute=True)
    allowed_template_ids = fields.Many2many("vet.exam.template",
                                            compute="_compute_allowed_template_ids")
    sent_to_encounter_at = fields.Datetime("Sent to Encounter", readonly=True, copy=False)

    # ------------------------------------------------------------------
    @api.depends("patient_id", "encounter_id")
    def _compute_from_patient(self):
        for exam in self:
            patient, enc = exam.patient_id, exam.encounter_id
            exam.patient_name = patient.name or exam.patient_name
            exam.species_id = patient.species_id or exam.species_id
            exam.clinic_id = enc.clinic_id or patient.clinic_id or exam.clinic_id
            exam.owner_id = enc.client_id or patient.primary_owner_id or exam.owner_id

    @api.depends("species_id")
    def _compute_allowed_template_ids(self):
        templates = self.env["vet.exam.template"].search([])
        for exam in self:
            exam.allowed_template_ids = templates.filtered(
                lambda t: not t.species_ids or exam.species_id in t.species_ids)

    @api.onchange("encounter_id")
    def _onchange_encounter_id(self):
        if self.encounter_id.patient_id:
            self.patient_id = self.encounter_id.patient_id

    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        exams = super().create(vals_list)
        exams._prefill_vitals()
        return exams

    def write(self, vals):
        res = super().write(vals)
        if vals.get("encounter_id"):
            self._prefill_vitals()
        return res

    def _vital_lines(self):
        self.ensure_one()
        return self.line_ids.filtered(
            lambda l: l.section_name == "Objective" and l.group_path == "Vital Signs"
            and l.name in VITALS)

    def _prefill_vitals(self):
        """Copy triage vitals from the encounter into empty Vital Signs fields."""
        for exam in self.filtered(lambda e: e.encounter_id and e.state == "draft"):
            enc = exam.encounter_id
            for line in exam._vital_lines():
                enc_field, unit = VITALS[line.name]
                value = enc[enc_field]
                if not value or (line.value or "").strip():
                    continue
                vals = {"value": f"{value:g}"}
                if unit and line.node_id:
                    opt = line.node_id.unit_option_ids.filtered(
                        lambda o: o.name.lower() == unit.lower())[:1]
                    if opt:
                        vals["unit_option_id"] = opt.id
                line.write(vals)

    # ------------------------------------------------------------------
    def _sections_html(self, sections):
        out = Markup("")
        for sec in sections:
            out += Markup("<p><strong>%s</strong></p>") % sec["name"].upper()
            for grp in sec["groups"]:
                if grp["name"]:
                    out += Markup("<p><u>%s</u></p>") % grp["name"]
                items = Markup("").join(
                    Markup("<li><em>%s</em>: %s</li>") % (line.name, line._get_result_html())
                    for line in grp["lines"])
                out += Markup("<ul>%s</ul>") % items
        return out

    def action_send_to_encounter(self):
        for exam in self:
            enc = exam.encounter_id
            if not enc:
                raise UserError(self.env._("Link the exam to a clinical encounter first."))
            if enc.state == "locked":
                raise UserError(self.env._(
                    "Encounter %s is locked, so its notes cannot be changed.", enc.name))
            if exam.patient_id and enc.patient_id and exam.patient_id != enc.patient_id:
                raise UserError(self.env._("The exam and the encounter are for different patients."))
            buckets = {}
            for sec in exam._get_report_sections():
                buckets.setdefault(SOAP_TARGET.get(sec["name"], "objective"), []).append(sec)
            if not buckets:
                raise UserError(self.env._("No findings to send — fill some fields first."))
            header = Markup("<p><strong>Structured exam %s — %s</strong></p>") % (
                exam.name, exam.template_id.name)
            vals = {}
            for target in SOAP_ORDER:
                if target in buckets:
                    current = enc[target] or Markup("")
                    vals[target] = Markup(current) + header + exam._sections_html(buckets[target])
            # vitals back to triage, only where the encounter has none yet
            for line in exam._vital_lines():
                enc_field, _unit = VITALS[line.name]
                if enc[enc_field] or not line.value:
                    continue
                try:
                    number = float(line.value.replace(",", "."))
                except ValueError:
                    continue
                unit = (line.unit_option_id.name or "").lower()
                if enc_field == "temperature_c" and unit == "°f":
                    number = round((number - 32) * 5 / 9, 1)
                elif enc_field == "weight_kg" and unit == "lb":
                    number = round(number * 0.45359237, 2)
                vals[enc_field] = int(round(number)) if enc_field in ("heart_rate", "respiratory_rate") else number
            enc.write(vals)
            exam.sent_to_encounter_at = fields.Datetime.now()
            enc.message_post(body=self.env._("Findings added from structured exam %s.", exam.name))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Sent to encounter"),
                "message": self.env._("Findings were added to the encounter's SOAP notes."),
                "type": "success",
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }

    def action_open_encounter(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "vet.encounter",
            "res_id": self.encounter_id.id,
            "view_mode": "form",
        }
