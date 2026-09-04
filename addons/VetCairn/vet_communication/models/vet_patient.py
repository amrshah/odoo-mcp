from odoo import fields, models


class VetPatient(models.Model):
    _inherit = "vet.patient"

    communication_ids = fields.One2many("vet.communication", "patient_id", string="Communications")
    communication_count = fields.Integer(compute="_compute_communication_count")

    def _compute_communication_count(self):
        data = self.env["vet.communication"]._read_group([("patient_id", "in", self.ids)], ["patient_id"], ["__count"])
        counts = {patient.id: count for patient, count in data}
        for patient in self:
            patient.communication_count = counts.get(patient.id, 0)

    def action_view_communications(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("vet_communication.action_vet_communication")
        action["domain"] = [("patient_id", "=", self.id)]
        action["context"] = {"default_patient_id": self.id, "default_client_id": self.primary_owner_id.id, "default_clinic_id": self.clinic_id.id, "default_company_id": self.company_id.id}
        return action
