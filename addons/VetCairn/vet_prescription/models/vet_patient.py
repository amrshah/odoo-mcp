from odoo import fields, models


class VetPatient(models.Model):
    _inherit = "vet.patient"
    prescription_count = fields.Integer(compute="_compute_prescription_count")
    def _compute_prescription_count(self):
        counts=self.env["vet.prescription"]._read_group([("patient_id","in",self.ids)],["patient_id"],["__count"]); mapped={p.id:c for p,c in counts}
        for rec in self: rec.prescription_count=mapped.get(rec.id,0)
    def action_view_prescriptions(self):
        self.ensure_one(); return {"type":"ir.actions.act_window","name":self.env._("Prescriptions — %s",self.display_name),"res_model":"vet.prescription","view_mode":"list,form","domain":[("patient_id","=",self.id)],"context":{"default_patient_id":self.id,"default_clinic_id":self.clinic_id.id,"default_company_id":self.company_id.id}}
