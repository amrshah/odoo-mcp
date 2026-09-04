from datetime import timedelta
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

@tagged("post_install", "-at_install")
class TestVetReminder(TransactionCase):
 @classmethod
 def setUpClass(cls):
  super().setUpClass(); c=cls.env.company; cls.clinic=cls.env["vet.clinic"].create({"name":"Reminder Test Clinic","code":"REM-TEST","company_id":c.id}); s=cls.env["vet.species"].create({"name":"Reminder Test Species","code":"REM-TEST-SPECIES"}); partner=cls.env["res.partner"].create({"name":"Reminder Client","email":"client@example.test","phone":"555-0100"}); cls.patient=cls.env["vet.patient"].create({"name":"Reminder Patient","clinic_id":cls.clinic.id,"company_id":c.id,"species_id":s.id,"ownership_ids":[(0,0,{"partner_id":partner.id,"is_primary":True})]}); cls.rtype=cls.env["vet.reminder.type"].create({"name":"Annual Reminder","code":"REM-ANNUAL-TEST","company_id":c.id,"default_channel":"email","subject_template":"Annual visit due","message_template":"Please contact the clinic."})
 def vals(self,**x):
  v={"clinic_id":self.clinic.id,"patient_id":self.patient.id,"reminder_type_id":self.rtype.id,"due_date":fields.Date.context_today(self)}; v.update(x); return v
 def test_templates_and_sequence(self):
  r=self.env["vet.reminder"].create(self.vals()); self.assertNotEqual(r.name,"New"); self.assertEqual(r.subject,"Annual visit due"); self.assertEqual(r.channel,"email")
 def test_workflow(self):
  r=self.env["vet.reminder"].create(self.vals()); r.action_schedule(); r.action_mark_sent(); self.assertEqual(r.state,"sent"); self.assertTrue(r.sent_at)
 def test_overdue(self):
  r=self.env["vet.reminder"].create(self.vals(due_date=fields.Date.context_today(self)-timedelta(days=1))); r.action_schedule(); self.assertTrue(r.is_overdue)
 def test_email_required(self):
  self.patient.primary_owner_id.email=False; r=self.env["vet.reminder"].create(self.vals())
  with self.assertRaises(ValidationError): r.action_schedule()
 def test_invalid_transition(self):
  r=self.env["vet.reminder"].create(self.vals())
  with self.assertRaises(UserError): r.action_mark_sent()
