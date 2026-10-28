from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    vet_cm_w_symptoms = fields.Integer("Symptoms weight", config_parameter="vet_cm.w_symptoms",
                                       default=50)
    vet_cm_w_age = fields.Integer("Age weight", config_parameter="vet_cm.w_age", default=15)
    vet_cm_w_weight = fields.Integer("Body-weight weight", config_parameter="vet_cm.w_weight",
                                     default=10)
    vet_cm_w_breed = fields.Integer("Breed weight", config_parameter="vet_cm.w_breed", default=10)
    vet_cm_w_vitals = fields.Integer("Vitals weight", config_parameter="vet_cm.w_vitals",
                                     default=15)
    vet_cm_min_cases = fields.Integer("Minimum similar cases", config_parameter="vet_cm.min_cases",
                                      default=3)
    vet_cm_min_similarity = fields.Integer("Minimum similarity %",
                                           config_parameter="vet_cm.min_similarity", default=35)
    vet_cm_min_confidence = fields.Integer("Minimum confidence %",
                                           config_parameter="vet_cm.min_confidence", default=40)
    vet_cm_max_matches = fields.Integer("Max cases compared", config_parameter="vet_cm.max_matches",
                                        default=20)
    vet_cm_voice_lang = fields.Selection([
        ("en-US", "English"), ("en-GB", "English (UK)"), ("ur-PK", "Urdu"),
    ], string="Default dictation language", config_parameter="vet_cm.voice_lang", default="en-US")
    vet_cm_ai_enabled = fields.Boolean("Enable AI layer", config_parameter="vet_cm.ai_enabled")
    vet_cm_ai_provider = fields.Selection([
        ("mock", "Demo mode (no provider)"), ("anthropic", "Anthropic (Claude)"),
        ("openai", "OpenAI"),
    ], string="AI provider", config_parameter="vet_cm.ai_provider", default="mock")
    vet_cm_ai_model = fields.Char("AI model", config_parameter="vet_cm.ai_model")
    vet_cm_ai_api_key = fields.Char("API key", config_parameter="vet_cm.ai_api_key")

    def action_vet_cm_load_demo(self):
        return self.env["vet.cm.demo.loader"].action_load_demo()
