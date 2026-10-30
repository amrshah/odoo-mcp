from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError

from .standard_structure import STANDARD

UNIT_LIKE = {"kg", "lb", "g", "mg", "c", "f"}
FIELD_TYPES = [
    ("note", "Notes only"),
    ("value", "Value + unit"),
    ("status", "Status choice"),
    ("value_status", "Value + status"),
]


class VetExamNode(models.Model):
    """Master structure: headings (any depth) and the fields under them."""

    _name = "vet.exam.node"
    _description = "Exam Structure Item"
    _parent_store = True
    _parent_name = "parent_id"
    _order = "sequence, id"
    _rec_name = "complete_name"

    name = fields.Char(required=True)
    complete_name = fields.Char(
        "Full Path", compute="_compute_complete_name", recursive=True, store=True
    )
    node_type = fields.Selection(
        [("heading", "Heading"), ("field", "Field")],
        string="Item Type", default="heading", required=True,
    )
    parent_id = fields.Many2one(
        "vet.exam.node", "Parent Heading", index=True, ondelete="cascade",
        domain="[('node_type', '=', 'heading')]",
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("vet.exam.node", "parent_id", "Sub-items")
    section_id = fields.Many2one(
        "vet.exam.node", "Main Heading", compute="_compute_section_id",
        recursive=True, store=True, index=True,
    )
    group_path = fields.Char(
        "Sub-heading", compute="_compute_group_path", recursive=True, store=True,
        help="Sub-headings between the main heading and this field.",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # ---- field setup ----
    field_type = fields.Selection(FIELD_TYPES, "Records", default="note")
    unit = fields.Char(help="Fixed unit shown after the value, e.g. mg/dL, bpm, mmHg.")
    option_ids = fields.One2many("vet.exam.option", "node_id", "All Options")
    unit_option_ids = fields.One2many(
        "vet.exam.option", "node_id", "Unit Choices",
        domain=[("kind", "=", "unit")], context={"default_kind": "unit"},
        help="Optional: let the doctor pick the unit (e.g. Kg / lb). Overrides the fixed unit.",
    )
    status_option_ids = fields.One2many(
        "vet.exam.option", "node_id", "Status Options",
        domain=[("kind", "=", "status")], context={"default_kind": "status"},
    )
    include_note = fields.Boolean("Include Notes Box", default=True)
    big_note = fields.Boolean("Large Notes Box")
    default_note = fields.Text(
        help="Standard wording that pre-fills this field's notes in every template "
             "that uses it. The doctor can edit it during the exam.",
    )
    type_label = fields.Char("Setup", compute="_compute_type_label")
    field_count = fields.Integer("Fields", compute="_compute_field_count")

    # ------------------------------------------------------------------
    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for node in self:
            if node.parent_id:
                node.complete_name = f"{node.parent_id.complete_name} / {node.name}"
            else:
                node.complete_name = node.name

    @api.depends("parent_id.section_id")
    def _compute_section_id(self):
        for node in self:
            node.section_id = node.parent_id.section_id if node.parent_id else node

    @api.depends("parent_id.complete_name", "node_type", "complete_name")
    def _compute_group_path(self):
        for node in self:
            base = node.parent_id.complete_name if node.node_type == "field" else node.complete_name
            parts = (base or "").split(" / ")[1:]
            node.group_path = " · ".join(parts)

    @api.depends("field_type", "unit", "unit_option_ids.name", "status_option_ids.name",
                 "include_note", "node_type")
    def _compute_type_label(self):
        for node in self:
            if node.node_type != "field":
                node.type_label = False
                continue
            bits = []
            if node.field_type in ("value", "value_status"):
                if node.unit_option_ids:
                    bits.append("value · " + "/".join(node.unit_option_ids.mapped("name")))
                else:
                    bits.append(("value " + node.unit) if node.unit else "value")
            if node.field_type in ("status", "value_status"):
                bits.append("choice: " + " / ".join(node.status_option_ids.mapped("name")))
            if node.include_note:
                bits.append("+notes" if bits else "notes")
            node.type_label = "  ·  ".join(bits) or "notes"

    def _compute_field_count(self):
        for node in self:
            if node.node_type == "field" or not node.id:
                node.field_count = 0
            else:
                node.field_count = self.search_count(
                    [("id", "child_of", node.id), ("node_type", "=", "field")]
                )

    # ------------------------------------------------------------------
    @api.constrains("node_type", "parent_id", "child_ids", "field_type", "status_option_ids")
    def _check_structure(self):
        for node in self:
            if node.node_type == "field":
                if not node.parent_id:
                    raise ValidationError(
                        self.env._("Field '%s' must sit under a heading.", node.name))
                if node.child_ids:
                    raise ValidationError(
                        self.env._("Field '%s' cannot have sub-items.", node.name))
                if node.field_type in ("status", "value_status") and not node.status_option_ids:
                    raise ValidationError(
                        self.env._("Field '%s' needs at least one status option.", node.name))
            if node.parent_id and node.parent_id.node_type == "field":
                raise ValidationError(self.env._("Items can only be placed under a heading."))
        if self._has_cycle():
            raise ValidationError(self.env._("You cannot create a recursive structure."))

    # ------------------------------------------------------------------
    def _iter_fields(self):
        """Fields under these nodes, in display (tree) order."""
        result = self.browse()
        for node in self.sorted(lambda n: (n.sequence, n.id)):
            if node.node_type == "field":
                result |= node
            else:
                result |= node.child_ids._iter_fields()
        return result

    @api.model
    def _get_ordered_fields(self):
        return self.search([("parent_id", "=", False)])._iter_fields()

    # ------------------------------------------------------------------
    # Standard list
    # ------------------------------------------------------------------
    @api.model
    def _seed_field_vals(self, spec):
        if isinstance(spec, str):
            name, opts, unit = spec, None, None
        else:
            name, opts, unit = spec["n"], spec.get("o"), spec.get("u")
        vals = {
            "name": name,
            "node_type": "field",
            "include_note": True,
            "big_note": name in ("Notes", "Diagnoses"),
            "field_type": "note",
        }
        option_cmds = []
        unit_like = bool(opts) and all(o.lower() in UNIT_LIKE for o in opts)
        if unit_like:
            vals["field_type"] = "value"
            for i, o in enumerate(opts):
                label = f"°{o}" if unit == "°" else o
                option_cmds.append(Command.create({"name": label, "kind": "unit", "sequence": i}))
        else:
            has_value = bool(unit) and unit != "°"
            if has_value:
                vals["unit"] = unit
            if opts:
                for i, o in enumerate(opts):
                    option_cmds.append(Command.create({"name": o, "kind": "status", "sequence": i}))
            if has_value and opts:
                vals["field_type"] = "value_status"
            elif has_value:
                vals["field_type"] = "value"
            elif opts:
                vals["field_type"] = "status"
        if option_cmds:
            vals["option_ids"] = option_cmds
        return vals

    @api.model
    def _seed(self, spec, parent):
        Node = self.with_context(active_test=False)
        if isinstance(spec, dict):
            for seq, (heading, sub) in enumerate(spec.items()):
                node = Node.search([("name", "=", heading), ("node_type", "=", "heading"),
                                    ("parent_id", "=", parent.id)], limit=1)
                if not node:
                    node = Node.create({"name": heading, "node_type": "heading",
                                        "parent_id": parent.id, "sequence": seq * 10})
                self._seed(sub, node)
        else:
            for seq, item in enumerate(spec):
                vals = self._seed_field_vals(item)
                exists = Node.search_count([("name", "=", vals["name"]), ("node_type", "=", "field"),
                                            ("parent_id", "=", parent.id)])
                if not exists:
                    vals.update(parent_id=parent.id, sequence=seq * 10)
                    Node.create(vals)

    @api.model
    def _load_standard_structure(self):
        """Add anything from the standard list that is missing. Never deletes or edits."""
        self._seed(STANDARD, self.browse())
        return True

    @api.model
    def action_load_standard(self):
        before = self.with_context(active_test=False).search_count([])
        self._load_standard_structure()
        added = self.with_context(active_test=False).search_count([]) - before
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Standard list"),
                "message": self.env._("%s item(s) added. Existing items were not changed.", added),
                "type": "success",
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }


class VetExamOption(models.Model):
    _name = "vet.exam.option"
    _description = "Exam Field Option"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    node_id = fields.Many2one("vet.exam.node", required=True, ondelete="cascade", index=True)
    kind = fields.Selection([("status", "Status"), ("unit", "Unit")], required=True, default="status")
