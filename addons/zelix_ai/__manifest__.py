# -*- coding: utf-8 -*-
{
    "name": "Zelix AI Copilot",
    "version": "19.0.1.0.0",
    "category": "Veterinary/AI",
    "summary": "AI Clinical Copilot for VetCairn powered by Microsoft BitNet 1-Bit SLM",
    "description": """
Zelix AI Clinical Copilot for Odoo 19 & VetCairn:
=================================================
* Role-aware Clinical Copilot sidebar in OWL 2
* Active record auto-detection (Patients, Appointments, Encounters)
* Evidence-grounded Pre-Consultation Briefing (W02)
* Ambient Consultation Scribe & Structured SOAP Note Generator (W04)
* Prescription Assistant with clinical safety checks (W09)
* Action Card approval dialogs and verified persistence write-back
* Seamless integration with Microsoft BitNet 1-Bit SLM runtime
    """,
    "author": "Zelix AI / VetCairn Team",
    "website": "https://ai.alamiaconnect.com",
    "license": "LGPL-3",
    "depends": [
        "base",
        "web",
        "vet_base",
        "vet_clinical",
        "vet_appointment",
        "vet_prescription",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/zelix_audit_views.xml",
        "views/zelix_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "zelix_ai/static/src/services/zelix_copilot_service.js",
            "zelix_ai/static/src/components/action_card/action_card.js",
            "zelix_ai/static/src/components/action_card/action_card.xml",
            "zelix_ai/static/src/components/copilot_sidebar/copilot_sidebar.js",
            "zelix_ai/static/src/components/copilot_sidebar/copilot_sidebar.xml",
            "zelix_ai/static/src/components/copilot_sidebar/copilot_sidebar.scss",
            "zelix_ai/static/src/systray/copilot_systray.js",
            "zelix_ai/static/src/systray/copilot_systray.xml",
            "zelix_ai/static/src/systray/copilot_systray.scss",
        ],
    },
    "application": True,
    "installable": True,
    "auto_install": False,
}
