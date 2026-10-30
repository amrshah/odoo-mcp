from odoo import api, fields, models
from odoo.exceptions import ValidationError

SPECIES = [
    ("general", "General"),
    ("canine", "Canine"),
    ("feline", "Feline"),
    ("equine", "Equine"),
    ("exotic", "Exotic"),
]


class VetExamTemplate(models.Model):
    _name = "vet.exam.template"
    _description = "Exam Template"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    species = fields.Selection(SPECIES, default="general", required=True, tracking=True)
    active = fields.Boolean(default=True)
    description = fields.Text()
    line_ids = fields.One2many("vet.exam.template.line", "template_id", "Fields", copy=True)
    field_count = fields.Integer("Field Count", compute="_compute_counts")
    section_count = fields.Integer("Sections", compute="_compute_counts")
    default_note_count = fields.Integer("Default Notes", compute="_compute_counts")
    exam_count = fields.Integer("Exams", compute="_compute_exam_count")

    @api.depends("line_ids.node_id", "line_ids.default_note")
    def _compute_counts(self):
        for tpl in self:
            tpl.field_count = len(tpl.line_ids)
            tpl.section_count = len(tpl.line_ids.node_id.section_id)
            tpl.default_note_count = len(tpl.line_ids.filtered("default_note"))

    def _compute_exam_count(self):
        data = self.env["vet.exam"]._read_group(
            [("template_id", "in", self.ids)], ["template_id"], ["__count"])
        counts = {tpl.id: c for tpl, c in data}
        for tpl in self:
            tpl.exam_count = counts.get(tpl.id, 0)

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        for tpl, vals in zip(self, vals_list):
            if "name" not in (default or {}):
                vals["name"] = self.env._("%s (copy)", tpl.name)
        return vals_list

    def _resequence_lines(self):
        order = {node.id: i for i, node in enumerate(self.env["vet.exam.node"]._get_ordered_fields())}
        for tpl in self:
            for line in tpl.line_ids:
                line.sequence = order.get(line.node_id.id, 100000 + line.id)

    def action_resequence(self):
        self._resequence_lines()
        return True

    def action_view_exams(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Exams"),
            "res_model": "vet.exam",
            "view_mode": "list,form",
            "domain": [("template_id", "=", self.id)],
            "context": {"default_template_id": self.id},
        }


class VetExamTemplateLine(models.Model):
    _name = "vet.exam.template.line"
    _description = "Exam Template Field"
    _order = "sequence, id"

    template_id = fields.Many2one("vet.exam.template", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    node_id = fields.Many2one(
        "vet.exam.node", "Field", required=True, ondelete="restrict",
        domain="[('node_type', '=', 'field')]",
    )
    section_id = fields.Many2one(related="node_id.section_id", string="Main Heading")
    group_path = fields.Char(related="node_id.group_path", string="Sub-heading")
    type_label = fields.Char(related="node_id.type_label", string="Setup")
    default_note = fields.Text(
        help="Pre-fills this field's notes when an exam is started from this template. "
             "Leave empty to use the field's own default note from the structure.",
    )

    @api.constrains("template_id", "node_id")
    def _check_unique_field(self):
        for line in self:
            dup = line.template_id.line_ids.filtered(
                lambda l: l.node_id == line.node_id and l != line)
            if dup:
                raise ValidationError(self.env._(
                    "'%s' is already in this template.", line.node_id.complete_name))

    @api.onchange("node_id")
    def _onchange_node_id(self):
        if self.node_id and not self.default_note:
            self.default_note = self.node_id.default_note
