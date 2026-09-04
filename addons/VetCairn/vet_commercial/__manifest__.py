{
    "name": "VetCairn Commercial",
    "summary": "Veterinary estimates, discounts, approvals, and commercial context",
    "version": "19.0.1.0.0",
    "category": "Services/Veterinary",
    "author": "VetCairn",
    "license": "LGPL-3",
    "depends": ["vet_treatment", "sale_management", "sale_stock", "vet_billing"],
    "data": [
        "security/vet_commercial_security.xml",
        "views/sale_order_views.xml",
        "views/account_move_views.xml",
        "views/vet_patient_views.xml",
        "views/vet_commercial_menus.xml",
    ],
    "application": False,
    "installable": True,
}
