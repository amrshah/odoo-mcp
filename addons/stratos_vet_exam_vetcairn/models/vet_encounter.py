from odoo import fields, models


class VetEncounter(models.Model):
    _inherit = "vet.encounter"

    exam_ids = fields.One2many("vet.exam", "encounter_id", "Structured Exams")
    exam_count = fields.Integer("Exams", compute="_compute_exam_count")

    def _compute_exam_count(self):
        for enc in self:
            enc.exam_count = len(enc.exam_ids)

    def action_structured_exam(self):
        """Open the encounter's exam, or start a new one pre-linked to it."""
        self.ensure_one()
        ctx = {
            "default_encounter_id": self.id,
            "default_patient_id": self.patient_id.id,
        }
        action = {
            "type": "ir.actions.act_window",
            "name": self.env._("Structured Exam"),
            "res_model": "vet.exam",
            "context": ctx,
        }
        if len(self.exam_ids) == 1:
            action.update(view_mode="form", res_id=self.exam_ids.id)
        elif self.exam_ids:
            action.update(view_mode="list,form", domain=[("encounter_id", "=", self.id)])
        else:
            action.update(view_mode="form", target="current")
        return action

    def action_new_structured_exam(self):
        self.ensure_one()
        action = self.action_structured_exam()
        action.update(view_mode="form", res_id=False, domain=False)
        return action
