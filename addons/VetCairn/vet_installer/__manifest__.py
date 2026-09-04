{
    "name": "VetCairn Complete Suite Installer",
    "summary": "Install the complete VetCairn veterinary practice suite in one step",
    "description": """
VetCairn Complete Suite Installer
=================================
Install this single application to install every supported internal VetCairn
module and its standard Odoo dependencies in the correct dependency order.

External provider integrations are intentionally not included.
    """,
    "version": "19.0.1.0.0",
    "category": "Services/Veterinary",
    "author": "VetCairn",
    "license": "LGPL-3",
    "depends": [
        "vet_base",
        "vet_appointment",
        "vet_clinical",
        "vet_vaccination",
        "vet_diagnostic",
        "vet_prescription",
        "vet_inventory",
        "vet_billing",
        "vet_documents",
        "vet_reminder",
        "vet_reporting",
        "vet_treatment",
        "vet_commercial",
        "vet_procurement",
        "vet_dashboard",
        "vet_task",
        "vet_communication",
        "vet_settings",
        "vet_completion",
    ],
    "data": [],
    "application": True,
    "installable": True,
    "auto_install": False,
}
