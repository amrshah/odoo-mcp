from odoo import fields, models


class VetPatient(models.Model):
    _inherit = "vet.patient"

    vaccination_count = fields.Integer(compute="_compute_vaccination_count")

    def _compute_vaccination_count(self):
        counts = self.env["vet.vaccination"]._read_group(
            [("patient_id", "in", self.ids)], ["patient_id"], ["__count"]
        )
        by_patient = {patient.id: count for patient, count in counts}
        for patient in self:
            patient.vaccination_count = by_patient.get(patient.id, 0)

    def action_view_vaccinations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Vaccinations — %s", self.display_name),
            "res_model": "vet.vaccination",
            "view_mode": "list,form,calendar",
            "domain": [("patient_id", "=", self.id)],
            "context": {
                "default_patient_id": self.id,
                "default_clinic_id": self.clinic_id.id,
                "default_company_id": self.company_id.id,
            },
        }
