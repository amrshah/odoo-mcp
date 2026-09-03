# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    zelix_backend_url = fields.Char(
        string="Zelix Copilot Backend URL",
        default="http://zelix_copilot:8010",
        config_parameter="zelix_ai.backend_url",
        help="URL of the Zelix Copilot Backend orchestrator service.",
    )
    zelix_bitnet_model = fields.Char(
        string="BitNet Model Path",
        default="/models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf",
        config_parameter="zelix_ai.bitnet_model",
        help="Model path identifier on the Alamia AI / BitNet runtime.",
    )
    zelix_auto_context = fields.Boolean(
        string="Auto-Inject Active Record Context",
        default=True,
        config_parameter="zelix_ai.auto_context",
        help="Automatically capture active patient, appointment, and encounter context from the current Odoo view.",
    )
