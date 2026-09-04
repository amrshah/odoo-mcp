from odoo import fields, models


class VetAppointment(models.Model):
    _inherit = "vet.appointment"

    encounter_id = fields.Many2one(
        "vet.encounter", compute="_compute_encounter", string="Clinical Encounter"
    )
    encounter_count = fields.Integer(compute="_compute_encounter")

    def _compute_encounter(self):
        encounters = self.env["vet.encounter"].search([("appointment_id", "in", self.ids)])
        by_appointment = {encounter.appointment_id.id: encounter for encounter in encounters}
        for appointment in self:
            appointment.encounter_id = by_appointment.get(appointment.id)
            appointment.encounter_count = int(bool(appointment.encounter_id))

    def _get_or_create_encounter(self):
        self.ensure_one()
        encounter = self.env["vet.encounter"].search(
            [("appointment_id", "=", self.id)], limit=1
        )
        if not encounter:
            encounter = self.env["vet.encounter"].create(
                {"appointment_id": self.id, "chief_complaint": self.reason}
            )
        return encounter

    def action_start(self):
        result = super().action_start()
        for appointment in self:
            encounter = appointment._get_or_create_encounter()
            if encounter.state == "draft":
                encounter.action_start()
        return result

    def action_complete(self):
        result = super().action_complete()
        for appointment in self:
            encounter = appointment._get_or_create_encounter()
            if encounter.state in ("draft", "in_progress"):
                encounter.action_complete()
        return result

    def action_open_encounter(self):
        self.ensure_one()
        encounter = self._get_or_create_encounter()
        return {
            "type": "ir.actions.act_window",
            "name": encounter.display_name,
            "res_model": "vet.encounter",
            "res_id": encounter.id,
            "view_mode": "form",
            "target": "current",
        }
