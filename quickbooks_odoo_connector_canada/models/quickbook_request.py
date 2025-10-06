# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError

class QuickbooksAPIVts(models.AbstractModel):

    _inherit = "quickbooks.api.vts"
    _description = "QuickBooks API"

    def _get_operation_map(self):
        operation_map = super(QuickbooksAPIVts, self)._get_operation_map()
        operation_map.update({'import_ca_product': 'Item','import_vendor': 'Vendor','import_pro_category': 'Item',
                                'import_invoice': 'Invoice'})
        return operation_map


    def get_data_from_quickbooks(self, qck_url, company_id, token, operation, from_date=None, to_date=None):
        
        operation_map = self._get_operation_map()
        
        entity = operation_map.get(operation)

        if not entity:
            raise UserError(f"Unsupported operation: {operation}")
        
        query = f"SELECT * FROM {entity}"

        if operation == "import_pro_category":
            query += " WHERE Type = 'Category'"
            if from_date and to_date:
                query += f" AND MetaData.CreateTime >= '{from_date}' AND MetaData.CreateTime <= '{to_date}'"
        else:
            if from_date and to_date:
                query += f" WHERE MetaData.CreateTime >= '{from_date}' AND MetaData.CreateTime <= '{to_date}'"

        endpoint = f"{company_id}/query"
        request_url = f"{qck_url}/{endpoint}?query={query}"

        response_info, response_status = self.qb_get_request(token, request_url)

        return response_info, response_status
