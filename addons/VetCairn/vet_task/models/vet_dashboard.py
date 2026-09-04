from odoo import api, fields, models
from odoo.exceptions import AccessError


class VetDashboard(models.Model):
    _inherit = "vet.dashboard"

    @api.model
    def get_dashboard_data(self):
        data = super().get_dashboard_data()
        try:
            self.env["vet.task"].check_access("read")
            overdue = self.env["vet.task"].search_count([("is_overdue", "=", True)])
            data["metrics"].insert(1, self._metric("Overdue Tasks", overdue, "fa-tasks", "danger", "vet_task.action_vet_task_my_work"))
            data["charts"].append({"title": "Open Tasks by Status", "items": self._selection_chart("vet.task", "state", [("state", "in", ("open", "in_progress", "blocked"))]), "action": "vet_task.action_vet_task"})
            data["quick_actions"].insert(1, {"label": "Tasks", "icon": "fa-tasks", "action": "vet_task.action_vet_task_my_work"})
        except AccessError:
            pass
        data["generated_at"] = fields.Datetime.to_string(fields.Datetime.now())
        return data
