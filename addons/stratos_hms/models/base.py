from odoo import api, fields, models


class HmsDepartment(models.Model):
    _name = "hms.department"
    _description = "Hospital Department"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    kind = fields.Selection(
        [("clinical", "Clinical"), ("diagnostic", "Diagnostic"), ("support", "Support")],
        default="clinical",
        required=True,
    )
    head_id = fields.Many2one("hms.practitioner", string="Head of Department")
    consult_product_id = fields.Many2one(
        "product.product", string="Consultation Fee Product",
        help="Product used to bill an OPD consultation in this department.",
    )
    consult_fee = fields.Float(string="Default Consultation Fee", default=1000.0)
    specialty_pack = fields.Text(
        string="Specialty Pack",
        help="Department-specific guidance the AI uses when drafting consults (protocols, "
             "common presentations, preferred first-line therapies).",
    )
    practitioner_ids = fields.One2many("hms.practitioner", "department_id", string="Practitioners")
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint("unique(code)", "Department code must be unique.")


class HmsPractitioner(models.Model):
    """A clinical or support staff member. One record per person, linked to a login.

    The `role` drives which workspace a person lands on; the security groups on
    the linked user drive what they can actually do.
    """
    _name = "hms.practitioner"
    _description = "Hospital Staff / Practitioner"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    user_id = fields.Many2one("res.users", string="Login", tracking=True, ondelete="set null")
    role = fields.Selection(
        [
            ("receptionist", "Receptionist / Front Desk"),
            ("nurse", "Nurse"),
            ("doctor", "Doctor"),
            ("pharmacist", "Pharmacist"),
            ("lab", "Lab Technologist"),
            ("radiology", "Radiology"),
            ("blood_bank", "Blood Bank"),
            ("ot", "Operation Theatre"),
            ("hod", "Head of Department"),
            ("director", "Director / Management"),
        ],
        required=True,
        default="doctor",
        tracking=True,
    )
    department_id = fields.Many2one("hms.department", string="Department")
    specialty = fields.Char()
    qualification = fields.Char()
    pmdc_no = fields.Char(string="PMDC Reg. No.", help="Pakistan Medical & Dental Council registration.")
    phone = fields.Char()
    email = fields.Char()
    consult_fee = fields.Float(string="Consultation Fee")
    image_128 = fields.Image(max_width=128, max_height=128)
    active = fields.Boolean(default=True)
    is_doctor = fields.Boolean(compute="_compute_is_doctor", store=True)

    @api.depends("role")
    def _compute_is_doctor(self):
        for rec in self:
            rec.is_doctor = rec.role in ("doctor", "hod")

    @api.model
    def get_current(self):
        """Practitioner record of the logged-in user (or empty recordset)."""
        return self.search([("user_id", "=", self.env.uid)], limit=1)

    def _compute_display_name(self):
        for rec in self:
            prefix = "Dr. " if rec.is_doctor and not rec.name.lower().startswith("dr") else ""
            rec.display_name = f"{prefix}{rec.name}"


class HmsAllergy(models.Model):
    _name = "hms.allergy"
    _description = "Allergy / Allergen"
    _order = "name"

    name = fields.Char(required=True)
    allergen_class = fields.Char(
        string="Allergen Class",
        help="Matches hms.drug.allergen_class to block dispensing (e.g. 'penicillin', 'sulfa', 'nsaid').",
    )
    severity = fields.Selection([("mild", "Mild"), ("moderate", "Moderate"), ("severe", "Severe")], default="moderate")


class HmsIcd10(models.Model):
    _name = "hms.icd10"
    _description = "ICD-10 Code"
    _order = "code"
    _rec_names_search = ["code", "name"]

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True)
    chapter = fields.Char()

    _code_uniq = models.Constraint("unique(code)", "ICD-10 code must be unique.")

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.code} — {rec.name}"
