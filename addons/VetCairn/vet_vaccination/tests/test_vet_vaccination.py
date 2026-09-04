from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestVetVaccination(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env.company
        cls.clinic = cls.env["vet.clinic"].create(
            {"name": "Vaccination Test Clinic", "code": "VAC-TEST", "company_id": company.id}
        )
        cls.species = cls.env["vet.species"].create(
            {"name": "Vaccination Test Species", "code": "VAC-TEST-SPECIES"}
        )
        cls.other_species = cls.env["vet.species"].create(
            {"name": "Other Vaccination Species", "code": "VAC-OTHER-SPECIES"}
        )
        client = cls.env["res.partner"].create({"name": "Vaccination Test Client"})
        cls.patient = cls.env["vet.patient"].create(
            {
                "name": "Vaccination Test Patient",
                "clinic_id": cls.clinic.id,
                "company_id": company.id,
                "species_id": cls.species.id,
                "ownership_ids": [(0, 0, {"partner_id": client.id, "is_primary": True})],
            }
        )
        cls.protocol = cls.env["vet.vaccine.protocol"].create(
            {
                "name": "Annual Test Vaccine",
                "code": "VAC-ANNUAL-TEST",
                "company_id": company.id,
                "species_id": cls.species.id,
                "booster_interval_months": 12,
                "default_route": "subcutaneous",
                "default_dose": 1.0,
                "dose_unit": "ml",
            }
        )

    def _values(self, **overrides):
        values = {
            "clinic_id": self.clinic.id,
            "patient_id": self.patient.id,
            "protocol_id": self.protocol.id,
            "planned_date": fields.Date.context_today(self),
        }
        values.update(overrides)
        return values

    def test_protocol_defaults_and_sequence(self):
        vaccination = self.env["vet.vaccination"].create(self._values())
        self.assertNotEqual(vaccination.name, "New")
        self.assertEqual(vaccination.route, "subcutaneous")
        self.assertEqual(vaccination.dose, 1.0)
        self.assertEqual(vaccination.client_id, self.patient.primary_owner_id)

    def test_administration_calculates_next_due(self):
        vaccination = self.env["vet.vaccination"].create(self._values())
        vaccination.action_administer()
        self.assertEqual(vaccination.state, "administered")
        self.assertTrue(vaccination.administered_date)
        self.assertTrue(vaccination.administered_by_id)
        self.assertEqual(
            vaccination.next_due_date.year, vaccination.administered_date.year + 1
        )

    def test_overdue_planned_vaccination(self):
        vaccination = self.env["vet.vaccination"].create(
            self._values(planned_date=fields.Date.context_today(self) - timedelta(days=1))
        )
        self.assertTrue(vaccination.is_overdue)

    def test_species_mismatch_is_rejected(self):
        wrong_protocol = self.env["vet.vaccine.protocol"].create(
            {
                "name": "Wrong Species Vaccine",
                "code": "VAC-WRONG-SPECIES",
                "company_id": self.env.company.id,
                "species_id": self.other_species.id,
                "booster_interval_months": 12,
            }
        )
        with self.assertRaises(ValidationError):
            self.env["vet.vaccination"].create(
                self._values(protocol_id=wrong_protocol.id)
            )

    def test_expired_vaccine_cannot_be_administered(self):
        vaccination = self.env["vet.vaccination"].create(
            self._values(expiry_date=fields.Date.context_today(self) - timedelta(days=1))
        )
        with self.assertRaises(ValidationError):
            vaccination.action_administer()

    def test_invalid_state_change_is_rejected(self):
        vaccination = self.env["vet.vaccination"].create(self._values())
        vaccination.action_cancel()
        with self.assertRaises(UserError):
            vaccination.action_administer()
