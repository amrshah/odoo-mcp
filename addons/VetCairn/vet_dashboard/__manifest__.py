{
    "name": "VetCairn Dashboard",
    "summary": "Role-aware veterinary operational dashboards and urgent work queues",
    "version": "19.0.1.0.0",
    "category": "Services/Veterinary",
    "author": "VetCairn",
    "license": "LGPL-3",
    "depends": ["vet_procurement", "vet_reporting", "web"],
    "data": [
        "security/ir.model.access.csv",
        "data/vet_dashboard_action.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "vet_dashboard/static/src/js/vet_dashboard.js",
            "vet_dashboard/static/src/xml/vet_dashboard.xml",
            "vet_dashboard/static/src/scss/vet_dashboard.scss",
        ],
    },
    "application": False,
    "installable": True,
}
