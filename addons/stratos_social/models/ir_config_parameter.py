from odoo import api, models


class IrConfigParameter(models.Model):
    _inherit = 'ir.config_parameter'

    @api.model
    def get_str(self, key, default=''):
        val = self.get_param(key, default)
        return str(val) if val is not None and val is not False else (default or '')

    @api.model
    def get_int(self, key, default=0):
        val = self.get_param(key, default)
        try:
            return int(val)
        except (ValueError, TypeError):
            return default
