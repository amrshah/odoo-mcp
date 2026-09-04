from odoo import fields, models

class VetPatient(models.Model):
    _inherit="vet.patient"
    treatment_plan_count=fields.Integer(compute="_compute_treatment_plan_count")
    def _compute_treatment_plan_count(self):
        counts=self.env["vet.treatment.plan"]._read_group([("patient_id","in",self.ids)],["patient_id"],["__count"]); mapped={p.id:c for p,c in counts}
        for rec in self: rec.treatment_plan_count=mapped.get(rec.id,0)
    def action_view_treatment_plans(self):
        self.ensure_one(); return {"type":"ir.actions.act_window","name":self.env._("Treatment Plans — %s",self.display_name),"res_model":"vet.treatment.plan","view_mode":"list,form","domain":[("patient_id","=",self.id)],"context":{"default_patient_id":self.id,"default_clinic_id":self.clinic_id.id,"default_company_id":self.company_id.id}}
