# -*- coding: utf-8 -*-
import logging
import requests
from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # Core AI Provider Switch
    zelix_ai_provider = fields.Selection(
        [
            ("offline", "Offline — Case Memory, Learned Rules & Protocols Only"),
            ("cloudflare", "Alamia AI Gateway & Edge Workers"),
            ("bitnet", "Microsoft BitNet 1.58b (Alamia AI Remote Endpoint)"),
            ("ollama", "Local Ollama (Gemma 3 / Qwen 2.5 / DeepSeek)"),
            ("anthropic", "Anthropic Claude (Sonnet 3.5 / 4.5)"),
            ("openai", "OpenAI (GPT-4o / GPT-4o-mini)"),
        ],
        string="AI Provider",
        default="cloudflare",
        config_parameter="zelix_ai.ai_provider",
        help="Select the AI reasoning provider for Zelix Copilot.",
    )

    # Alamia AI Gateway & Edge Workers (CF Powered)
    zelix_cf_account_id = fields.Char(
        string="Alamia Account ID",
        default="be941241fb3499e9567c7ec28528c984",
        config_parameter="zelix_ai.cf_account_id",
    )
    zelix_cf_api_token = fields.Char(
        string="Alamia AI API Token",
        config_parameter="zelix_ai.cf_api_token",
    )
    zelix_cf_gateway_id = fields.Char(
        string="Alamia Gateway Slug (Optional)",
        config_parameter="zelix_ai.cf_gateway_id",
        help="Optional Alamia AI Gateway slug for response caching and request telemetry.",
    )
    zelix_cf_model = fields.Selection(
        [
            ("@cf/meta/llama-3.1-8b-instruct-fp8", "Alamia Llama 3.1 8B (Fast & Accurate)"),
            ("@cf/meta/llama-3.2-3b-instruct", "Alamia Llama 3.2 3B (Lightweight)"),
            ("@cf/deepseek-ai/deepseek-r1-distill-qwen-32b", "Alamia DeepSeek R1 32B (Clinical Reasoning)"),
        ],
        string="Alamia AI Model",
        default="@cf/meta/llama-3.1-8b-instruct-fp8",
        config_parameter="zelix_ai.cf_model",
    )

    # BitNet / Alamia Remote Provider
    zelix_bitnet_url = fields.Char(
        string="BitNet Endpoint URL",
        default="https://ai.alamiaconnect.com",
        config_parameter="zelix_ai.bitnet_url",
    )
    zelix_bitnet_api_key = fields.Char(
        string="BitNet API Key",
        default="",
        config_parameter="zelix_ai.bitnet_api_key",
    )
    zelix_bitnet_model = fields.Char(
        string="BitNet Model Path",
        default="/models/BitNet-b1.58-2B-4T/ggml-model-i2_s.gguf",
        config_parameter="zelix_ai.bitnet_model",
    )

    # Local Ollama Provider
    zelix_ollama_host = fields.Char(
        string="Ollama Host URL",
        default="http://localhost:11434",
        config_parameter="zelix_ai.ollama_host",
    )
    zelix_ollama_model = fields.Char(
        string="Ollama Model",
        default="gemma3:1b-it-qat",
        config_parameter="zelix_ai.ollama_model",
    )

    # Cloud Providers
    zelix_anthropic_api_key = fields.Char(
        string="Anthropic API Key",
        config_parameter="zelix_ai.anthropic_api_key",
    )
    zelix_anthropic_model = fields.Char(
        string="Anthropic Model",
        default="claude-sonnet-4-5",
        config_parameter="zelix_ai.anthropic_model",
    )
    zelix_openai_api_key = fields.Char(
        string="OpenAI API Key",
        config_parameter="zelix_ai.openai_api_key",
    )
    zelix_openai_model = fields.Char(
        string="OpenAI Model",
        default="gpt-4o",
        config_parameter="zelix_ai.openai_model",
    )

    # General & Speech Settings
    zelix_backend_url = fields.Char(
        string="Zelix Copilot Backend URL",
        default="http://zelix_copilot:8010",
        config_parameter="zelix_ai.backend_url",
        help="URL of the Zelix Copilot Backend orchestrator service.",
    )
    zelix_ai_timeout = fields.Integer(
        string="AI Timeout (seconds)",
        default=60,
        config_parameter="zelix_ai.timeout",
    )
    zelix_speech_lang = fields.Selection(
        [
            ("en-US", "English (United States)"),
            ("en-PK", "English (Pakistan)"),
            ("ur-PK", "Urdu (Pakistan)"),
            ("en-GB", "English (UK)"),
        ],
        string="Default Scribe Speech Language",
        default="en-US",
        config_parameter="zelix_ai.speech_lang",
        help="Browser Web Speech API language for ambient consultation recording.",
    )
    zelix_auto_context = fields.Boolean(
        string="Auto-Inject Active Record Context",
        default=True,
        config_parameter="zelix_ai.auto_context",
        help="Automatically capture active patient, appointment, and encounter context from the current Odoo view.",
    )

    def action_zelix_test_ai(self):
        """Ping the configured AI provider to verify connectivity and latency."""
        self.ensure_one()
        provider = self.zelix_ai_provider or "offline"
        timeout = self.zelix_ai_timeout or 30

        try:
            if provider == "offline":
                case_count = self.env["zelix.case.memory"].sudo().search_count([])
                rule_count = self.env["zelix.ai.rule"].sudo().search_count([("active", "=", True)])
                msg = f"Offline mode active. Institutional memory: {case_count} cases, {rule_count} learned clinician rules available."
                return self._notify("success", "Zelix AI Offline Engine", msg)

            elif provider == "cloudflare":
                account_id = self.zelix_cf_account_id or "be941241fb3499e9567c7ec28528c984"
                token = self.zelix_cf_api_token
                if not token:
                    raise UserError(_("Please provide an Alamia AI API Token in settings."))
                gateway_id = self.zelix_cf_gateway_id
                if gateway_id:
                    url = f"https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/workers-ai/v1/chat/completions"
                else:
                    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1/chat/completions"
                resp = requests.post(
                    url,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={
                        "model": self.zelix_cf_model or "@cf/meta/llama-3.1-8b-instruct-fp8",
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 10,
                    },
                    timeout=timeout,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    msg = f"Alamia AI Gateway & Edge Online! Model: {self.zelix_cf_model}."
                    return self._notify("success", "Alamia AI Connection Succeeded", msg)
                else:
                    msg = f"Alamia AI returned HTTP {resp.status_code}: {resp.text[:200]}"
                    return self._notify("warning", "Alamia AI Warning", msg)

            elif provider == "bitnet":
                url = (self.zelix_bitnet_url or "https://ai.alamiaconnect.com").rstrip("/")
                headers = {}
                if self.zelix_bitnet_api_key:
                    headers["Authorization"] = f"Bearer {self.zelix_bitnet_api_key}"
                resp = requests.get(f"{url}/health", headers=headers, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    msg = f"BitNet Remote Engine Online ({data.get('status', 'OK')}) at {url}. Model: {self.zelix_bitnet_model}"
                    return self._notify("success", "BitNet Connection Succeeded", msg)
                else:
                    msg = f"BitNet responded with HTTP {resp.status_code}: {resp.text[:200]}"
                    return self._notify("warning", "BitNet Server Warning", msg)

            elif provider == "ollama":
                url = (self.zelix_ollama_host or "http://localhost:11434").rstrip("/")
                resp = requests.get(f"{url}/api/tags", timeout=timeout)
                if resp.status_code == 200:
                    models_list = [m.get("name") for m in resp.json().get("models", [])]
                    msg = f"Ollama instance reachable at {url}. Available models: {', '.join(models_list[:5])}"
                    return self._notify("success", "Ollama Connection Succeeded", msg)
                else:
                    return self._notify("warning", "Ollama Warning", f"Ollama HTTP {resp.status_code}")

            elif provider == "anthropic":
                if not self.zelix_anthropic_api_key:
                    raise UserError(_("Please provide an Anthropic API Key."))
                resp = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.zelix_anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.zelix_anthropic_model or "claude-sonnet-4-5",
                        "max_tokens": 10,
                        "messages": [{"role": "user", "content": "ping"}],
                    },
                    timeout=timeout,
                )
                if resp.status_code == 200:
                    return self._notify("success", "Anthropic Claude Connected", f"Model {self.zelix_anthropic_model} validated.")
                else:
                    return self._notify("warning", "Anthropic API Error", f"HTTP {resp.status_code}: {resp.text[:200]}")

            elif provider == "openai":
                if not self.zelix_openai_api_key:
                    raise UserError(_("Please provide an OpenAI API Key."))
                resp = requests.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {self.zelix_openai_api_key}"},
                    timeout=timeout,
                )
                if resp.status_code == 200:
                    return self._notify("success", "OpenAI Connected", f"OpenAI account validated. Target model: {self.zelix_openai_model}")
                else:
                    return self._notify("warning", "OpenAI Error", f"HTTP {resp.status_code}: {resp.text[:200]}")

        except Exception as e:
            return self._notify("danger", "Connection Failed", str(e))

    def _notify(self, ntype, title, message):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": ntype,
                "sticky": False,
            },
        }
