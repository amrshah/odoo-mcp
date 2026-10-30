from markupsafe import Markup, escape

from odoo import Command, api, fields, models

from .vet_exam_node import FIELD_TYPES
from .vet_exam_template import SPECIES


class VetExam(models.Model):
    _name = "vet.exam"
    _description = "Veterinary Exam"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char("Reference", default="New", readonly=True, copy=False)
    patient_name = fields.Char("Patient / Case", required=True, tracking=True)
    owner_id = fields.Many2one("res.partner", "Owner / Client", tracking=True)
    species = fields.Selection(SPECIES, default="general")
    template_id = fields.Many2one("vet.exam.template", "Template", required=True, tracking=True,
                                  ondelete="restrict")
    date = fields.Datetime(default=fields.Datetime.now, required=True)
    vet_id = fields.Many2one("res.users", "Veterinarian", default=lambda self: self.env.user,
                             tracking=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    state = fields.Selection([("draft", "In Progress"), ("done", "Completed")],
                             default="draft", tracking=True)
    line_ids = fields.One2many("vet.exam.line", "exam_id", "Findings", copy=True)
    filled_count = fields.Integer("Filled", compute="_compute_filled")
    summary_html = fields.Html("Output Preview", compute="_compute_summary_html", sanitize=False)

    # ------------------------------------------------------------------
    @api.model
    def _prepare_line_commands(self, template):
        cmds = []
        for tl in template.line_ids.sorted(lambda l: (l.sequence, l.id)):
            node = tl.node_id
            cmds.append(Command.create({
                "node_id": node.id,
                "sequence": tl.sequence,
                "section_name": node.section_id.name,
                "group_path": node.group_path,
                "name": node.name,
                "field_type": node.field_type,
                "unit": node.unit,
                "include_note": node.include_note,
                "big_note": node.big_note,
                "note": tl.default_note or node.default_note or False,
            }))
        return cmds

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("vet.exam") or "New"
            if vals.get("template_id") and not vals.get("line_ids"):
                tpl = self.env["vet.exam.template"].browse(vals["template_id"])
                vals["line_ids"] = self._prepare_line_commands(tpl)
                vals.setdefault("species", tpl.species)
        return super().create(vals_list)

    @api.onchange("template_id")
    def _onchange_template_id(self):
        if self.state == "draft" and self.template_id:
            self.species = self.template_id.species
            self.line_ids = [Command.clear()] + self._prepare_line_commands(self.template_id)

    # ------------------------------------------------------------------
    @api.depends("line_ids.has_data")
    def _compute_filled(self):
        for exam in self:
            exam.filled_count = len(exam.line_ids.filtered("has_data"))

    def _get_report_sections(self):
        """[{'name': section, 'groups': [{'name': sub-heading, 'lines': recordset}]}],
        only lines that carry data, in template order."""
        self.ensure_one()
        sections = []
        for line in self.line_ids.sorted(lambda l: (l.sequence, l.id)).filtered("has_data"):
            if not sections or sections[-1]["name"] != line.section_name:
                sections.append({"name": line.section_name or "", "groups": []})
            groups = sections[-1]["groups"]
            if not groups or groups[-1]["name"] != (line.group_path or ""):
                groups.append({"name": line.group_path or "", "lines": self.env["vet.exam.line"]})
            groups[-1]["lines"] |= line
        return sections

    @api.depends("line_ids.value", "line_ids.status_id", "line_ids.note",
                 "line_ids.unit_option_id", "patient_name")
    def _compute_summary_html(self):
        for exam in self:
            sections = exam._get_report_sections()
            if not sections:
                exam.summary_html = Markup(
                    '<p class="text-muted">No findings entered yet. Blank fields are skipped.</p>')
                continue
            out = Markup("")
            for sec in sections:
                out += Markup('<h5 class="mt-3 mb-1 pb-1 border-bottom text-uppercase" '
                              'style="color:#0b5850">%s</h5>') % sec["name"]
                for grp in sec["groups"]:
                    if grp["name"]:
                        out += Markup('<div class="fw-bold mt-2" style="color:#b45309">%s</div>') % grp["name"]
                    for line in grp["lines"]:
                        out += Markup('<div class="d-flex py-1"><div style="min-width:240px">'
                                      '<em>%s</em></div><div>%s</div></div>') % (
                            line.name, line._get_result_html())
            exam.summary_html = out

    # ------------------------------------------------------------------
    def action_done(self):
        self.write({"state": "done"})

    def action_draft(self):
        self.write({"state": "draft"})

    def action_reload_template(self):
        for exam in self.filtered(lambda e: e.state == "draft" and e.template_id):
            exam.line_ids.unlink()
            exam.write({"line_ids": exam._prepare_line_commands(exam.template_id)})

    def action_print(self):
        return self.env.ref("stratos_vet_exam.action_report_vet_exam").report_action(self)


class VetExamLine(models.Model):
    _name = "vet.exam.line"
    _description = "Exam Finding"
    _order = "sequence, id"

    exam_id = fields.Many2one("vet.exam", required=True, ondelete="cascade", index=True)
    state = fields.Selection(related="exam_id.state")
    sequence = fields.Integer(default=10)
    node_id = fields.Many2one("vet.exam.node", "Structure Field", ondelete="set null")
    # snapshot of the structure at exam time, so history survives later edits
    section_name = fields.Char("Main Heading")
    group_path = fields.Char("Sub-heading")
    name = fields.Char("Field", required=True)
    field_type = fields.Selection(FIELD_TYPES, default="note")
    unit = fields.Char()
    include_note = fields.Boolean(default=True)
    big_note = fields.Boolean()

    value = fields.Char()
    unit_option_id = fields.Many2one(
        "vet.exam.option", "Unit Choice",
        domain="[('node_id', '=', node_id), ('kind', '=', 'unit')]")
    status_id = fields.Many2one(
        "vet.exam.option", "Status",
        domain="[('node_id', '=', node_id), ('kind', '=', 'status')]")
    note = fields.Text("Notes")

    has_value = fields.Boolean(compute="_compute_flags")
    has_status = fields.Boolean(compute="_compute_flags")
    has_unit_choice = fields.Boolean(compute="_compute_flags")
    value_text = fields.Char("Result Value", compute="_compute_value_text")
    has_data = fields.Boolean(compute="_compute_has_data", store=True)

    @api.depends("field_type", "node_id.unit_option_ids")
    def _compute_flags(self):
        for line in self:
            line.has_value = line.field_type in ("value", "value_status")
            line.has_status = line.field_type in ("status", "value_status")
            line.has_unit_choice = line.has_value and bool(line.node_id.unit_option_ids)

    @api.depends("value", "unit", "unit_option_id")
    def _compute_value_text(self):
        for line in self:
            if line.value:
                unit = line.unit_option_id.name or line.unit or ""
                line.value_text = f"{line.value} {unit}".strip()
            else:
                line.value_text = False

    @api.depends("value", "status_id", "note")
    def _compute_has_data(self):
        for line in self:
            line.has_data = bool((line.value or "").strip() or line.status_id
                                 or (line.note or "").strip())

    def _get_result_html(self):
        self.ensure_one()
        parts = []
        if self.status_id:
            parts.append(Markup("<b>%s</b>") % self.status_id.name)
        if self.value_text:
            parts.append(escape(self.value_text))
        if self.note:
            parts.append(Markup('<span style="white-space:pre-wrap">%s</span>') % self.note)
        return Markup(" — ").join(parts)
