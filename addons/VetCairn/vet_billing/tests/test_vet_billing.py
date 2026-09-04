from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

@tagged("post_install", "-at_install")
class TestVetBilling(TransactionCase):
 @classmethod
 def setUpClass(cls):
  super().setUpClass(); c=cls.env.company; cls.clinic=cls.env["vet.clinic"].create({"name":"Billing Test Clinic","code":"BILL-TEST","company_id":c.id}); s=cls.env["vet.species"].create({"name":"Billing Test Species","code":"BILL-TEST-SPECIES"}); partner=cls.env["res.partner"].create({"name":"Billing Client"}); cls.patient=cls.env["vet.patient"].create({"name":"Billing Patient","clinic_id":cls.clinic.id,"company_id":c.id,"species_id":s.id,"ownership_ids":[(0,0,{"partner_id":partner.id,"is_primary":True})]}); tmpl=cls.env["product.template"].create({"name":"Consultation Charge","is_vet_item":True,"vet_item_type":"service","list_price":75.0,"is_storable":False}); cls.product=tmpl.product_variant_id
 def vals(self,**x):
  v={"clinic_id":self.clinic.id,"patient_id":self.patient.id,"product_id":self.product.id,"description":"Consultation","quantity":1,"unit_price":75}; v.update(x); return v
 def test_defaults_and_subtotal(self):
  charge=self.env["vet.charge"].create(self.vals()); self.assertNotEqual(charge.name,"New"); self.assertEqual(charge.subtotal,75); self.assertEqual(charge.client_id,self.patient.primary_owner_id)
 def test_ready_workflow(self):
  charge=self.env["vet.charge"].create(self.vals()); charge.action_ready(); self.assertEqual(charge.state,"ready")
 def test_invalid_quantity(self):
  with self.assertRaises(ValidationError): self.env["vet.charge"].create(self.vals(quantity=0))
 def test_invalid_transition(self):
  charge=self.env["vet.charge"].create(self.vals())
  with self.assertRaises(UserError): charge.action_create_invoice()
