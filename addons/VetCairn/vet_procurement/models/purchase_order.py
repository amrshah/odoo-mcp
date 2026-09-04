from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    is_vet_purchase = fields.Boolean(string="Veterinary Purchase", default=False, index=True, tracking=True)
    vet_clinic_id = fields.Many2one("vet.clinic", string="Clinic", domain="[('company_id','=',company_id)]", index=True, tracking=True)
    vet_controlled_item = fields.Boolean(string="Contains Controlled Item", compute="_compute_vet_controlled_item", search="_search_vet_controlled_item")
    vet_review_state = fields.Selection([("not_required","Not Required"),("pending","Pending Review"),("approved","Approved"),("rejected","Rejected")], default="not_required", required=True, index=True, tracking=True)
    vet_approved_by_id = fields.Many2one("res.users", string="Approved By", readonly=True, copy=False)
    vet_approved_at = fields.Datetime(string="Approved At", readonly=True, copy=False)
    vet_rejection_reason = fields.Text(string="Rejection Reason", tracking=True)
    vet_procurement_notes = fields.Text(string="Veterinary Procurement Notes")

    @api.depends("order_line.product_id.product_tmpl_id.vet_controlled")
    def _compute_vet_controlled_item(self):
        for order in self:
            order.vet_controlled_item = any(order.order_line.mapped("product_id.product_tmpl_id.vet_controlled"))

    def _search_vet_controlled_item(self, operator, value):
        controlled_domain = [("order_line.product_id.product_tmpl_id.vet_controlled", "=", True)]
        if (operator in ("=", "==") and value) or (operator == "!=" and not value):
            return controlled_domain
        return ["!"] + controlled_domain

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._sync_vet_review_state()
        return orders

    def _sync_vet_review_state(self):
        for order in self:
            target = order.vet_review_state
            if not order.vet_controlled_item:
                target = "not_required"
            elif target in (False, "not_required", "rejected"):
                target = "pending"
            if target != order.vet_review_state:
                order.with_context(skip_vet_review_sync=True).write({"vet_review_state": target})

    @api.constrains("is_vet_purchase", "vet_clinic_id")
    def _check_vet_clinic(self):
        for order in self.filtered("is_vet_purchase"):
            if not order.vet_clinic_id:
                raise ValidationError("A veterinary purchase order requires a clinic.")
            if order.vet_clinic_id.company_id != order.company_id:
                raise ValidationError("The purchase order and clinic must belong to the same company.")

    def action_vet_request_review(self):
        invalid = self.filtered(lambda order: not order.vet_controlled_item or order.state not in ("draft", "sent"))
        if invalid:
            raise UserError("Only draft controlled-item purchases can be submitted for review.")
        self.write({"vet_review_state":"pending", "vet_approved_by_id":False, "vet_approved_at":False})
        return True

    def action_vet_approve(self):
        if not self.env.user.has_group("vet_procurement.group_vet_procurement_manager"):
            raise AccessError("Procurement Manager permission is required.")
        invalid = self.filtered(lambda order: order.vet_review_state != "pending" or order.state not in ("draft", "sent"))
        if invalid:
            raise UserError("Only pending draft purchases can be approved.")
        self.write({"vet_review_state":"approved", "vet_approved_by_id":self.env.user.id, "vet_approved_at":fields.Datetime.now(), "vet_rejection_reason":False})
        return True

    def action_vet_reject(self):
        if not self.env.user.has_group("vet_procurement.group_vet_procurement_manager"):
            raise AccessError("Procurement Manager permission is required.")
        if self.filtered(lambda order: order.vet_review_state != "pending"):
            raise UserError("Only pending purchases can be rejected.")
        if self.filtered(lambda order: not order.vet_rejection_reason):
            raise ValidationError("Enter a rejection reason first.")
        self.write({"vet_review_state":"rejected"})
        return True

    def button_confirm(self):
        blocked = self.filtered(lambda order: order.is_vet_purchase and order.vet_controlled_item and order.vet_review_state != "approved")
        if blocked:
            raise UserError("Controlled-item purchase orders require Procurement Manager approval before confirmation.")
        return super().button_confirm()

    def _prepare_picking(self):
        values = super()._prepare_picking()
        if self.is_vet_purchase:
            values.update({"is_vet_receipt":True, "vet_clinic_id":self.vet_clinic_id.id})
        return values


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.order_id._sync_vet_review_state()
        return lines

    def write(self, values):
        orders = self.order_id
        result = super().write(values)
        (orders | self.order_id)._sync_vet_review_state()
        return result

    def unlink(self):
        orders = self.order_id
        result = super().unlink()
        orders._sync_vet_review_state()
        return result
