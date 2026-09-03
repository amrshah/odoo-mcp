# -*- coding: utf-8 -*-
from odoo import fields, models


class ZelixCopilotAudit(models.Model):
    _name = "zelix.copilot.audit"
    _description = "Zelix AI Copilot Audit Trail"
    _order = "create_date desc"

    request_id = fields.Char(string="Request ID", required=True, index=True)
    user_id = fields.Many2one("res.users", string="Clinician / User", default=lambda self: self.env.user)
    role = fields.Char(string="Clinical Role", default="veterinarian")
    workflow_id = fields.Char(string="Workflow Identifier", required=True)
    model_used = fields.Char(string="AI Model Used")
    patient_id = fields.Many2one("vet.patient", string="Associated Patient")
    prompt_text = fields.Text(string="User Input Prompt")
    response_text = fields.Text(string="AI Response / Output")
    validation_status = fields.Selection(
        [("passed", "Passed"), ("failed", "Failed"), ("skipped", "Skipped")],
        string="Validation Status",
        default="passed",
    )
    validation_errors = fields.Text(string="Validation Errors")
    action_cards_count = fields.Integer(string="Proposed Actions Count", default=0)
    execution_status = fields.Selection(
        [
            ("proposed", "Proposed / Pending Approval"),
            ("approved", "Approved & Executed"),
            ("rejected", "Rejected by User"),
            ("failed", "Execution Failed"),
        ],
        string="Execution Status",
        default="proposed",
    )
    odoo_record_ref = fields.Char(string="Created/Updated Odoo Record")
