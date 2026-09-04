from datetime import timedelta
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

@tagged("post_install", "-at_install")
class TestVetDocuments(TransactionCase):
 @classmethod
 def setUpClass(cls):
  super().setUpClass(); c=cls.env.company; cls.clinic=cls.env["vet.clinic"].create({"name":"Doc Test Clinic","code":"DOC-TEST","company_id":c.id}); s=cls.env["vet.species"].create({"name":"Doc Test Species","code":"DOC-TEST-SPECIES"}); p=cls.env["res.partner"].create({"name":"Doc Client"}); cls.patient=cls.env["vet.patient"].create({"name":"Doc Patient","clinic_id":cls.clinic.id,"company_id":c.id,"species_id":s.id,"ownership_ids":[(0,0,{"partner_id":p.id,"is_primary":True})]}); cls.dtype=cls.env["vet.document.type"].create({"name":"Consent Test","code":"DOC-CONSENT-TEST","category":"consent","company_id":c.id,"signature_required":True,"expiry_required":True,"default_validity_days":30})
 def vals(self,**x):
  v={"title":"Procedure Consent","clinic_id":self.clinic.id,"patient_id":self.patient.id,"document_type_id":self.dtype.id,"file_data":b"dGVzdA==","filename":"consent.txt"}; v.update(x); return v
 def test_defaults_and_expiry(self):
  doc=self.env["vet.patient.document"].create(self.vals()); self.assertNotEqual(doc.name,"New"); self.assertEqual(doc.expiry_date,doc.document_date+timedelta(days=30))
 def test_signing(self):
  doc=self.env["vet.patient.document"].create(self.vals(signed_by_name="Test Client")); doc.action_sign(); self.assertEqual(doc.state,"signed"); self.assertTrue(doc.signed_at)
 def test_signer_required(self):
  doc=self.env["vet.patient.document"].create(self.vals())
  with self.assertRaises(ValidationError): doc.action_sign()
 def test_invalid_dates(self):
  today=fields.Date.context_today(self)
  with self.assertRaises(ValidationError): self.env["vet.patient.document"].create(self.vals(document_date=today,expiry_date=today-timedelta(days=1)))
 def test_invalid_transition(self):
  doc=self.env["vet.patient.document"].create(self.vals()); doc.action_void()
  with self.assertRaises(UserError): doc.action_void()
