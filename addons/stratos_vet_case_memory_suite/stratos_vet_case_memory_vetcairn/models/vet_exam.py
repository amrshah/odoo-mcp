from odoo import fields, models

REPRO = {"intact": "intact", "spayed": "neutered", "neutered": "neutered"}


class VetExam(models.Model):
    _inherit = "vet.exam"

    def _cm_case_vals(self, species=False):
        """Add what VetCairn already knows about the patient."""
        vals = super()._cm_case_vals(species=species)
        pat = self.patient_id
        if not pat:
            return vals
        if pat.breed_id:
            vals["breed"] = pat.breed_id.name
        if pat.sex in ("male", "female"):
            vals["sex"] = pat.sex
        if pat.reproductive_status in REPRO:
            vals["repro_status"] = REPRO[pat.reproductive_status]
        if pat.birthdate:
            today = fields.Date.context_today(self)
            months = (today.year - pat.birthdate.year) * 12 + today.month - pat.birthdate.month
            vals["age_months"] = max(months, 0)
        return vals
