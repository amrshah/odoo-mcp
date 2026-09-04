from odoo import api, models
from odoo.exceptions import AccessError


class VetDashboard(models.Model):
    _inherit = "vet.dashboard"

    @api.model
    def get_dashboard_data(self):
        data = super().get_dashboard_data()
        try:
            model = self.env["vet.communication"]
            model.check_access("read")
            planned = model.search_count([("state", "in", ("planned", "failed"))])
            data["metrics"].append(self._metric("Communication Queue", planned, "fa-comments", "warning", "vet_communication.action_vet_communication_queue"))
            data["charts"].append({"title": "Communications by Channel", "items": self._selection_chart("vet.communication", "channel", []), "action": "vet_communication.action_vet_communication"})
            data["quick_actions"].append({"label": "Communications", "icon": "fa-comments", "action": "vet_communication.action_vet_communication"})
        except AccessError:
            pass
        return data
