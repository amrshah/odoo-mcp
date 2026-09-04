from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
@tagged("post_install","-at_install")
class TestCompletion(TransactionCase):
 @classmethod
 def setUpClass(cls):
  super().setUpClass(); cls.c=cls.env["vet.clinic"].create({"name":"Completion Clinic","code":"CCX"}); cls.p=cls.env["res.partner"].create({"name":"Owner","is_vet_client":True}); cls.s=cls.env["vet.species"].create({"name":"Test Species","code":"TSP"}); cls.patient=cls.env["vet.patient"].create({"name":"Patient","clinic_id":cls.c.id,"species_id":cls.s.id,"ownership_ids":[(0,0,{"partner_id":cls.p.id,"is_primary":True})]}); cls.w=cls.env["vet.ward"].create({"name":"Ward","clinic_id":cls.c.id}); cls.b=cls.env["vet.bed"].create({"name":"B1","ward_id":cls.w.id})
 def test_admission_bed_workflow(self):
  a=self.env["vet.admission"].create({"clinic_id":self.c.id,"patient_id":self.patient.id,"ward_id":self.w.id,"bed_id":self.b.id,"reason":"Observation"}); a.action_admit(); self.assertEqual(self.b.status,"occupied"); a.discharge_summary="<p>Stable</p>"; a.action_discharge(); self.assertEqual(self.b.status,"cleaning")
 def test_migration_is_non_destructive(self):
  batch=self.env["vet.migration.batch"].create({"name":"Dry Run","source":"Authorized export","line_ids":[(0,0,{"record_type":"client","source_key":"1","payload":{"name":"Sample"}})]}); before=self.env["res.partner"].search_count([]); batch.action_validate(); batch.action_ready(); batch.action_rehearse(); self.assertEqual(before,self.env["res.partner"].search_count([])); self.assertEqual(batch.state,"rehearsed")
