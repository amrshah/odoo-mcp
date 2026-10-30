{
    "name": "Veterinary Exam Templates — VetCairn Connector",
    "version": "19.0.1.0.0",
    "category": "Healthcare",
    "summary": "Links structured exams to VetCairn patients and clinical encounters",
    "description": """
Connects Veterinary Exam Templates (stratos_vet_exam) to VetCairn:
* Exams belong to a VetCairn patient and (optionally) a clinical encounter.
* Start a structured exam from the encounter; vitals pre-fill from triage.
* Send findings into the encounter's S / O / A / P notes, and vitals back.
* Templates can be limited to species; patient and encounter show their exams.
* Access follows VetCairn roles; menus move under VetCairn.
""",
    "author": "Stratos Hub",
    "website": "https://www.stratos-hub.com",
    "license": "LGPL-3",
    "depends": ["stratos_vet_exam", "vet_clinical"],
    "data": [
        "security/ir.model.access.csv",
        "security/access_override.xml",
        "views/vet_exam_template_views.xml",
        "views/vet_exam_views.xml",
        "views/vet_encounter_views.xml",
        "views/vet_patient_views.xml",
        "views/menus.xml",
        "report/vet_exam_report.xml",
    ],
    "auto_install": True,
    "installable": True,
}
