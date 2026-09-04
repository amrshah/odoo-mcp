from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestVetDiagnostic(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls.clinic = cls.env["vet.clinic"].create({"name": "DX Test Clinic", "code": "DX-TEST", "company_id": company.id})
        cls.species = cls.env["vet.species"].create({"name": "DX Test Species", "code": "DX-TEST-SPECIES"})
        client = cls.env["res.partner"].create({"name": "DX Test Client"})
        cls.patient = cls.env["vet.patient"].create({"name": "DX Test Patient", "clinic_id": cls.clinic.id, "company_id": company.id, "species_id": cls.species.id, "ownership_ids": [(0, 0, {"partner_id": client.id, "is_primary": True})]})
        cls.dx_type = cls.env["vet.diagnostic.type"].create({"name": "Complete Blood Count", "code": "DX-CBC-TEST", "category": "laboratory", "company_id": company.id, "specimen_required": True, "default_specimen": "Whole blood"})

    def _values(self, **extra):
        values = {"clinic_id": self.clinic.id, "patient_id": self.patient.id, "diagnostic_type_id": self.dx_type.id, "clinical_question": "Investigate lethargy"}
        values.update(extra)
        return values

    def test_defaults_and_sequence(self):
        order = self.env["vet.diagnostic.order"].create(self._values())
        self.assertNotEqual(order.name, "New")
        self.assertEqual(order.specimen, "Whole blood")
        self.assertEqual(order.client_id, self.patient.primary_owner_id)

    def test_full_lab_workflow(self):
        order = self.env["vet.diagnostic.order"].create(self._values())
        order.action_order(); order.action_collect(); order.action_start()
        order.result_summary = "CBC within reference intervals"
        order.action_complete()
        self.assertEqual(order.state, "completed")
        self.assertTrue(order.resulted_at)

    def test_result_required_for_completion(self):
        order = self.env["vet.diagnostic.order"].create(self._values())
        order.action_order()
        with self.assertRaises(ValidationError):
            order.action_complete()

    def test_specimen_required(self):
        order = self.env["vet.diagnostic.order"].create(self._values())
        order.specimen = False
        with self.assertRaises(ValidationError):
            order.action_order()

    def test_invalid_transition(self):
        order = self.env["vet.diagnostic.order"].create(self._values())
        with self.assertRaises(UserError):
            order.action_collect()
