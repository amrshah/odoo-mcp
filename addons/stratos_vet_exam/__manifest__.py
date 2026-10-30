{
    "name": "Veterinary Exam Templates (SOAP)",
    "version": "19.0.1.0.0",
    "category": "Healthcare",
    "summary": "Build SOAP exam templates from a master structure, fill exams, print findings",
    "description": """
Veterinary Exam Template Builder
================================
* Master structure: main headings, nested sub-headings and fields
  (notes / value + unit / status choice / value + status), with default notes.
* Ships with the standard SOAP list (Subjective, Objective, Assessment, Plan,
  Diagnostics, Holistic, Client Communication).
* Templates: pick whole headings or single fields, per-template default notes.
* Exams: load a template, record findings, print a clean PDF that skips blanks.
""",
    "author": "Stratos Hub",
    "website": "https://www.stratos-hub.com",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence.xml",
        "views/vet_exam_node_views.xml",
        "wizard/template_add_fields_views.xml",
        "views/vet_exam_template_views.xml",
        "views/vet_exam_views.xml",
        "report/vet_exam_report.xml",
        "views/menus.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
}
