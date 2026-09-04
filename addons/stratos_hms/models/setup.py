import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class HmsSetup(models.AbstractModel):
    """Pakistan defaults applied at install (data phase, before demo): PKR currency,
    local payment journals, hold-unpaid policy."""
    _name = "hms.setup"
    _description = "HMS install-time setup"

    @api.model
    def apply_pakistan_defaults(self):
        env = self.env
        company = env.company
        pkr = env.ref("base.PKR", raise_if_not_found=False)
        if pkr:
            if not pkr.active:
                pkr.active = True
            has_moves = env["account.move"].sudo().search_count([("company_id", "=", company.id), ("state", "=", "posted")])
            if company.currency_id != pkr and not has_moves:
                try:
                    company.sudo().write({"currency_id": pkr.id})
                except Exception as e:  # noqa: BLE001
                    _logger.warning("Could not switch company currency to PKR: %s", e)
        if not company.country_id:
            pk = env.ref("base.pk", raise_if_not_found=False)
            if pk:
                company.sudo().country_id = pk
        Journal = env["account.journal"].sudo()
        for name, code, jtype in (("Cash Counter", "CASH", "cash"), ("Card Terminal", "CARD", "bank"), ("JazzCash", "JAZZ", "bank"), ("EasyPaisa", "EASY", "bank")):
            if not Journal.search([("code", "=", code), ("company_id", "=", company.id)], limit=1):
                try:
                    Journal.create({"name": name, "code": code, "type": jtype, "company_id": company.id})
                except Exception as e:  # noqa: BLE001
                    _logger.warning("Could not create journal %s: %s", name, e)
        env["ir.config_parameter"].sudo().set_param("stratos_hms.hold_unpaid", "True")
        return True
