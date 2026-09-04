from odoo import fields, models


class VetPatient(models.Model):
    _inherit = "vet.patient"

    encounter_count = fields.Integer(compute="_compute_encounter_count")

    def _compute_encounter_count(self):
        counts = self.env["vet.encounter"]._read_group(
            [("patient_id", "in", self.ids)], ["patient_id"], ["__count"]
        )
        count_by_patient = {patient.id: count for patient, count in counts}
        for patient in self:
            patient.encounter_count = count_by_patient.get(patient.id, 0)

    def action_view_encounters(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Clinical History — %s", self.display_name),
            "res_model": "vet.encounter",
            "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {"default_patient_id": self.id},
        }
