from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HmsTheatre(models.Model):
    _name = "hms.theatre"
    _description = "Operation Theatre"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)


class HmsSurgery(models.Model):
    """Full theatre workflow with the WHO Surgical Safety Checklist as three hard gates:
    Sign In (before anaesthesia) → Time Out (before incision) → Sign Out (before leaving theatre)."""
    _name = "hms.surgery"
    _description = "Surgery / Procedure"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "scheduled_at desc"

    name = fields.Char(readonly=True, copy=False, default="New")
    visit_id = fields.Many2one("hms.visit", required=True, ondelete="restrict")
    admission_id = fields.Many2one("hms.admission", ondelete="set null")
    patient_id = fields.Many2one(related="visit_id.patient_id", store=True)
    has_allergy = fields.Boolean(related="patient_id.has_allergy")
    allergy_summary = fields.Char(related="visit_id.allergy_summary")
    procedure = fields.Char(required=True)
    procedure_product_id = fields.Many2one("product.product", string="Procedure (billing)")
    price = fields.Float(string="Procedure Charge (PKR)")
    surgeon_id = fields.Many2one("hms.practitioner", required=True, domain="[('is_doctor','=',True)]")
    anaesthetist_id = fields.Many2one("hms.practitioner", domain="[('is_doctor','=',True)]")
    theatre_id = fields.Many2one("hms.theatre", required=True)
    scheduled_at = fields.Datetime(required=True, default=fields.Datetime.now)
    started_at = fields.Datetime(readonly=True)
    ended_at = fields.Datetime(readonly=True)
    anaesthesia_type = fields.Selection([("ga", "General"), ("spinal", "Spinal"), ("local", "Local"), ("sedation", "Sedation")], default="ga")
    state = fields.Selection([("scheduled", "Scheduled"), ("sign_in", "Signed In"), ("time_out", "Time Out Done"), ("in_progress", "In Progress"), ("sign_out", "Signed Out"), ("completed", "Completed"), ("cancelled", "Cancelled")], default="scheduled", tracking=True)
    # WHO checklist — Sign In
    si_identity_confirmed = fields.Boolean(string="Patient identity, site, procedure & consent confirmed")
    si_site_marked = fields.Boolean(string="Site marked / not applicable")
    si_anaesthesia_check = fields.Boolean(string="Anaesthesia machine & medication check complete")
    si_pulse_ox = fields.Boolean(string="Pulse oximeter on patient and functioning")
    si_allergy_known = fields.Boolean(string="Known allergy reviewed")
    si_airway_risk = fields.Boolean(string="Difficult airway / aspiration risk assessed")
    si_blood_loss_risk = fields.Boolean(string="Risk of >500 ml blood loss assessed (IV access / blood available)")
    # Time Out
    to_team_introduced = fields.Boolean(string="All team members introduced by name and role")
    to_confirm_patient = fields.Boolean(string="Patient name, procedure and incision site confirmed")
    to_antibiotic = fields.Boolean(string="Antibiotic prophylaxis given within last 60 min / not applicable")
    to_critical_events = fields.Boolean(string="Anticipated critical events reviewed (surgeon, anaesthetist, nursing)")
    to_imaging = fields.Boolean(string="Essential imaging displayed / not applicable")
    # Sign Out
    so_procedure_recorded = fields.Boolean(string="Name of procedure recorded")
    so_counts_correct = fields.Boolean(string="Instrument, sponge and needle counts correct")
    so_specimen_labelled = fields.Boolean(string="Specimen labelled (patient name) / not applicable")
    so_equipment_issues = fields.Boolean(string="Equipment problems addressed")
    so_recovery_concerns = fields.Boolean(string="Key concerns for recovery communicated")
    operative_note = fields.Text()
    consent_ok = fields.Boolean(compute="_compute_consent_ok")

    @api.depends("visit_id.consent_ids.state")
    def _compute_consent_ok(self):
        for rec in self:
            rec.consent_ok = any(c.kind == "surgery" and c.state == "signed" for c in rec.visit_id.consent_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("hms.surgery") or "New"
        recs = super().create(vals_list)
        for rec in recs:
            if not any(c.kind == "surgery" for c in rec.visit_id.consent_ids):
                self.env["hms.consent"].create({"visit_id": rec.visit_id.id, "kind": "surgery"})
        return recs

    def _require(self, fields_, label):
        for rec in self:
            missing = [rec._fields[f].string for f in fields_ if not rec[f]]
            if missing:
                raise UserError(_("%s checklist incomplete:\n• %s") % (label, "\n• ".join(missing)))

    def action_sign_in(self):
        for rec in self:
            if not rec.consent_ok:
                raise UserError(_("Surgical consent has not been signed. Sign In blocked."))
            rec._require(["si_identity_confirmed", "si_site_marked", "si_anaesthesia_check", "si_pulse_ox", "si_allergy_known", "si_airway_risk", "si_blood_loss_risk"], "WHO Sign In")
            rec.state = "sign_in"

    def action_time_out(self):
        for rec in self:
            rec._require(["to_team_introduced", "to_confirm_patient", "to_antibiotic", "to_critical_events", "to_imaging"], "WHO Time Out")
            rec.write({"state": "in_progress", "started_at": fields.Datetime.now()})

    def action_sign_out(self):
        for rec in self:
            rec._require(["so_procedure_recorded", "so_counts_correct", "so_specimen_labelled", "so_equipment_issues", "so_recovery_concerns"], "WHO Sign Out")
            rec.write({"state": "completed", "ended_at": fields.Datetime.now()})
            product = rec.procedure_product_id or self.env["product.product"].sudo().create({"name": rec.procedure, "type": "service", "list_price": rec.price})
            rec.procedure_product_id = product
            self.env["hms.charge"].create({
                "visit_id": rec.visit_id.id, "product_id": product.id, "description": f"Surgery: {rec.procedure} ({rec.surgeon_id.display_name})",
                "quantity": 1, "price_unit": rec.price, "source": "surgery",
            })
            rec.visit_id._advance_stage("treatment")
            rec.visit_id.message_post(body=_("Surgery completed: %s. WHO checklist complete (sign in / time out / sign out).") % rec.procedure)

    def action_cancel(self):
        self.write({"state": "cancelled"})
