# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    qck_instance_id = fields.Many2one('quickbooks.connect', string="Quickbook Instance", copy=False)
    qkb_product_ID = fields.Char(string="Quickbook Product ID")
    qck_product_type = fields.Char(string="Quickbook Product Type ID")

    def creating_product_payload(self,product):
        payload = {
            "Name": product.name,
            "Type": product.type,
            "TrackQtyOnHand": True,
            "QtyOnHand": int(product.qty_available),
            "InvStartDate": product.create_date.strftime("%Y-%m-%d") if product.create_date else product.date.today(),
            "IncomeAccountRef": {
                "value":product.property_account_income_id.id or "79",
                "name":product.property_account_income_id.name or "Sales of Product Income"
            },
            "ExpenseAccountRef": {
                "value": product.property_account_expense_id or '80',
                "name": product.property_account_expense_id.name or "Cost of Goods Sold"
            },
            "AssetAccountRef": {
                "value": '81',
                "name": "Inventory Asset"
            }
        }
        return payload


    def export_product_to_qbk(self,product):
        if product.qkb_product_ID:
            product.message_post(body=f"Product already exported to QuickBooks with ID {product.qkb_product_ID}.")
            return
        company = product.company_id.id if product.company_id else False
        quickbook_instance = self.env['quickbooks.connect'].sudo().search([('company_id', '=', company)], limit=1)
        if not quickbook_instance:
            product.message_post(body=f"No QuickBooks instance configured for {company} company.")
            return
        log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(quickbooks_operation_name="product",
                                                                                quickbooks_operation_type="export",
                                                                                instance=quickbook_instance.id,
                                                                                quickbooks_operation_message=f"Starting export for Bill Payment {product.name}")
        try:
            qbk_product_val =  self.creating_product_payload(product)

            inv_url = f"{quickbook_instance.quickbook_base_url}/{quickbook_instance.realm_id}/item"

            response_json, status_code = self.env['quickbooks.api.vts'].sudo().qb_post_request(quickbook_instance.access_token,inv_url, qbk_product_val)

            if status_code in (200, 201):
                print(status_code)
            else:
                msg = f"Failed to export product {product.name} to QuickBooks. Response: {response_json}"
                product.message_post(body=msg)
        except Exception as e:
            product.message_post(body=f"Exception while exporting product {product.name} to QuickBooks: {str(e)}")

    def export_product_to_quickbooks(self):
        for product in self:
            product.export_product_to_qbk(product)

