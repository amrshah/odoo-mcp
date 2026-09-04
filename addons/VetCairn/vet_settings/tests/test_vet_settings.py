from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

@tagged("post_install", "-at_install")
class TestVetSettings(TransactionCase):
    def test_settings_persist_and_validate(self):
        settings=self.env["res.config.settings"].create({"vet_appointment_slot_minutes":20,"vet_document_expiry_warning_days":45,"vet_default_deposit_percent":25,"vet_dashboard_refresh_minutes":5})
        settings.execute()
        loaded=self.env["res.config.settings"].create({})
        loaded.get_values()
        self.assertEqual(loaded.vet_appointment_slot_minutes,20)
        self.assertEqual(loaded.vet_default_deposit_percent,25)
        with self.assertRaises(ValidationError): self.env["res.config.settings"].create({"vet_appointment_slot_minutes":0})
    def test_clinic_operating_hours(self):
        clinic=self.env["vet.clinic"].create({"name":"Settings Test Clinic","code":"STC","company_id":self.env.company.id,"opening_hour":8,"closing_hour":20})
        self.assertTrue(clinic.accepts_emergencies)
        with self.assertRaises(ValidationError): clinic.write({"opening_hour":22,"closing_hour":8})
