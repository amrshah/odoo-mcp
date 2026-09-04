from odoo import fields, models


class VetPatient(models.Model):
    _inherit = "vet.patient"

    task_ids = fields.One2many("vet.task", "patient_id", string="Tasks")
    open_task_count = fields.Integer(compute="_compute_open_task_count")

    def _compute_open_task_count(self):
        grouped = self.env["vet.task"]._read_group([("patient_id", "in", self.ids), ("state", "in", ("draft", "open", "in_progress", "blocked"))], ["patient_id"], ["__count"])
        counts = {patient.id: count for patient, count in grouped}
        for patient in self:
            patient.open_task_count = counts.get(patient.id, 0)

    def action_view_tasks(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("vet_task.action_vet_task")
        action["domain"] = [("patient_id", "=", self.id)]
        action["context"] = {"default_patient_id": self.id, "default_clinic_id": self.clinic_id.id, "default_company_id": self.company_id.id}
        return action
