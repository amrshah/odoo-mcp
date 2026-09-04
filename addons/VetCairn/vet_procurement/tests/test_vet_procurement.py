from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestVetProcurement(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls.clinic = cls.env["vet.clinic"].create({"name":"Procurement Test Clinic","code":"PO-TEST","company_id":company.id})
        cls.vendor = cls.env["res.partner"].create({"name":"Procurement Test Supplier","supplier_rank":1})
        cls.product = cls.env["product.product"].create({"name":"Controlled Test Stock","is_vet_item":True,"vet_item_type":"medication","vet_controlled":True,"is_storable":True,"tracking":"lot","standard_price":10.0})

    def _values(self, **extra):
        values = {"partner_id":self.vendor.id,"is_vet_purchase":True,"vet_clinic_id":self.clinic.id,"order_line":[(0,0,{"product_id":self.product.id,"product_qty":5,"price_unit":10.0})]}
        values.update(extra)
        return values

    def test_controlled_item_requires_review(self):
        order = self.env["purchase.order"].create(self._values())
        self.assertTrue(order.vet_controlled_item)
        self.assertEqual(order.vet_review_state, "pending")

    def test_controlled_order_cannot_confirm_unapproved(self):
        order = self.env["purchase.order"].create(self._values())
        with self.assertRaises(UserError):
            order.button_confirm()

    def test_manager_approval(self):
        order = self.env["purchase.order"].create(self._values())
        order.action_vet_approve()
        self.assertEqual(order.vet_review_state, "approved")
        self.assertTrue(order.vet_approved_at)

    def test_receipt_context_is_prepared(self):
        order = self.env["purchase.order"].create(self._values())
        values = order._prepare_picking()
        self.assertTrue(values["is_vet_receipt"])
        self.assertEqual(values["vet_clinic_id"], self.clinic.id)

    def test_veterinary_purchase_requires_clinic(self):
        with self.assertRaises(ValidationError):
            self.env["purchase.order"].create(self._values(vet_clinic_id=False))
