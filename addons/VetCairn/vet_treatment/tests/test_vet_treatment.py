from datetime import timedelta
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

@tagged("post_install", "-at_install")
class TestVetTreatment(TransactionCase):
 @classmethod
 def setUpClass(cls):
  super().setUpClass(); c=cls.env.company; cls.clinic=cls.env["vet.clinic"].create({"name":"Treatment Test Clinic","code":"TX-TEST","company_id":c.id}); s=cls.env["vet.species"].create({"name":"Treatment Test Species","code":"TX-TEST-SPECIES"}); p=cls.env["res.partner"].create({"name":"Treatment Client"}); cls.patient=cls.env["vet.patient"].create({"name":"Treatment Patient","clinic_id":cls.clinic.id,"company_id":c.id,"species_id":s.id,"ownership_ids":[(0,0,{"partner_id":p.id,"is_primary":True})]}); cls.diagnosis=cls.env["vet.diagnosis"].create({"name":"Test Diagnosis","code":"TX-DX-TEST","company_id":c.id})
 def plan_vals(self,**x):
  v={"title":"Recovery Plan","clinic_id":self.clinic.id,"patient_id":self.patient.id,"provider_id":self.env.user.id,"diagnosis_ids":[(6,0,self.diagnosis.ids)],"care_setting":"inpatient","room":"Ward 1","line_ids":[(0,0,{"name":"Monitor temperature","category":"monitoring","due_datetime":fields.Datetime.now()+timedelta(hours=1),"instructions":"Record temperature"})]}; v.update(x); return v
 def test_sequence_and_activity_stats(self):
  plan=self.env["vet.treatment.plan"].create(self.plan_vals()); self.assertNotEqual(plan.name,"New"); self.assertEqual(plan.activity_count,1); self.assertEqual(plan.patient_id,self.patient)
 def test_full_workflow(self):
  plan=self.env["vet.treatment.plan"].create(self.plan_vals()); plan.action_start(); plan.line_ids.action_start(); plan.line_ids.action_complete(); plan.action_complete(); self.assertEqual(plan.state,"completed"); self.assertTrue(plan.discharged_at)
 def test_plan_requires_activity(self):
  values=self.plan_vals(line_ids=[]); plan=self.env["vet.treatment.plan"].create(values)
  with self.assertRaises(ValidationError): plan.action_start()
 def test_plan_requires_terminal_activities(self):
  plan=self.env["vet.treatment.plan"].create(self.plan_vals()); plan.action_start()
  with self.assertRaises(ValidationError): plan.action_complete()
 def test_invalid_line_transition(self):
  plan=self.env["vet.treatment.plan"].create(self.plan_vals()); line=plan.line_ids; line.action_complete()
  with self.assertRaises(UserError): line.action_start()
