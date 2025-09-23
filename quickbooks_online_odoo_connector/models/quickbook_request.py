from odoo import models
from odoo.exceptions import UserError
import requests


class QuickbooksAPIVts(models.AbstractModel):
    _inherit = "quickbooks.api.vts"
    _description = "QuickBooks API"

    def _get_operation_map(self):
        operation_map = super(QuickbooksAPIVts, self)._get_operation_map()
        operation_map.update({'import_product': 'Item'})
        
        return operation_map
        