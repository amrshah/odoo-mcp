from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    vet_default_clinic_id = fields.Many2one("vet.clinic", string="Default Clinic", domain="[('company_id', '=', company_id)]", config_parameter="vetcairn.default_clinic_id")
    vet_appointment_slot_minutes = fields.Integer(string="Default Slot (Minutes)", default=30, config_parameter="vetcairn.appointment_slot_minutes")
    vet_appointment_buffer_minutes = fields.Integer(string="Scheduling Buffer (Minutes)", default=0, config_parameter="vetcairn.appointment_buffer_minutes")
    vet_require_appointment_confirmation = fields.Boolean(string="Require Appointment Confirmation", default=True, config_parameter="vetcairn.require_appointment_confirmation")
    vet_allow_provider_overlap = fields.Boolean(string="Allow Provider Schedule Overlap", config_parameter="vetcairn.allow_provider_overlap")
    vet_require_patient_weight = fields.Boolean(string="Require Weight During Consultation", default=True, config_parameter="vetcairn.require_patient_weight")
    vet_require_clinical_diagnosis = fields.Boolean(string="Require Diagnosis Before Completion", config_parameter="vetcairn.require_clinical_diagnosis")
    vet_document_expiry_warning_days = fields.Integer(string="Document Expiry Warning (Days)", default=30, config_parameter="vetcairn.document_expiry_warning_days")
    vet_vaccine_due_warning_days = fields.Integer(string="Vaccination Due Warning (Days)", default=30, config_parameter="vetcairn.vaccine_due_warning_days")
    vet_inventory_expiry_warning_days = fields.Integer(string="Stock Expiry Warning (Days)", default=90, config_parameter="vetcairn.inventory_expiry_warning_days")
    vet_require_controlled_purchase_review = fields.Boolean(string="Review Controlled-Item Purchases", default=True, config_parameter="vetcairn.require_controlled_purchase_review")
    vet_require_estimate_approval = fields.Boolean(string="Require Estimate Approval", default=True, config_parameter="vetcairn.require_estimate_approval")
    vet_default_deposit_percent = fields.Float(string="Default Deposit (%)", default=0, config_parameter="vetcairn.default_deposit_percent")
    vet_default_communication_channel = fields.Selection([("phone", "Phone Call"), ("email", "Email"), ("sms", "SMS"), ("postal", "Postal Mail")], default="phone", required=True, config_parameter="vetcairn.default_communication_channel")
    vet_enforce_communication_consent = fields.Boolean(string="Enforce Client Communication Consent", default=True, config_parameter="vetcairn.enforce_communication_consent")
    vet_default_task_due_days = fields.Integer(string="Default Task Due (Days)", default=1, config_parameter="vetcairn.default_task_due_days")
    vet_dashboard_refresh_minutes = fields.Integer(string="Dashboard Refresh Guidance (Minutes)", default=5, config_parameter="vetcairn.dashboard_refresh_minutes")

    @api.constrains("vet_appointment_slot_minutes", "vet_appointment_buffer_minutes", "vet_document_expiry_warning_days", "vet_vaccine_due_warning_days", "vet_inventory_expiry_warning_days", "vet_default_task_due_days", "vet_dashboard_refresh_minutes", "vet_default_deposit_percent")
    def _check_vet_settings_values(self):
        for settings in self:
            non_negative = (settings.vet_appointment_buffer_minutes, settings.vet_document_expiry_warning_days, settings.vet_vaccine_due_warning_days, settings.vet_inventory_expiry_warning_days, settings.vet_default_task_due_days)
            if settings.vet_appointment_slot_minutes <= 0 or settings.vet_dashboard_refresh_minutes <= 0 or any(value < 0 for value in non_negative):
                raise ValidationError("Durations and warning periods must be positive or zero as appropriate.")
            if not 0 <= settings.vet_default_deposit_percent <= 100:
                raise ValidationError("The default deposit percentage must be between 0 and 100.")
