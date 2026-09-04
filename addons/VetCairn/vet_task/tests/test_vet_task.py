from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestVetTask(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.clinic = cls.env["vet.clinic"].create({"name": "Task Test Clinic", "code": "TTC", "company_id": cls.env.company.id})
        cls.task_type = cls.env["vet.task.type"].create({"name": "Test Follow-up", "code": "TEST", "company_id": cls.env.company.id})

    def _task(self, **extra):
        values = {"title": "Call client with result", "clinic_id": self.clinic.id, "task_type_id": self.task_type.id, "assigned_user_id": self.env.user.id, "due_datetime": fields.Datetime.now() + timedelta(hours=1)}
        values.update(extra)
        return self.env["vet.task"].create(values)

    def test_task_workflow_and_required_checklist(self):
        task = self._task(checklist_line_ids=[(0, 0, {"name": "Verify result", "is_required": True})])
        task.action_open()
        task.action_start()
        with self.assertRaises(ValidationError):
            task.action_done()
        task.checklist_line_ids.write({"is_done": True})
        task.action_done()
        self.assertEqual(task.state, "done")
        self.assertEqual(task.checklist_progress, 100)
        self.assertTrue(task.completed_by_id)

    def test_overdue_and_dashboard(self):
        task = self._task(due_datetime=fields.Datetime.now() - timedelta(hours=1))
        task.action_open()
        self.assertTrue(task.is_overdue)
        dashboard = self.env["vet.dashboard"].get_dashboard_data()
        self.assertIn("Overdue Tasks", {metric["label"] for metric in dashboard["metrics"]})
        self.assertIn("Tasks", {item["label"] for item in dashboard["quick_actions"]})
