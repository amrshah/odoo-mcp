from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestVetInstaller(TransactionCase):
    def test_complete_suite_is_installed(self):
        expected = {
            "vet_base", "vet_appointment", "vet_clinical", "vet_vaccination",
            "vet_diagnostic", "vet_prescription", "vet_inventory", "vet_billing",
            "vet_documents", "vet_reminder", "vet_reporting", "vet_treatment",
            "vet_commercial", "vet_procurement", "vet_dashboard", "vet_task",
            "vet_communication", "vet_settings", "vet_completion",
        }
        modules = self.env["ir.module.module"].search([("name", "in", list(expected))])
        self.assertEqual(set(modules.mapped("name")), expected)
        self.assertFalse(modules.filtered(lambda module: module.state != "installed"))

    def test_core_suite_models_are_available(self):
        for model_name in (
            "vet.patient", "vet.appointment", "vet.encounter", "vet.prescription",
            "vet.charge", "vet.task", "vet.communication", "vet.admission",
            "vet.insurance.claim", "vet.migration.batch",
        ):
            self.assertIn(model_name, self.env)
