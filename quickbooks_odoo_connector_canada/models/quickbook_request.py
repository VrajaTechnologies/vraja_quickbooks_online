# -*- coding: utf-8 -*-
from odoo import models

class QuickbooksAPIVts(models.AbstractModel):

    _inherit = "quickbooks.api.vts"
    _description = "QuickBooks API"

    def _get_operation_map(self):
        operation_map = super(QuickbooksAPIVts, self)._get_operation_map()
        operation_map.update({'import_ca_product': 'Item','import_vendor': 'Vendor'})
        return operation_map
