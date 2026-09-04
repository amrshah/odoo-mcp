from odoo import fields, models


class VetClinic(models.Model):
    _inherit = "vet.clinic"

    purchase_order_count = fields.Integer(compute="_compute_purchase_order_count")

    def _compute_purchase_order_count(self):
        counts = self.env["purchase.order"]._read_group([("vet_clinic_id", "in", self.ids), ("is_vet_purchase", "=", True)], ["vet_clinic_id"], ["__count"])
        mapped = {clinic.id: count for clinic, count in counts}
        for clinic in self:
            clinic.purchase_order_count = mapped.get(clinic.id, 0)

    def action_view_purchase_orders(self):
        self.ensure_one()
        return {"type":"ir.actions.act_window", "name":self.env._("Purchase Orders — %s", self.display_name), "res_model":"purchase.order", "view_mode":"list,kanban,form", "domain":[("vet_clinic_id","=",self.id),("is_vet_purchase","=",True)], "context":{"default_is_vet_purchase":True,"default_vet_clinic_id":self.id,"default_company_id":self.company_id.id}}
