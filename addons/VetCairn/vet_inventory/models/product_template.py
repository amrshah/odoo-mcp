from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_vet_item = fields.Boolean(string="Veterinary Item", index=True, tracking=True)
    vet_item_type = fields.Selection(
        [("medication","Medication"),("vaccine","Vaccine"),("supply","Clinical Supply"),
         ("food","Food / Nutrition"),("retail","Retail"),("service","Service")],
        string="Veterinary Item Type", default="supply", tracking=True,
    )
    vet_controlled = fields.Boolean(string="Controlled Item", tracking=True)
    vet_concentration = fields.Float(string="Concentration", tracking=True)
    vet_concentration_unit = fields.Char(string="Concentration Unit")
    vet_default_route = fields.Selection(
        [("oral","Oral"),("topical","Topical"),("subcutaneous","Subcutaneous"),
         ("intramuscular","Intramuscular"),("intravenous","Intravenous"),("other","Other")],
        string="Default Route", tracking=True,
    )
    vet_dose_min = fields.Float(string="Minimum Dose")
    vet_dose_max = fields.Float(string="Maximum Dose")
    vet_dose_unit = fields.Char(string="Dose Unit")
    vet_storage_location = fields.Char(string="Storage Location", tracking=True)
    vet_reorder_min = fields.Float(string="Minimum Stock")
    vet_reorder_max = fields.Float(string="Target Stock")
    vet_print_label = fields.Boolean(string="Print Dispensing Label")
    vet_print_on_invoice = fields.Boolean(string="Print on Invoice", default=True)
    vet_clinical_instructions = fields.Text(string="Clinical / Dispensing Instructions")

    @api.onchange("is_vet_item", "vet_item_type")
    def _onchange_vet_inventory_type(self):
        if self.is_vet_item and self.vet_item_type != "service":
            self.is_storable = True
        if self.vet_item_type in ("medication", "vaccine"):
            self.tracking = "lot"
            self.use_expiration_date = True
            self.vet_print_label = True
        elif self.vet_item_type == "service":
            self.is_storable = False
            self.tracking = "none"

    @api.constrains("vet_dose_min", "vet_dose_max", "vet_reorder_min", "vet_reorder_max")
    def _check_vet_ranges(self):
        for product in self:
            if min(product.vet_dose_min, product.vet_dose_max, product.vet_reorder_min, product.vet_reorder_max) < 0:
                raise ValidationError("Dose and stock levels cannot be negative.")
            if product.vet_dose_max and product.vet_dose_min > product.vet_dose_max:
                raise ValidationError("Minimum dose cannot exceed maximum dose.")
            if product.vet_reorder_max and product.vet_reorder_min > product.vet_reorder_max:
                raise ValidationError("Minimum stock cannot exceed target stock.")
