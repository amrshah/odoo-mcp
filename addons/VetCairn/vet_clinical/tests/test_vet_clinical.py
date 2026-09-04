from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestVetClinical(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls.clinic = cls.env["vet.clinic"].create(
            {"name": "Clinical Test Clinic", "code": "CLIN-TEST", "company_id": company.id}
        )
        cls.species = cls.env["vet.species"].create(
            {"name": "Clinical Test Species", "code": "CLIN-TEST-SPECIES"}
        )
        cls.client = cls.env["res.partner"].create({"name": "Clinical Test Client"})
        cls.patient = cls.env["vet.patient"].create(
            {
                "name": "Clinical Test Patient",
                "clinic_id": cls.clinic.id,
                "company_id": company.id,
                "species_id": cls.species.id,
                "ownership_ids": [(0, 0, {"partner_id": cls.client.id, "is_primary": True})],
            }
        )
        cls.provider = cls.env["res.users"].create(
            {
                "name": "Clinical Test Veterinarian",
                "login": "clinical-test-veterinarian",
                "vet_is_provider": True,
                "company_id": company.id,
                "company_ids": [(6, 0, company.ids)],
            }
        )
        cls.appointment_type = cls.env["vet.appointment.type"].create(
            {
                "name": "Clinical Test Consultation",
                "code": "CLIN-TEST-CONSULT",
                "duration": 0.5,
                "company_id": company.id,
            }
        )
        start = fields.Datetime.now() + timedelta(days=5)
        cls.appointment = cls.env["vet.appointment"].create(
            {
                "clinic_id": cls.clinic.id,
                "patient_id": cls.patient.id,
                "provider_id": cls.provider.id,
                "appointment_type_id": cls.appointment_type.id,
                "start_datetime": start,
                "end_datetime": start + timedelta(minutes=30),
                "reason": "Reduced appetite",
            }
        )

    def test_starting_visit_creates_encounter(self):
        self.appointment.action_arrive()
        self.appointment.action_start()
        encounter = self.env["vet.encounter"].search(
            [("appointment_id", "=", self.appointment.id)]
        )
        self.assertEqual(len(encounter), 1)
        self.assertEqual(encounter.state, "in_progress")
        self.assertEqual(encounter.chief_complaint, self.appointment.reason)

    def test_completing_visit_completes_encounter(self):
        self.appointment.action_arrive()
        self.appointment.action_start()
        self.appointment.action_complete()
        self.assertEqual(self.appointment.encounter_id.state, "completed")
        self.assertTrue(self.appointment.encounter_id.completed_at)

    def test_invalid_temperature_is_rejected(self):
        encounter = self.appointment._get_or_create_encounter()
        with self.assertRaises(ValidationError):
            encounter.temperature_c = 60

    def test_locked_note_cannot_be_edited(self):
        encounter = self.appointment._get_or_create_encounter()
        encounter.action_complete()
        encounter.action_lock()
        with self.assertRaises(UserError):
            encounter.write({"assessment": "Changed after locking"})

    def test_one_encounter_per_appointment(self):
        self.appointment._get_or_create_encounter()
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.env["vet.encounter"].create(
                {"appointment_id": self.appointment.id, "chief_complaint": "Duplicate"}
            )
