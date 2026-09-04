from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestVetReporting(TransactionCase):
    def test_all_analysis_actions_exist(self):
        xmlids = ["action_vet_report_appointments", "action_vet_report_clinical", "action_vet_report_vaccinations", "action_vet_report_diagnostics", "action_vet_report_prescriptions", "action_vet_report_inventory", "action_vet_report_billing", "action_vet_report_reminders"]
        for xmlid in xmlids:
            action = self.env.ref(f"vet_reporting.{xmlid}")
            self.assertIn("pivot", action.view_mode)

    def test_report_views_are_valid(self):
        views = self.env["ir.ui.view"].search([("name", "like", "report.%")]) | self.env["ir.ui.view"].search([("name", "like", "%inventory.pivot")])
        self.assertTrue(views)
        for view in views.filtered(lambda item: item.model.startswith("vet.") or item.model == "product.template"):
            self.assertTrue(view.arch_db)

    def test_inventory_report_uses_aggregatable_stock_measures(self):
        action = self.env.ref("vet_reporting.action_vet_report_inventory")
        self.assertEqual(action.res_model, "stock.quant")
        self.assertFalse(action.search_view_id, "The old product search view must not remain on the stock quant action")
        pivot = self.env.ref("vet_reporting.view_vet_inventory_report_pivot")
        self.assertIn('name="quantity" type="measure"', pivot.arch_db)
        self.assertNotIn('name="qty_available" type="measure"', pivot.arch_db)
        self.env["stock.quant"]._read_group(
            [("product_id.is_vet_item", "=", True), ("location_id.usage", "=", "internal")],
            ["product_id"],
            ["quantity:sum", "reserved_quantity:sum"],
        )

    def test_printable_schedule_is_bound(self):
        report = self.env.ref("vet_reporting.action_report_vet_appointment_schedule")
        self.assertEqual(report.model, "vet.appointment")
        self.assertEqual(report.report_type, "qweb-pdf")
