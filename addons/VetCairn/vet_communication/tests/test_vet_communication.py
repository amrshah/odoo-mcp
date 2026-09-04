from datetime import timedelta
from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

@tagged("post_install", "-at_install")
class TestVetCommunication(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.clinic = cls.env["vet.clinic"].create({"name":"Communication Test Clinic","code":"CTC","company_id":cls.env.company.id})
        cls.client = cls.env["res.partner"].create({"name":"Communication Test Client","is_vet_client":True,"phone":"555-0100","email":"client@example.test","vet_preferred_clinic_id":cls.clinic.id})
    def _communication(self, **extra):
        values={"clinic_id":self.clinic.id,"client_id":self.client.id,"subject":"Recovery follow-up","body":"<p>Record the recovery update.</p>","channel":"phone","direction":"outbound"}; values.update(extra); return self.env["vet.communication"].create(values)
    def test_complete_and_follow_up_task(self):
        record=self._communication(follow_up_required=True,follow_up_datetime=fields.Datetime.now()+timedelta(days=1),follow_up_user_id=self.env.user.id)
        record.action_plan(); record.action_complete()
        self.assertEqual(record.state,"completed"); self.assertEqual(record.follow_up_task_id.state,"open")
    def test_channel_validation_and_dashboard(self):
        self.client.vet_transactional_sms=False
        record=self._communication(channel="sms")
        with self.assertRaises(ValidationError): record.action_plan()
        data=self.env["vet.dashboard"].get_dashboard_data()
        self.assertIn("Communication Queue",{item["label"] for item in data["metrics"]})
