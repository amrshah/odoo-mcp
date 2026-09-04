from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestVetCommercial(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls.clinic = cls.env["vet.clinic"].create({"name":"Estimate Test Clinic","code":"EST-TEST","company_id":company.id})
        species = cls.env["vet.species"].create({"name":"Estimate Test Species","code":"EST-TEST-SPECIES"})
        cls.client = cls.env["res.partner"].create({"name":"Estimate Test Client"})
        cls.patient = cls.env["vet.patient"].create({"name":"Estimate Test Patient","clinic_id":cls.clinic.id,"company_id":company.id,"species_id":species.id,"ownership_ids":[(0,0,{"partner_id":cls.client.id,"is_primary":True})]})
        cls.product = cls.env["product.product"].create({"name":"Estimate Test Service","list_price":100.0})

    def _values(self, **extra):
        values = {"partner_id":self.client.id,"is_vet_estimate":True,"vet_patient_id":self.patient.id,"vet_clinic_id":self.clinic.id,"order_line":[(0,0,{"product_id":self.product.id,"product_uom_qty":1,"price_unit":100.0,"discount":10.0})]}
        values.update(extra)
        return values

    def test_estimate_amount_and_deposit(self):
        estimate = self.env["sale.order"].create(self._values(vet_deposit_percent=50))
        self.assertEqual(estimate.amount_total, 90.0)
        self.assertEqual(estimate.vet_deposit_amount, 45.0)
        self.assertEqual(estimate.order_line.discount, 10.0)

    def test_client_acceptance(self):
        estimate = self.env["sale.order"].create(self._values(vet_approved_by_name="Estimate Test Client"))
        estimate.action_vet_accept()
        self.assertEqual(estimate.vet_approval_state, "accepted")
        self.assertTrue(estimate.vet_approved_at)

    def test_unapproved_estimate_cannot_confirm(self):
        estimate = self.env["sale.order"].create(self._values())
        with self.assertRaises(UserError):
            estimate.action_confirm()

    def test_invalid_deposit(self):
        with self.assertRaises(ValidationError):
            self.env["sale.order"].create(self._values(vet_deposit_percent=120))

    def test_invoice_context_is_prepared(self):
        estimate = self.env["sale.order"].create(self._values())
        values = estimate._prepare_invoice()
        self.assertEqual(values["vet_patient_id"], self.patient.id)
        self.assertEqual(values["vet_clinic_id"], self.clinic.id)
        self.assertEqual(values["vet_estimate_id"], estimate.id)
