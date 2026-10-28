{
    "name": "Vet Clinical Suggestions (Case Memory)",
    "version": "19.0.1.0.0",
    "category": "Services/Veterinary",
    "summary": "Self-learning clinical suggestions for veterinary hospitals: "
               "similar past cases suggest diagnosis, tests and treatment; "
               "the vet approves, modifies or rejects. Voice capture included.",
    "description": """
Vet Clinical Suggestions (Case Memory)
======================================
* The system suggests, the veterinarian decides. Nothing becomes an order without a vet's approval.
* Learns only from FINALISED cases and their OUTCOMES (resolved, improved, not improved, died) plus every approve / modify / reject decision.
* Species is a hard filter; breed, age, weight and vitals refine matching.
* Weight-based (mg/kg) dosing, species-toxic drug block list, breed cautions, pregnancy cautions, withdrawal periods for food-producing animals and zoonotic alerts.
* Voice recognition (browser speech, English / Urdu): every recording is kept in the case history; symptoms and vitals are proposed from speech and applied only when the vet confirms.
* Optional AI layer (Anthropic / OpenAI) to structure dictation into SOAP and explain suggestions. Works fully without AI.
""",
    "author": "Stratos Hub",
    "website": "https://www.stratos-hub.com",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "data/config_data.xml",
        "data/master_data.xml",
        "wizard/reject_wizard_views.xml",
        "views/master_views.xml",
        "views/case_views.xml",
        "views/suggestion_views.xml",
        "views/pattern_views.xml",
        "views/voice_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
        "report/case_report.xml",
    ],
    "demo": [
        "demo/demo.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "stratos_vet_case_memory/static/src/voice/*",
        ],
    },
    "application": True,
    "installable": True,
}
