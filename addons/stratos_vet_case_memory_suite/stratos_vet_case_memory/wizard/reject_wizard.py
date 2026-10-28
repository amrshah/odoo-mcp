from odoo import _, fields, models
from odoo.exceptions import UserError


class VetCmRejectWizard(models.TransientModel):
    _name = "vet.cm.reject.wizard"
    _description = "Reject Suggestion"

    line_ids = fields.Many2many("vet.cm.suggestion.line", string="Suggestions")
    reason_type = fields.Selection([
        ("not_fit", "Does not fit this patient"),
        ("better_option", "A better option is available"),
        ("contra", "Contraindicated for this animal"),
        ("owner", "Owner declined / cost"),
        ("other", "Other"),
    ], default="not_fit", required=True)
    reason = fields.Text("Details")

    def action_confirm(self):
        self.ensure_one()
        if self.reason_type == "other" and not self.reason:
            raise UserError(_("Please write the reason."))
        label = dict(self._fields["reason_type"].selection)[self.reason_type]
        text = label + (f": {self.reason}" if self.reason else "")
        self.line_ids._check_can_decide()
        self.line_ids._decide("rejected", text, self.reason_type)
        return {"type": "ir.actions.act_window_close"}
