from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    vet_communication_ids = fields.One2many("vet.communication", "client_id", string="Communications")
    vet_communication_count = fields.Integer(compute="_compute_vet_communication_count")

    def _compute_vet_communication_count(self):
        data = self.env["vet.communication"]._read_group([("client_id", "in", self.ids)], ["client_id"], ["__count"])
        counts = {partner.id: count for partner, count in data}
        for partner in self:
            partner.vet_communication_count = counts.get(partner.id, 0)

    def action_view_vet_communications(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("vet_communication.action_vet_communication")
        action["domain"] = [("client_id", "=", self.id)]
        action["context"] = {"default_client_id": self.id, "default_clinic_id": self.vet_preferred_clinic_id.id}
        return action
