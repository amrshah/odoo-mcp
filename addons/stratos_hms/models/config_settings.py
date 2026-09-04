from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    hms_ai_provider = fields.Selection(
        [("none", "Offline — memory, learned rules & protocols only"), ("anthropic", "Anthropic Claude"), ("openai", "OpenAI")],
        string="AI Provider", default="none", config_parameter="stratos_hms.ai_provider",
    )
    hms_anthropic_api_key = fields.Char(string="Anthropic API Key", config_parameter="stratos_hms.anthropic_api_key")
    hms_anthropic_model = fields.Char(string="Anthropic Model", default="claude-sonnet-4-5", config_parameter="stratos_hms.anthropic_model")
    hms_openai_api_key = fields.Char(string="OpenAI API Key", config_parameter="stratos_hms.openai_api_key")
    hms_openai_model = fields.Char(string="OpenAI Model", default="gpt-4o", config_parameter="stratos_hms.openai_model")
    hms_ai_timeout = fields.Integer(string="AI Timeout (s)", default=60, config_parameter="stratos_hms.ai_timeout")
    hms_hold_unpaid = fields.Boolean(string="Hold file until consultation fee is paid", default=True, config_parameter="stratos_hms.hold_unpaid")
    hms_registration_fee = fields.Float(string="Registration Fee (first visit)", default=200.0, config_parameter="stratos_hms.registration_fee")
    hms_speech_lang = fields.Selection([("en-PK", "English (Pakistan)"), ("ur-PK", "Urdu"), ("en-US", "English (US)")], string="Default Scribe Language", default="en-PK", config_parameter="stratos_hms.speech_lang")
    hms_hospital_tagline = fields.Char(string="Hospital Tagline on Documents", config_parameter="stratos_hms.tagline")

    def action_hms_test_ai(self):
        msg = self.env["hms.ai.service"].test_connection()
        return {"type": "ir.actions.client", "tag": "display_notification", "params": {"title": "AI connection", "message": msg, "type": "success", "sticky": False}}
