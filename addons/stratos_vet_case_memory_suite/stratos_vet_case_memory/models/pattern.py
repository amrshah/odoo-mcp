from odoo import _, api, fields, models

GOOD_OUTCOMES = ("resolved", "improved")
KNOWN_OUTCOMES = ("resolved", "improved", "not_improved", "died")


class VetCmPattern(models.Model):
    """Knowledge base entry: one item (diagnosis / test / drug) for one species.

    Case statistics are rebuilt from finalised cases; vet feedback
    (approve / modify / reject) adjusts the confidence factor.
    """
    _name = "vet.cm.pattern"
    _description = "Knowledge Base Pattern"
    _inherit = ["mail.thread"]
    _order = "species_id, item_type, case_count desc"
    _rec_name = "item_name"

    species_id = fields.Many2one("vet.cm.species", required=True, index=True)
    item_type = fields.Selection([
        ("diagnosis", "Diagnosis"), ("test", "Test"), ("drug", "Treatment"),
    ], required=True)
    diagnosis_id = fields.Many2one("vet.cm.diagnosis")
    test_id = fields.Many2one("vet.cm.test")
    drug_id = fields.Many2one("vet.cm.drug")
    item_name = fields.Char(compute="_compute_item_name", store=True)

    case_count = fields.Integer("Finalised cases", readonly=True)
    known_count = fields.Integer("Cases with known outcome", readonly=True)
    success_count = fields.Integer("Resolved / improved", readonly=True)
    success_rate = fields.Float("Success %", compute="_compute_rates", store=True, digits=(16, 1))

    approved_count = fields.Integer(readonly=True, tracking=True)
    modified_count = fields.Integer(readonly=True, tracking=True)
    rejected_count = fields.Integer(readonly=True, tracking=True,
                                    help="Clinical rejections: better option or contraindicated.")
    excluded_count = fields.Integer("Excluded (did not fit)", readonly=True,
                                    help="Rejected as 'does not fit this patient' or owner "
                                         "declined: normal differential exclusion, no penalty.")
    acceptance_rate = fields.Float("Acceptance %", compute="_compute_rates", store=True,
                                   digits=(16, 1))
    factor = fields.Float("Confidence factor", compute="_compute_rates", store=True,
                          digits=(16, 2),
                          help="Multiplier from vet feedback (0.30 - 1.30).")
    suppressed = fields.Boolean(readonly=True, tracking=True,
                                help="Repeatedly rejected: hidden from suggestions until a "
                                     "senior vet reviews and reinstates it.")

    _key_uniq = models.Constraint(
        "UNIQUE(species_id, item_type, diagnosis_id, test_id, drug_id)",
        "Pattern already exists.")

    @api.depends("item_type", "diagnosis_id", "test_id", "drug_id")
    def _compute_item_name(self):
        for p in self:
            rec = p.diagnosis_id or p.test_id or p.drug_id
            p.item_name = rec.display_name if rec else False

    @api.depends("case_count", "known_count", "success_count",
                 "approved_count", "modified_count", "rejected_count")
    def _compute_rates(self):
        for p in self:
            p.success_rate = 100.0 * p.success_count / p.known_count if p.known_count else 0.0
            decided = p.approved_count + p.modified_count + p.rejected_count
            p.acceptance_rate = (100.0 * (p.approved_count + p.modified_count) / decided
                                 if decided else 0.0)
            f = 1 + 0.05 * p.approved_count + 0.02 * p.modified_count - 0.10 * p.rejected_count
            p.factor = min(1.3, max(0.3, f))

    # ------------------------------------------------------------------
    @api.model
    def _get(self, species, item_type, record):
        field = {"diagnosis": "diagnosis_id", "test": "test_id", "drug": "drug_id"}[item_type]
        pat = self.search([("species_id", "=", species.id), ("item_type", "=", item_type),
                           (field, "=", record.id)], limit=1)
        if not pat:
            pat = self.sudo().create({"species_id": species.id, "item_type": item_type,
                                      field: record.id})
        return pat

    @api.model
    def _rebuild_for_species(self, species):
        """Recount case statistics for one species from finalised cases."""
        cases = self.env["vet.cm.case"].sudo().search([
            ("species_id", "=", species.id), ("state", "=", "final")])
        stats = {}

        def bump(key, outcome):
            st = stats.setdefault(key, [0, 0, 0])
            st[0] += 1
            if outcome in KNOWN_OUTCOMES:
                st[1] += 1
            if outcome in GOOD_OUTCOMES:
                st[2] += 1

        for c in cases:
            if c.diagnosis_id:
                bump(("diagnosis", c.diagnosis_id), c.outcome)
            for t in c.test_line_ids.test_id:
                bump(("test", t), c.outcome)
            for d in c.treatment_line_ids.drug_id:
                bump(("drug", d), c.outcome)
        existing = self.sudo().search([("species_id", "=", species.id)])
        seen = self.browse()
        for (itype, rec), (n, known, good) in stats.items():
            pat = self.sudo()._get(species, itype, rec)
            pat.write({"case_count": n, "known_count": known, "success_count": good})
            seen |= pat
        (existing - seen).write({"case_count": 0, "known_count": 0, "success_count": 0})

    def _register_decision(self, decision, reason_type=False):
        for p in self.sudo():
            if decision == "rejected" and reason_type in ("not_fit", "owner"):
                p.excluded_count += 1
                continue
            if decision == "approved":
                p.approved_count += 1
            elif decision == "modified":
                p.modified_count += 1
            elif decision == "rejected":
                p.rejected_count += 1
                decided = p.approved_count + p.modified_count + p.rejected_count
                if (not p.suppressed and p.rejected_count >= 3
                        and p.rejected_count / decided >= 0.6):
                    p.suppressed = True
                    p.message_post(body=_(
                        "Suppressed automatically after %s rejections. A senior vet must "
                        "review and reinstate it.", p.rejected_count))

    def action_reinstate(self):
        if not self.env.user.has_group("stratos_vet_case_memory.group_vet_cm_manager"):
            from odoo.exceptions import UserError
            raise UserError(_("Only a senior vet can reinstate a pattern."))
        for p in self:
            p.message_post(body=_("Reinstated by %(user)s (rejections reset from %(n)s).",
                                  user=self.env.user.name, n=p.rejected_count))
            p.write({"suppressed": False, "rejected_count": 0})

    def action_suppress(self):
        for p in self:
            p.suppressed = True
            p.message_post(body=_("Suppressed manually by %s.", self.env.user.name))

    def action_view_cases(self):
        self.ensure_one()
        domain = [("species_id", "=", self.species_id.id), ("state", "=", "final")]
        if self.item_type == "diagnosis":
            domain.append(("diagnosis_id", "=", self.diagnosis_id.id))
        elif self.item_type == "test":
            domain.append(("test_line_ids.test_id", "=", self.test_id.id))
        else:
            domain.append(("treatment_line_ids.drug_id", "=", self.drug_id.id))
        return {
            "type": "ir.actions.act_window", "name": self.item_name,
            "res_model": "vet.cm.case", "view_mode": "list,form", "domain": domain,
        }
