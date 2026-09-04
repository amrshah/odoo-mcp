from odoo import fields, models

class VetDemoRegistry(models.Model):
    _name="vet.demo.registry"; _description="VetCairn Demo Cleanup Registry"; _order="sequence desc,id desc"
    model_name=fields.Char(required=True,index=True); res_id=fields.Integer(required=True,index=True); sequence=fields.Integer(required=True); label=fields.Char()
