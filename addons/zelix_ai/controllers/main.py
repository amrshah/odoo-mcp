# -*- coding: utf-8 -*-
import json
import logging
import urllib.request
import urllib.error
from odoo import http
from odoo.http import request

logger = logging.getLogger(__name__)


class ZelixCopilotController(http.Controller):

    def _get_backend_url(self):
        return request.env["ir.config_parameter"].sudo().get_param("zelix_ai.backend_url", "http://zelix_copilot:8010").rstrip("/")

    @http.route("/zelix_ai/session_info", type="jsonrpc", auth="user", methods=["POST"], csrf=False)
    def session_info(self):
        """Returns dynamic role, clinical capabilities, and quick actions for the current user."""
        user = request.env.user
        
        if user.has_group("base.group_system") or user.has_group("vet_base.group_vet_manager"):
            role = "practice_manager"
            role_title = "Practice Administrator"
            greeting = f"Hello {user.name}! I am your Zelix AI Practice Copilot. How can I assist with clinic operations, case summaries, or appointments today?"
            quick_actions = [
                {"label": "Clinic Activity", "icon": "fa-line-chart", "prompt": "Give me an operational summary of today's appointments and clinic activity."},
                {"label": "Patient Census", "icon": "fa-users", "prompt": "How many patients are registered in the clinic?"},
                {"label": "Medicine Stock", "icon": "fa-medkit", "prompt": "Check available medication inventory and pharmacy stock."},
                {"label": "Case Summary", "icon": "fa-file-text-o", "prompt": "Summarize patient history and past encounters."},
            ]
        elif user.has_group("vet_base.group_vet_technician"):
            role = "technician"
            role_title = "Veterinary Technician"
            greeting = f"Hello {user.name}! I am your Zelix AI Tech Copilot. How can I help you with vital recording, patient care tasks, or medication administration?"
            quick_actions = [
                {"label": "Record Vitals", "icon": "fa-heartbeat", "prompt": "Record vitals for active patient: Temperature 101.5 F, HR 110, RR 24, Weight 14.5 kg."},
                {"label": "Medication Admin", "icon": "fa-flask", "prompt": "Log medication administration for today's treatment plan."},
                {"label": "Case Summary", "icon": "fa-file-text-o", "prompt": "Summarize patient history and past encounters."},
                {"label": "Pre-Consult Brief", "icon": "fa-user-md", "prompt": "Prepare me for my next patient. What should I focus on?"},
            ]
        elif user.has_group("vet_base.group_vet_receptionist"):
            role = "receptionist"
            role_title = "Front Desk Receptionist"
            greeting = f"Hello {user.name}! I am your Zelix AI Front-Desk Copilot. How can I assist you with appointment bookings or client communications?"
            quick_actions = [
                {"label": "Book Appointment", "icon": "fa-calendar-plus-o", "prompt": "Book a follow-up appointment for next week."},
                {"label": "Check Reminders", "icon": "fa-bell-o", "prompt": "Check due vaccination reminders for today."},
                {"label": "Client Message", "icon": "fa-comment-o", "prompt": "Draft WhatsApp reminder message for the owner."},
                {"label": "Patient Summary", "icon": "fa-id-card-o", "prompt": "Summarize patient history and owner contact details."},
            ]
        else:
            role = "veterinarian"
            role_title = "Doctor / Veterinarian"
            greeting = f"Hello Dr. {user.name}! I am your Zelix AI Clinical Copilot, powered by local BitNet SLM. How can I assist you with today's consultations?"
            quick_actions = [
                {"label": "Pre-Consult Brief", "icon": "fa-user-md", "prompt": "Prepare me for my next patient Max. What should I focus on?"},
                {"label": "Generate SOAP", "icon": "fa-stethoscope", "prompt": "Generate today SOAP note from physical exam and consultation history."},
                {"label": "Prescribe Rx", "icon": "fa-medkit", "prompt": "Prescribe Amoxicillin-Clavulanate 250mg 1 tab BID for 7 days."},
                {"label": "Case Summary", "icon": "fa-file-text-o", "prompt": "Summarize patient history and past encounters."},
            ]

        return {
            "user_id": user.id,
            "name": user.name,
            "role": role,
            "role_title": role_title,
            "greeting": greeting,
            "quick_actions": quick_actions,
        }

    @http.route("/zelix_ai/chat", type="jsonrpc", auth="user", methods=["POST"], csrf=False)
    def chat(self, message, context=None):
        """Processes clinical Copilot chat request and persists audit record."""
        backend_url = self._get_backend_url()
        user = request.env.user
        ctx = context or {}

        # Resolve clinical role
        role = "veterinarian"
        if user.has_group("vet_base.group_vet_manager"):
            role = "practice_manager"
        elif user.has_group("vet_base.group_vet_technician"):
            role = "technician"
        elif user.has_group("vet_base.group_vet_receptionist"):
            role = "receptionist"

        ctx["user_uid"] = user.id
        ctx["user_name"] = user.name
        ctx["role"] = role

        payload = {
            "message": message,
            "context": ctx,
            "role": role,
        }

        # Request to Copilot backend service
        backend_urls = [backend_url, "http://127.0.0.1:8010", "http://localhost:8010", "http://zelix_copilot:8010"]
        response_data = None
        last_error = None

        for url in list(dict.fromkeys(backend_urls)):
            try:
                req = urllib.request.Request(
                    f"{url}/api/copilot/chat",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    if resp.status == 200:
                        response_data = json.loads(resp.read().decode("utf-8"))
                        break
            except Exception as e:
                last_error = e
                continue

        if not response_data:
            logger.error(f"Failed to communicate with Zelix Copilot backend: {last_error}")
            return {
                "error": True,
                "message": f"Zelix Copilot backend is unreachable. Please verify the service is running on port 8010 ({last_error}).",
            }

        # Create audit record in Odoo
        try:
            patient_id = ctx.get("patient_id")
            if not patient_id and ctx.get("model") == "vet.patient" and ctx.get("record_id"):
                patient_id = ctx.get("record_id")

            request.env["zelix.copilot.audit"].sudo().create({
                "request_id": response_data.get("request_id", "req_unknown"),
                "user_id": user.id,
                "role": role,
                "workflow_id": response_data.get("workflow_id", "unknown"),
                "model_used": response_data.get("model_used", "BitNet-b1.58-2B"),
                "patient_id": patient_id if patient_id else False,
                "prompt_text": message,
                "response_text": response_data.get("response", ""),
                "action_cards_count": len(response_data.get("action_cards", [])),
                "execution_status": "proposed" if response_data.get("action_cards") else "approved",
            })
        except Exception as audit_err:
            logger.warning(f"Failed to create audit log: {audit_err}")

        return response_data

    @http.route("/zelix_ai/action/approve", type="jsonrpc", auth="user", methods=["POST"], csrf=False)
    def approve_action(self, action_id):
        """Executes human approval for an ActionCard proposal."""
        backend_url = self._get_backend_url()
        payload = {"action_id": action_id}

        backend_urls = [backend_url, "http://127.0.0.1:8010", "http://localhost:8010", "http://zelix_copilot:8010"]
        response_data = None
        last_error = None

        for url in list(dict.fromkeys(backend_urls)):
            try:
                req = urllib.request.Request(
                    f"{url}/api/copilot/action/approve",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    if resp.status == 200:
                        response_data = json.loads(resp.read().decode("utf-8"))
                        break
            except Exception as e:
                last_error = e
                continue

        if not response_data:
            return {"success": False, "error": f"Failed to execute approval: {last_error}"}

        return response_data

    @http.route("/zelix_ai/action/reject", type="jsonrpc", auth="user", methods=["POST"], csrf=False)
    def reject_action(self, action_id, reason="User rejected proposal."):
        """Rejects an ActionCard proposal."""
        backend_url = self._get_backend_url()
        payload = {"action_id": action_id, "reason": reason}

        backend_urls = [backend_url, "http://127.0.0.1:8010", "http://localhost:8010", "http://zelix_copilot:8010"]
        response_data = None

        for url in list(dict.fromkeys(backend_urls)):
            try:
                req = urllib.request.Request(
                    f"{url}/api/copilot/action/reject",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    if resp.status == 200:
                        response_data = json.loads(resp.read().decode("utf-8"))
                        break
            except Exception:
                continue

        return response_data or {"success": True, "action_id": action_id, "status": "rejected"}
