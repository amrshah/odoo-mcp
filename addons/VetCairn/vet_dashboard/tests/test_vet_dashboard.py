from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestVetDashboard(TransactionCase):
    def test_dashboard_payload_and_navigation(self):
        payload = self.env["vet.dashboard"].get_dashboard_data()
        self.assertTrue({"metrics", "charts", "quick_actions", "generated_at", "company"} <= payload.keys())
        self.assertIn("Appointments Today", {metric["label"] for metric in payload["metrics"]})
        self.assertEqual(len(payload["charts"]), 3)
        self.assertTrue(payload["quick_actions"])
        menu = self.env.ref("vet_dashboard.menu_vet_dashboard")
        action = self.env.ref("vet_dashboard.action_vet_dashboard")
        self.assertEqual(menu.sequence, 1)
        self.assertEqual(action.tag, "vetcairn.dashboard")
