from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged

@tagged("post_install", "-at_install")
class TestVetInventory(TransactionCase):
 def test_medication_onchange_enables_traceability(self):
  product=self.env["product.template"].new({"name":"Test Medication","is_vet_item":True,"vet_item_type":"medication"}); product._onchange_vet_inventory_type(); self.assertTrue(product.is_storable); self.assertEqual(product.tracking,"lot"); self.assertTrue(product.use_expiration_date); self.assertTrue(product.vet_print_label)
 def test_service_onchange_disables_stock(self):
  product=self.env["product.template"].new({"name":"Test Service","is_vet_item":True,"vet_item_type":"service","is_storable":True}); product._onchange_vet_inventory_type(); self.assertFalse(product.is_storable); self.assertEqual(product.tracking,"none")
 def test_invalid_dose_range(self):
  with self.assertRaises(ValidationError): self.env["product.template"].create({"name":"Invalid Dose","is_vet_item":True,"vet_item_type":"medication","vet_dose_min":10,"vet_dose_max":5})
 def test_invalid_stock_range(self):
  with self.assertRaises(ValidationError): self.env["product.template"].create({"name":"Invalid Stock","is_vet_item":True,"vet_item_type":"supply","vet_reorder_min":20,"vet_reorder_max":10})
