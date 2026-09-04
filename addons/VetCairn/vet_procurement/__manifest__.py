{
    "name": "VetCairn Procurement",
    "summary": "Veterinary suppliers, purchase review, receipts, and replenishment",
    "version": "19.0.1.0.0",
    "category": "Services/Veterinary",
    "author": "VetCairn",
    "license": "LGPL-3",
    "depends": ["vet_commercial", "purchase_stock"],
    "data": [
        "security/vet_procurement_security.xml",
        "views/purchase_order_views.xml",
        "views/stock_picking_views.xml",
        "views/vet_clinic_views.xml",
        "views/vet_procurement_menus.xml",
    ],
    "application": False,
    "installable": True,
}
