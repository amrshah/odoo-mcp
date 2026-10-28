import json
import logging

import requests

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class VetCmAiClient(models.AbstractModel):
    """Pluggable AI provider. 'mock' works offline for demos and training."""
    _name = "vet.cm.ai.client"
    _description = "Vet Case Memory AI client"

    @api.model
    def _cfg(self, key, default=False):
        return self.env["ir.config_parameter"].sudo().get_param("vet_cm." + key, default)

    @api.model
    def _complete(self, system, user, json_mode=False, mock_payload=None):
        if self._cfg("ai_enabled") != "True":
            raise UserError(_("The AI layer is switched off (Settings → Vet Clinical "
                              "Suggestions). Everything else works without it."))
        provider = self._cfg("ai_provider", "mock")
        model = self._cfg("ai_model") or False
        key = self._cfg("ai_api_key") or False
        if provider == "mock":
            if mock_payload is not None:
                return mock_payload
            return _("[Demo mode – no AI provider connected] The matched cases share the key "
                     "signs and species of this patient; check vitals, weight-based doses "
                     "and the safety warnings before approving.")
        if not key:
            raise UserError(_("Add the API key in Settings → Vet Clinical Suggestions."))
        try:
            if provider == "anthropic":
                resp = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                             "content-type": "application/json"},
                    data=json.dumps({
                        "model": model or "claude-sonnet-5-5",
                        "max_tokens": 1200,
                        "system": system,
                        "messages": [{"role": "user", "content": user}],
                    }), timeout=60)
                resp.raise_for_status()
                return "".join(b.get("text", "") for b in resp.json().get("content", []))
            if provider == "openai":
                body = {
                    "model": model or "gpt-4.1-mini",
                    "messages": [{"role": "system", "content": system},
                                 {"role": "user", "content": user}],
                }
                if json_mode:
                    body["response_format"] = {"type": "json_object"}
                resp = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}",
                             "Content-Type": "application/json"},
                    data=json.dumps(body), timeout=60)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except requests.RequestException as e:
            _logger.warning("Vet case memory AI call failed: %s", e)
            raise UserError(_("The AI provider could not be reached: %s", e))
        raise UserError(_("Unknown AI provider: %s", provider))
