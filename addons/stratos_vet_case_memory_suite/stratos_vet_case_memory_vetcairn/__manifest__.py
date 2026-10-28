{
    "name": "Vet Clinical Suggestions – VetCairn Bridge",
    "version": "19.0.1.0.0",
    "category": "Services/Veterinary",
    "summary": "Maps VetCairn roles to Clinical Suggestions roles and places the "
               "suggestions under the VetCairn Clinical menu.",
    "description": """
Installs automatically when VetCairn's exam connector (stratos_vet_exam_vetcairn) and the
Clinical Suggestions SOAP connector are both installed.

* VetCairn Technician gets Nurse / Reception rights, Veterinarian gets Veterinarian, Manager gets Senior Vet.
* Clinical Cases and Approval Queue appear under VetCairn > Clinical.
* The clinical-case button sits in the same button bar as the Encounter button on the exam.
* The VetCairn patient species is used to choose the species for matching.
""",
    "author": "Stratos Hub",
    "website": "https://www.stratos-hub.com",
    "license": "LGPL-3",
    "depends": ["stratos_vet_case_memory_soap", "stratos_vet_exam_vetcairn"],
    "data": [
        "security/groups.xml",
        "views/views.xml",
    ],
    "auto_install": True,
    "installable": True,
}
