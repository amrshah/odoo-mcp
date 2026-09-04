from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestVetAppointment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.clinic = cls.env["vet.clinic"].create(
            {"name": "Test Clinic", "code": "APT-TEST", "company_id": cls.company.id}
        )
        cls.species = cls.env["vet.species"].create(
            {"name": "Test Species", "code": "APT-TEST-SPECIES"}
        )
        cls.client = cls.env["res.partner"].create({"name": "Test Client"})
        cls.patient = cls.env["vet.patient"].create(
            {
                "name": "Test Patient",
                "clinic_id": cls.clinic.id,
                "company_id": cls.company.id,
                "species_id": cls.species.id,
                "ownership_ids": [(0, 0, {"partner_id": cls.client.id, "is_primary": True})],
            }
        )
        cls.provider = cls.env["res.users"].create(
            {
                "name": "Test Provider",
                "login": "test-provider-vetcairn",
                "vet_is_provider": True,
                "company_id": cls.company.id,
                "company_ids": [(6, 0, cls.company.ids)],
            }
        )
        cls.appointment_type = cls.env["vet.appointment.type"].create(
            {
                "name": "Test Consultation",
                "code": "APT-CONSULT",
                "duration": 0.5,
                "company_id": cls.company.id,
            }
        )
        cls.start = fields.Datetime.now() + timedelta(days=2)

    def _appointment_values(self, **overrides):
        values = {
            "clinic_id": self.clinic.id,
            "patient_id": self.patient.id,
            "provider_id": self.provider.id,
            "appointment_type_id": self.appointment_type.id,
            "start_datetime": self.start,
            "end_datetime": self.start + timedelta(minutes=30),
            "reason": "Routine examination",
        }
        values.update(overrides)
        return values

    def test_sequence_owner_and_duration(self):
        appointment = self.env["vet.appointment"].create(self._appointment_values())
        self.assertNotEqual(appointment.name, "New")
        self.assertEqual(appointment.client_id, self.client)
        self.assertEqual(appointment.duration, 0.5)

    def test_default_end_uses_appointment_type_duration(self):
        values = self._appointment_values()
        values.pop("end_datetime")
        appointment = self.env["vet.appointment"].create(values)
        self.assertEqual(appointment.end_datetime, self.start + timedelta(minutes=30))

    def test_end_must_be_after_start(self):
        with self.assertRaises(ValidationError):
            self.env["vet.appointment"].create(
                self._appointment_values(end_datetime=self.start)
            )

    def test_provider_overlap_is_rejected(self):
        self.env["vet.appointment"].create(self._appointment_values())
        other_client = self.env["res.partner"].create({"name": "Other Client"})
        other_patient = self.env["vet.patient"].create(
            {
                "name": "Other Patient",
                "clinic_id": self.clinic.id,
                "company_id": self.company.id,
                "species_id": self.species.id,
                "ownership_ids": [(0, 0, {"partner_id": other_client.id, "is_primary": True})],
            }
        )
        with self.assertRaises(ValidationError):
            self.env["vet.appointment"].create(
                self._appointment_values(patient_id=other_patient.id)
            )

    def test_cancelled_booking_does_not_block_slot(self):
        first = self.env["vet.appointment"].create(self._appointment_values())
        first.action_cancel()
        replacement = self.env["vet.appointment"].create(self._appointment_values())
        self.assertTrue(replacement)

    def test_status_workflow(self):
        appointment = self.env["vet.appointment"].create(self._appointment_values())
        appointment.action_confirm()
        appointment.action_arrive()
        appointment.action_start()
        appointment.action_complete()
        self.assertEqual(appointment.state, "completed")
        self.assertTrue(appointment.arrived_at)
        self.assertTrue(appointment.started_at)
        self.assertTrue(appointment.completed_at)

    def test_invalid_status_transition_is_rejected(self):
        appointment = self.env["vet.appointment"].create(self._appointment_values())
        with self.assertRaises(UserError):
            appointment.action_complete()
