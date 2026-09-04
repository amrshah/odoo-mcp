from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestVetBase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.clinic = cls.env["vet.clinic"].create(
            {"name": "Test Clinic", "code": "TEST"}
        )
        cls.species = cls.env["vet.species"].create(
            {"name": "Test Species", "code": "TEST-SPECIES"}
        )
        cls.breed = cls.env["vet.breed"].create(
            {"name": "Test Breed", "species_id": cls.species.id}
        )
        cls.client = cls.env["res.partner"].create(
            {"name": "Test Client", "is_vet_client": True}
        )

    def _create_patient(self, **values):
        patient_values = {
            "name": "Test Patient",
            "clinic_id": self.clinic.id,
            "species_id": self.species.id,
            "breed_id": self.breed.id,
        }
        patient_values.update(values)
        return self.env["vet.patient"].create(patient_values)

    def test_patient_sequence_and_primary_owner(self):
        patient = self._create_patient()
        self.assertTrue(patient.identifier.startswith("PAT-"))
        self.env["vet.patient.owner"].create(
            {
                "patient_id": patient.id,
                "partner_id": self.client.id,
                "is_primary": True,
            }
        )
        self.assertEqual(patient.primary_owner_id, self.client)
        self.assertEqual(self.client.vet_patient_count, 1)

    def test_only_one_active_primary_owner(self):
        patient = self._create_patient()
        self.env["vet.patient.owner"].create(
            {
                "patient_id": patient.id,
                "partner_id": self.client.id,
                "is_primary": True,
            }
        )
        second_client = self.env["res.partner"].create(
            {"name": "Second Client", "is_vet_client": True}
        )
        with self.assertRaises(ValidationError):
            self.env["vet.patient.owner"].create(
                {
                    "patient_id": patient.id,
                    "partner_id": second_client.id,
                    "is_primary": True,
                }
            )

    def test_breed_must_match_species(self):
        other_species = self.env["vet.species"].create(
            {"name": "Other Species", "code": "OTHER-SPECIES"}
        )
        with self.assertRaises(ValidationError):
            self._create_patient(species_id=other_species.id)

    def test_deceased_patient_requires_date(self):
        with self.assertRaises(ValidationError):
            self._create_patient(status="deceased")

    def test_birthdate_cannot_be_future(self):
        tomorrow = fields.Date.today() + timedelta(days=1)
        with self.assertRaises(ValidationError):
            self._create_patient(birthdate=tomorrow)

