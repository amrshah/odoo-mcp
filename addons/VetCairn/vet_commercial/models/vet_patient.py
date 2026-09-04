from odoo import fields, models


class VetPatient(models.Model):
    _inherit = "vet.patient"

    estimate_count = fields.Integer(compute="_compute_estimate_count")

    def _compute_estimate_count(self):
        counts = self.env["sale.order"]._read_group([("vet_patient_id", "in", self.ids), ("is_vet_estimate", "=", True)], ["vet_patient_id"], ["__count"])
        mapped = {patient.id: count for patient, count in counts}
        for patient in self:
            patient.estimate_count = mapped.get(patient.id, 0)

    def action_view_estimates(self):
        self.ensure_one()
        return {"type":"ir.actions.act_window", "name":self.env._("Estimates — %s", self.display_name), "res_model":"sale.order", "view_mode":"list,kanban,form", "domain":[("vet_patient_id","=",self.id),("is_vet_estimate","=",True)], "context":{"default_is_vet_estimate":True,"default_vet_patient_id":self.id,"default_vet_clinic_id":self.clinic_id.id,"default_partner_id":self.primary_owner_id.id}}
