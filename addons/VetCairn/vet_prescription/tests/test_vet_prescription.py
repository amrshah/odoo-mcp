from datetime import timedelta
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

@tagged("post_install", "-at_install")
class TestVetPrescription(TransactionCase):
 @classmethod
 def setUpClass(cls):
  super().setUpClass(); c=cls.env.company
  cls.clinic=cls.env["vet.clinic"].create({"name":"RX Test Clinic","code":"RX-TEST","company_id":c.id}); s=cls.env["vet.species"].create({"name":"RX Test Species","code":"RX-TEST-SPECIES"}); p=cls.env["res.partner"].create({"name":"RX Client"}); cls.patient=cls.env["vet.patient"].create({"name":"RX Patient","clinic_id":cls.clinic.id,"company_id":c.id,"species_id":s.id,"ownership_ids":[(0,0,{"partner_id":p.id,"is_primary":True})]}); cls.med=cls.env["vet.medication"].create({"name":"Test Medication","code":"RX-MED-TEST","company_id":c.id,"default_route":"oral"})
 def vals(self,**x):
  v={"clinic_id":self.clinic.id,"patient_id":self.patient.id,"prescriber_id":self.env.user.id,"medication_id":self.med.id,"dose":"1 tablet","frequency":"Twice daily","quantity":10,"quantity_unit":"tablet(s)","instructions":"Give with food","clinical_indication":"Test indication","refills_authorized":2}; v.update(x); return v
 def test_defaults(self):
  r=self.env["vet.prescription"].create(self.vals()); self.assertNotEqual(r.name,"New"); self.assertEqual(r.route,"oral"); self.assertEqual(r.refills_remaining,2)
 def test_workflow(self):
  r=self.env["vet.prescription"].create(self.vals()); r.action_submit(); r.action_approve(); r.action_dispense(); self.assertEqual(r.state,"dispensed"); self.assertTrue(r.dispensed_at)
 def test_quantity(self):
  with self.assertRaises(ValidationError): self.env["vet.prescription"].create(self.vals(quantity=0))
 def test_expired(self):
  r=self.env["vet.prescription"].create(self.vals(expiry_date=fields.Date.context_today(self)-timedelta(days=1))); r.action_submit(); r.action_approve()
  with self.assertRaises(ValidationError): r.action_dispense()
 def test_invalid_transition(self):
  r=self.env["vet.prescription"].create(self.vals())
  with self.assertRaises(UserError): r.action_dispense()
