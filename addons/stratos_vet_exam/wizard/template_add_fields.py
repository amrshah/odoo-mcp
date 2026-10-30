from odoo import fields, models


class VetExamTemplateAddFields(models.TransientModel):
    _name = "vet.exam.template.add.fields"
    _description = "Add Fields to Exam Template"

    template_id = fields.Many2one("vet.exam.template", required=True)
    node_ids = fields.Many2many(
        "vet.exam.node", string="Headings / Fields",
        help="Pick a whole heading (e.g. Objective / Oral) to add every field under it, "
             "or pick single fields.",
    )

    def action_add(self):
        self.ensure_one()
        Node = self.env["vet.exam.node"]
        tpl = self.template_id
        picked = Node.search([("id", "child_of", self.node_ids.ids), ("node_type", "=", "field")])
        existing = tpl.line_ids.node_id
        new_lines = []
        for node in Node._get_ordered_fields():
            if node in picked and node not in existing:
                new_lines.append({"template_id": tpl.id, "node_id": node.id,
                                  "default_note": node.default_note or False})
        self.env["vet.exam.template.line"].create(new_lines)
        tpl._resequence_lines()
        return {"type": "ir.actions.act_window_close"}
