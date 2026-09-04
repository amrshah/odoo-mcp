from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class ResUsers(models.Model):
    _inherit="res.users"
    vet_all_clinic_access=fields.Boolean(string="All Veterinary Clinics",default=True)

class VetWard(models.Model):
    _name="vet.ward"; _description="Veterinary Ward"; _order="clinic_id,name"
    name=fields.Char(required=True); active=fields.Boolean(default=True); company_id=fields.Many2one("res.company",required=True,default=lambda s:s.env.company); clinic_id=fields.Many2one("vet.clinic",required=True,ondelete="cascade"); notes=fields.Text()

class VetBed(models.Model):
    _name="vet.bed"; _description="Veterinary Bed / Cage"; _order="ward_id,name"
    name=fields.Char(required=True); active=fields.Boolean(default=True); company_id=fields.Many2one(related="ward_id.company_id",store=True); clinic_id=fields.Many2one(related="ward_id.clinic_id",store=True); ward_id=fields.Many2one("vet.ward",required=True,ondelete="cascade"); species_id=fields.Many2one("vet.species"); status=fields.Selection([("available","Available"),("occupied","Occupied"),("cleaning","Cleaning"),("maintenance","Maintenance")],default="available",required=True); notes=fields.Text()

class VetAdmission(models.Model):
    _name="vet.admission"; _description="Veterinary Admission"; _inherit=["mail.thread","mail.activity.mixin"]; _order="admitted_at desc"
    name=fields.Char(required=True,readonly=True,default=lambda s:s.env._("New")); company_id=fields.Many2one("res.company",required=True,default=lambda s:s.env.company); clinic_id=fields.Many2one("vet.clinic",required=True); patient_id=fields.Many2one("vet.patient",required=True); client_id=fields.Many2one(related="patient_id.primary_owner_id",store=True); encounter_id=fields.Many2one("vet.encounter"); attending_id=fields.Many2one("res.users",required=True,default=lambda s:s.env.user); ward_id=fields.Many2one("vet.ward",required=True); bed_id=fields.Many2one("vet.bed",required=True,domain="[('ward_id','=',ward_id)]"); admitted_at=fields.Datetime(default=fields.Datetime.now,required=True); expected_discharge=fields.Datetime(); discharged_at=fields.Datetime(readonly=True); state=fields.Selection([("draft","Draft"),("admitted","Admitted"),("ready","Ready for Discharge"),("discharged","Discharged"),("cancelled","Cancelled")],default="draft",required=True,tracking=True); reason=fields.Text(required=True); discharge_summary=fields.Html(); handover_notes=fields.Text()
    @api.model_create_multi
    def create(self,vals):
        for v in vals:
            if v.get("name",self.env._("New"))==self.env._("New"): v["name"]=self.env["ir.sequence"].next_by_code("vet.admission") or self.env._("New")
        return super().create(vals)
    def action_admit(self):
        if self.filtered(lambda r:r.state!="draft" or r.bed_id.status!="available"): raise ValidationError("Only draft admissions with an available bed can be admitted.")
        self.mapped("bed_id").write({"status":"occupied"}); self.write({"state":"admitted"})
    def action_ready(self): self.write({"state":"ready"})
    def action_discharge(self):
        if self.filtered(lambda r:r.state not in ("admitted","ready") or not r.discharge_summary): raise ValidationError("A discharge summary is required.")
        self.mapped("bed_id").write({"status":"cleaning"}); self.write({"state":"discharged","discharged_at":fields.Datetime.now()})

class VetInsuranceClaim(models.Model):
    _name="vet.insurance.claim"; _description="Veterinary Insurance Claim"; _inherit=["mail.thread","mail.activity.mixin"]
    name=fields.Char(required=True,readonly=True,default=lambda s:s.env._("New")); company_id=fields.Many2one("res.company",required=True,default=lambda s:s.env.company); clinic_id=fields.Many2one("vet.clinic",required=True); patient_id=fields.Many2one("vet.patient",required=True); client_id=fields.Many2one(related="patient_id.primary_owner_id",store=True); insurer_id=fields.Many2one("res.partner",required=True); policy_number=fields.Char(required=True); invoice_id=fields.Many2one("account.move",required=True,domain="[('move_type','=','out_invoice')]"); currency_id=fields.Many2one(related="invoice_id.currency_id"); claimed_amount=fields.Monetary(required=True); approved_amount=fields.Monetary(); paid_amount=fields.Monetary(); state=fields.Selection([("draft","Draft"),("submitted","Submitted"),("review","Under Review"),("approved","Approved"),("part_paid","Part Paid"),("paid","Paid"),("declined","Declined"),("cancelled","Cancelled")],default="draft",required=True,tracking=True); submitted_at=fields.Datetime(readonly=True); decision_reference=fields.Char(); decline_reason=fields.Text()
    @api.model_create_multi
    def create(self,vals):
        for v in vals:
            if v.get("name",self.env._("New"))==self.env._("New"): v["name"]=self.env["ir.sequence"].next_by_code("vet.insurance.claim") or self.env._("New")
        return super().create(vals)
    def action_submit(self): self.write({"state":"submitted","submitted_at":fields.Datetime.now()})

class VetFinancialAdjustment(models.Model):
    _name="vet.financial.adjustment"; _description="Veterinary Financial Adjustment"; _inherit=["mail.thread","mail.activity.mixin"]
    name=fields.Char(required=True,readonly=True,default=lambda s:s.env._("New")); company_id=fields.Many2one("res.company",required=True,default=lambda s:s.env.company); clinic_id=fields.Many2one("vet.clinic",required=True); partner_id=fields.Many2one("res.partner",required=True); patient_id=fields.Many2one("vet.patient"); invoice_id=fields.Many2one("account.move",required=True); adjustment_type=fields.Selection([("credit","Credit"),("refund","Refund"),("writeoff","Write-off"),("return","Return"),("deposit","Deposit")],required=True); currency_id=fields.Many2one(related="invoice_id.currency_id"); amount=fields.Monetary(required=True); reason=fields.Text(required=True); state=fields.Selection([("draft","Draft"),("approved","Approved"),("posted","Posted"),("cancelled","Cancelled")],default="draft",required=True,tracking=True); approved_by_id=fields.Many2one("res.users",readonly=True); posted_move_id=fields.Many2one("account.move",readonly=True)
    @api.model_create_multi
    def create(self,vals):
        for v in vals:
            if v.get("name",self.env._("New"))==self.env._("New"): v["name"]=self.env["ir.sequence"].next_by_code("vet.financial.adjustment") or self.env._("New")
        return super().create(vals)
    @api.constrains("amount")
    def _positive(self):
        if any(r.amount<=0 for r in self): raise ValidationError("Adjustment amount must be positive.")
    def action_approve(self): self.write({"state":"approved","approved_by_id":self.env.user.id})

class VetMigrationBatch(models.Model):
    _name="vet.migration.batch"; _description="Veterinary Migration Rehearsal"; _inherit=["mail.thread","mail.activity.mixin"]
    name=fields.Char(required=True); source=fields.Char(required=True); company_id=fields.Many2one("res.company",required=True,default=lambda s:s.env.company); state=fields.Selection([("draft","Draft"),("validated","Validated"),("ready","Ready"),("rehearsed","Rehearsed"),("cancelled","Cancelled")],default="draft",required=True,tracking=True); line_ids=fields.One2many("vet.migration.line","batch_id"); notes=fields.Text(); validated_at=fields.Datetime(readonly=True); rehearsal_at=fields.Datetime(readonly=True)
    def action_validate(self):
        for b in self:
            b.line_ids._validate_line(); b.write({"state":"validated","validated_at":fields.Datetime.now()})
    def action_ready(self):
        if self.mapped("line_ids").filtered(lambda l:l.status=="error"): raise ValidationError("Resolve validation errors first.")
        self.write({"state":"ready"})
    def action_rehearse(self): self.write({"state":"rehearsed","rehearsal_at":fields.Datetime.now()})

class VetMigrationLine(models.Model):
    _name="vet.migration.line"; _description="Veterinary Migration Staging Line"
    batch_id=fields.Many2one("vet.migration.batch",required=True,ondelete="cascade"); sequence=fields.Integer(default=10); record_type=fields.Selection([("client","Client"),("patient","Patient"),("appointment","Appointment"),("product","Product"),("invoice","Invoice")],required=True); source_key=fields.Char(required=True); target_model=fields.Char(); target_id=fields.Integer(); payload=fields.Json(required=True); status=fields.Selection([("pending","Pending"),("valid","Valid"),("warning","Warning"),("error","Error")],default="pending",required=True); message=fields.Text(); duplicate_key=fields.Char()
    def _validate_line(self):
        for l in self:
            if not l.payload: l.write({"status":"error","message":"Payload is empty."})
            elif not l.payload.get("name"): l.write({"status":"warning","message":"Name is missing; review before rehearsal."})
            else: l.write({"status":"valid","message":"Structure validated; no production record created."})
