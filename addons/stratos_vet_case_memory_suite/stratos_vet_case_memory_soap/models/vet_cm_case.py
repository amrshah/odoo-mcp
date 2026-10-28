from odoo import _, api, fields, models


class VetCmCase(models.Model):
    _inherit = "vet.cm.case"

    exam_ids = fields.One2many("vet.exam", "cm_case_id", string="SOAP exams")
    exam_count = fields.Integer(compute="_compute_exam_count")

    def _compute_exam_count(self):
        for case in self:
            case.exam_count = len(case.exam_ids)

    @api.model_create_multi
    def create(self, vals_list):
        cases = super().create(vals_list)
        exam_id = self.env.context.get("vet_cm_link_exam_id")
        if exam_id and len(cases) == 1:
            exam = self.env["vet.exam"].browse(exam_id).exists()
            if exam and not exam.cm_case_id:
                exam.cm_case_id = cases
                cases._sync_from_exam(exam)
        return cases

    def _sync_from_exam(self, exam):
        """Pull S / O data from the SOAP exam (symptoms are only ever added)."""
        for case in self.filtered(lambda c: c.state == "draft"):
            vals = exam._cm_case_vals(species=case.species_id)
            vals.pop("species_id", None)
            vals.pop("animal_name", None)
            symptoms = vals.pop("symptom_ids", [])
            vals["symptom_ids"] = [(4, sid) for sid in symptoms]
            case.write(vals)

    def action_open_exam(self):
        self.ensure_one()
        action = {"type": "ir.actions.act_window", "name": _("SOAP exam"),
                  "res_model": "vet.exam"}
        if len(self.exam_ids) == 1:
            action.update(view_mode="form", res_id=self.exam_ids.id, views=[(False, "form")])
        else:
            action.update(view_mode="list,form", domain=[("cm_case_id", "=", self.id)])
        return action
