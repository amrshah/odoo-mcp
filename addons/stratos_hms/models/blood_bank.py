from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

BLOOD_GROUPS = [("a+", "A+"), ("a-", "A−"), ("b+", "B+"), ("b-", "B−"), ("ab+", "AB+"), ("ab-", "AB−"), ("o+", "O+"), ("o-", "O−")]
COMPONENTS = [("wb", "Whole Blood"), ("prbc", "Packed Red Cells"), ("ffp", "Fresh Frozen Plasma"), ("plt", "Platelets"), ("cryo", "Cryoprecipitate")]

# ABO/Rh compatibility for red cells: recipient -> acceptable donor groups
COMPATIBLE = {
    "o-": ["o-"], "o+": ["o-", "o+"], "a-": ["o-", "a-"], "a+": ["o-", "o+", "a-", "a+"],
    "b-": ["o-", "b-"], "b+": ["o-", "o+", "b-", "b+"], "ab-": ["o-", "a-", "b-", "ab-"],
    "ab+": ["o-", "o+", "a-", "a+", "b-", "b+", "ab-", "ab+"],
}


class HmsBloodUnit(models.Model):
    _name = "hms.blood.unit"
    _description = "Blood Unit"
    _order = "expiry_date"

    name = fields.Char(string="Bag No.", required=True)
    blood_group = fields.Selection(BLOOD_GROUPS, required=True)
    component = fields.Selection(COMPONENTS, default="prbc", required=True)
    volume_ml = fields.Integer(default=450)
    collected_date = fields.Date(default=fields.Date.today)
    expiry_date = fields.Date(required=True)
    donor_ref = fields.Char(string="Donor Ref")
    screening_done = fields.Boolean(string="Screened (HBV/HCV/HIV/Syphilis/Malaria)")
    state = fields.Selection([("available", "Available"), ("reserved", "Reserved"), ("issued", "Issued"), ("expired", "Expired"), ("discarded", "Discarded")], default="available")
    request_id = fields.Many2one("hms.blood.request", readonly=True)
    is_expired = fields.Boolean(compute="_compute_expired")

    _bag_uniq = models.Constraint("unique(name)", "Bag number must be unique.")

    def _compute_expired(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_expired = rec.expiry_date and rec.expiry_date < today

    def _compute_display_name(self):
        grp = dict(BLOOD_GROUPS)
        for rec in self:
            rec.display_name = f"{rec.name} · {grp.get(rec.blood_group)} · {dict(COMPONENTS).get(rec.component)}"


class HmsBloodRequest(models.Model):
    """Two-person verification before issue: the verifier and the issuer must be different people,
    and the unit must be ABO/Rh compatible, screened and in date."""
    _name = "hms.blood.request"
    _description = "Blood Request"
    _inherit = ["mail.thread"]
    _order = "create_date desc"

    name = fields.Char(readonly=True, copy=False, default="New")
    visit_id = fields.Many2one("hms.visit", required=True)
    patient_id = fields.Many2one(related="visit_id.patient_id", store=True)
    patient_group = fields.Selection(related="patient_id.blood_group", string="Patient Blood Group")
    doctor_id = fields.Many2one("hms.practitioner", default=lambda self: self.env["hms.practitioner"].get_current())
    component = fields.Selection(COMPONENTS, default="prbc", required=True)
    units_requested = fields.Integer(default=1, required=True)
    urgency = fields.Selection([("routine", "Routine"), ("urgent", "Urgent"), ("massive", "Massive Transfusion")], default="routine")
    indication = fields.Char(required=True)
    unit_ids = fields.One2many("hms.blood.unit", "request_id", string="Reserved / Issued Units")
    crossmatch_done = fields.Boolean(string="Crossmatch compatible")
    crossmatch_by_id = fields.Many2one("hms.practitioner")
    verify1_id = fields.Many2one("hms.practitioner", string="Verified By (1)", readonly=True)
    verify2_id = fields.Many2one("hms.practitioner", string="Verified By (2)", readonly=True)
    state = fields.Selection([("requested", "Requested"), ("reserved", "Units Reserved"), ("verified", "Two-Person Verified"), ("issued", "Issued"), ("cancelled", "Cancelled")], default="requested", tracking=True)
    price_per_unit = fields.Float(default=3500.0)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("hms.blood.request") or "New"
        recs = super().create(vals_list)
        for rec in recs:
            if not any(c.kind == "blood" for c in rec.visit_id.consent_ids):
                self.env["hms.consent"].create({"visit_id": rec.visit_id.id, "kind": "blood"})
        return recs

    def action_reserve(self):
        Unit = self.env["hms.blood.unit"]
        for rec in self:
            if not rec.patient_group:
                raise UserError(_("Patient blood group is not recorded. Group & screen first."))
            ok_groups = COMPATIBLE.get(rec.patient_group, [rec.patient_group])
            units = Unit.search([("state", "=", "available"), ("component", "=", rec.component), ("blood_group", "in", ok_groups),
                                 ("screening_done", "=", True), ("expiry_date", ">=", fields.Date.today())], order="expiry_date", limit=rec.units_requested)
            if len(units) < rec.units_requested:
                raise UserError(_("Only %s compatible screened unit(s) available (need %s).") % (len(units), rec.units_requested))
            units.write({"state": "reserved", "request_id": rec.id})
            rec.state = "reserved"

    def action_verify(self):
        me = self.env["hms.practitioner"].get_current()
        for rec in self:
            if not rec.crossmatch_done:
                raise UserError(_("Record the crossmatch result first."))
            if not rec.verify1_id:
                rec.verify1_id = me
                rec.message_post(body=_("First verification by %s.") % me.display_name)
            elif rec.verify1_id == me:
                raise UserError(_("Two-person verification requires a second, different person."))
            else:
                consent_ok = any(c.kind == "blood" and c.state == "signed" for c in rec.visit_id.consent_ids)
                if not consent_ok:
                    raise UserError(_("Transfusion consent is not signed."))
                rec.write({"verify2_id": me.id, "state": "verified"})

    def action_issue(self):
        for rec in self:
            if rec.state != "verified":
                raise UserError(_("Two-person verification must be complete before issue."))
            rec.unit_ids.write({"state": "issued"})
            rec.state = "issued"
            product = self.env.ref("stratos_hms.product_blood_unit", raise_if_not_found=False) or self.env["product.product"].sudo().create({"name": "Blood unit", "type": "service", "list_price": rec.price_per_unit})
            self.env["hms.charge"].create({
                "visit_id": rec.visit_id.id, "product_id": product.id, "description": f"Blood: {dict(COMPONENTS)[rec.component]} × {len(rec.unit_ids)}",
                "quantity": len(rec.unit_ids), "price_unit": rec.price_per_unit, "source": "blood",
            })
            rec.visit_id.message_post(body=_("Blood issued: %s (verified by %s and %s).") % (", ".join(rec.unit_ids.mapped("name")), rec.verify1_id.display_name, rec.verify2_id.display_name))

    def action_cancel(self):
        for rec in self:
            rec.unit_ids.filtered(lambda u: u.state == "reserved").write({"state": "available", "request_id": False})
            rec.state = "cancelled"
