from odoo import fields, models

class VetPatient(models.Model):
    _inherit="vet.patient"
    invoice_count=fields.Integer(compute="_compute_invoice_count")
    def _compute_invoice_count(self):
        counts=self.env["account.move"]._read_group([("vet_patient_id","in",self.ids),("move_type","in",("out_invoice","out_refund"))],["vet_patient_id"],["__count"]); mapped={p.id:c for p,c in counts}
        for rec in self: rec.invoice_count=mapped.get(rec.id,0)
    def action_view_invoices(self):
        self.ensure_one(); return {"type":"ir.actions.act_window","name":self.env._("Invoices — %s",self.display_name),"res_model":"account.move","view_mode":"list,form","domain":[("vet_patient_id","=",self.id),("move_type","in",("out_invoice","out_refund"))],"context":{"default_move_type":"out_invoice","default_partner_id":self.primary_owner_id.id,"default_vet_patient_id":self.id,"default_vet_clinic_id":self.clinic_id.id}}
