{
    "name": "Vet Clinical Suggestions – SOAP Exam Connector",
    "version": "19.0.1.0.0",
    "category": "Services/Veterinary",
    "summary": "Runs clinical suggestions and voice dictation inside the SOAP exam "
               "(stratos_vet_exam); approved plan flows back into the exam.",
    "description": """
Connects Vet Clinical Suggestions to Veterinary Exam Templates (SOAP):
* S – Subjective history lines and dictation become the symptoms used for matching.
* O – Vital Signs (temperature °C/°F, weight Kg/lb, heart rate, respiration) feed similarity and mg/kg dosing.
* A – Suggested diagnoses are approved / modified / rejected by the vet and written into Assessment / Diagnoses.
* P – Approved tests and treatment are written into Plan / Notes.
* Mark Completed on the exam finalises the clinical case, which then feeds the knowledge base.
* Voice dictation button on the exam; every recording stays in the case history.
Works with stratos_vet_exam alone and with the VetCairn connector
(stratos_vet_exam_vetcairn): the VetCairn patient species is used when present.
""",
    "author": "Stratos Hub",
    "website": "https://www.stratos-hub.com",
    "license": "LGPL-3",
    "depends": ["stratos_vet_case_memory", "stratos_vet_exam"],
    "data": [
        "views/vet_exam_views.xml",
        "views/vet_cm_case_views.xml",
    ],
    "auto_install": True,
    "installable": True,
}
