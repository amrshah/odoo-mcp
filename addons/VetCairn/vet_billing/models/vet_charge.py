from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class VetCharge(models.Model):
    _name = "vet.charge"
    _description = "Veterinary Charge"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "charge_datetime desc, id desc"

    name = fields.Char(string="Charge Number", required=True, readonly=True, copy=False, default=lambda self: self.env._("New"), index=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    clinic_id = fields.Many2one("vet.clinic", required=True, ondelete="restrict", domain="[('company_id','=',company_id)]", index=True, tracking=True)
    patient_id = fields.Many2one("vet.patient", required=True, ondelete="restrict", domain="[('company_id','=',company_id)]", index=True, tracking=True)
    client_id = fields.Many2one(related="patient_id.primary_owner_id", store=True, index=True)
    appointment_id = fields.Many2one("vet.appointment", ondelete="set null", domain="[('patient_id','=',patient_id)]")
    encounter_id = fields.Many2one("vet.encounter", ondelete="set null", domain="[('patient_id','=',patient_id)]")
    product_id = fields.Many2one("product.product", required=True, ondelete="restrict", domain="[('product_tmpl_id.is_vet_item','=',True)]", tracking=True)
    description = fields.Char(required=True, tracking=True)
    quantity = fields.Float(default=1.0, required=True, tracking=True)
    unit_price = fields.Float(required=True, tracking=True)
    tax_ids = fields.Many2many("account.tax", string="Taxes", domain="[('type_tax_use','=','sale'),('company_id','=',company_id)]")
    subtotal = fields.Monetary(compute="_compute_subtotal", store=True, currency_field="currency_id")
    charge_datetime = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    state = fields.Selection([("draft","Draft"),("ready","Ready to Invoice"),("invoiced","Invoiced"),("cancelled","Cancelled")], default="draft", required=True, index=True, tracking=True)
    invoice_id = fields.Many2one("account.move", readonly=True, copy=False, index=True)
    invoice_state = fields.Selection(related="invoice_id.state", string="Invoice Status")
    notes = fields.Text()

    _name_company_unique = models.Constraint("UNIQUE(name, company_id)", "Charge numbers must be unique within a company.")

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            if values.get("name", self.env._("New")) == self.env._("New"):
                values["name"] = self.env["ir.sequence"].next_by_code("vet.charge") or self.env._("New")
            if values.get("product_id"):
                product=self.env["product.product"].browse(values["product_id"])
                values.setdefault("description", product.display_name); values.setdefault("unit_price", product.lst_price)
        return super().create(vals_list)

    @api.depends("quantity", "unit_price")
    def _compute_subtotal(self):
        for charge in self: charge.subtotal=charge.quantity*charge.unit_price

    @api.onchange("patient_id")
    def _onchange_patient_id(self):
        if self.patient_id: self.clinic_id=self.patient_id.clinic_id; self.company_id=self.patient_id.company_id

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id: self.description=self.product_id.display_name; self.unit_price=self.product_id.lst_price; self.tax_ids=self.product_id.taxes_id

    @api.constrains("quantity", "unit_price")
    def _check_amounts(self):
        for charge in self:
            if charge.quantity <= 0: raise ValidationError("Charge quantity must be greater than zero.")
            if charge.unit_price < 0: raise ValidationError("Charge unit price cannot be negative.")

    def action_ready(self):
        if self.filtered(lambda c: c.state != "draft"): raise UserError("Only draft charges can be marked ready.")
        if self.filtered(lambda c: not c.client_id): raise ValidationError("The patient needs a primary client before invoicing.")
        self.write({"state":"ready"}); return True

    def action_create_invoice(self):
        self.ensure_one()
        if self.state != "ready": raise UserError("Only ready charges can be invoiced.")
        accounts=self.product_id.product_tmpl_id.get_product_accounts()
        income_account=accounts.get("income")
        if not income_account: raise UserError("Configure an income account for this product or its category before invoicing.")
        invoice=self.env["account.move"].create({"move_type":"out_invoice","partner_id":self.client_id.id,"company_id":self.company_id.id,"invoice_origin":self.name,"vet_patient_id":self.patient_id.id,"vet_clinic_id":self.clinic_id.id,"vet_appointment_id":self.appointment_id.id,"vet_encounter_id":self.encounter_id.id,"invoice_line_ids":[(0,0,{"product_id":self.product_id.id,"name":self.description,"quantity":self.quantity,"price_unit":self.unit_price,"tax_ids":[(6,0,self.tax_ids.ids)],"account_id":income_account.id})]})
        self.write({"state":"invoiced","invoice_id":invoice.id})
        return {"type":"ir.actions.act_window","res_model":"account.move","res_id":invoice.id,"view_mode":"form","target":"current"}

    def action_cancel(self):
        if self.filtered(lambda c: c.state not in ("draft","ready")): raise UserError("An invoiced charge cannot be cancelled here.")
        self.write({"state":"cancelled"}); return True
