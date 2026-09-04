from odoo import fields, models


class VetPatient(models.Model):
    _inherit = "vet.patient"

    diagnostic_count = fields.Integer(compute="_compute_diagnostic_count")

    def _compute_diagnostic_count(self):
        counts = self.env["vet.diagnostic.order"]._read_group(
            [("patient_id", "in", self.ids)], ["patient_id"], ["__count"]
        )
        mapped = {patient.id: count for patient, count in counts}
        for patient in self:
            patient.diagnostic_count = mapped.get(patient.id, 0)

    def action_view_diagnostics(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": self.env._("Diagnostics — %s", self.display_name),
            "res_model": "vet.diagnostic.order", "view_mode": "list,form",
            "domain": [("patient_id", "=", self.id)],
            "context": {"default_patient_id": self.id, "default_clinic_id": self.clinic_id.id,
                        "default_company_id": self.company_id.id},
        }
