from odoo import models, fields, api
from datetime import timedelta, datetime
import pprint

class QuickbooksWizardInherit(models.TransientModel):
    _inherit = "quickbooks.operations"

    import_operations = fields.Selection(selection_add=[("import_product", "Import Product")])

    def get_product_from_quickbooks(self, product_info, product_status):

        if product_status == 200 and product_info and 'QueryResponse' in product_info:
            product_item = product_info.get('QueryResponse').get('Item')

            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(
                quickbooks_operation_name='product',
                quickbooks_operation_type='import',
                instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Quickbooks to fetch Items')
            quickbook_map_product = []
            quickbook_map_product_log_ln = []
            for product in product_item:
                qkb_product_name = product.get('Name', '').strip()
                qkb_product_id = product.get('Id', '')

                product_detail = False
                if qkb_product_name:
                    product_detail = self.env['product.template'].sudo().search(['|', ('name', '=', qkb_product_name),('qkb_product_ID','=',qkb_product_id)], limit=1)

                product_mapping =self.env['qbo.product.vts'].sudo().search([('quickbook_product_id', '=', qkb_product_id)],limit=1)
                if not product_mapping:
                    mapping_vals = {
                        'quickbook_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                        'quickbook_product_id': qkb_product_id,
                        'quickbook_product_name': qkb_product_name,
                        'product_id': product_detail.id if product_detail else False,
                        'company_id': self.quickbook_instance_id.company_id.id if self.quickbook_instance_id.company_id else self.env.company.id,
                        'qbo_response': pprint.pformat(product),
                    }
                    quickbook_map_product.append(mapping_vals)
                    if not product_detail:
                        product_log_vals = {
                            'quickbooks_operation_name': 'product',
                            'quickbooks_operation_type': 'import',
                            'qkb_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                            'quickbooks_operation_message': f"Product doesn't match with QuickBooks Product: {qkb_product_name}",
                            'process_response_message': pprint.pformat(product),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                            'fault_operation': True
                        }
                        quickbook_map_product_log_ln.append(product_log_vals)

                    elif product_detail:
                        product_detail.write({'qck_instance_id':self.quickbook_instance_id.id if self.quickbook_instance_id else False})
                        product_log_vals = {
                            'quickbooks_operation_name': 'product',
                            'quickbooks_operation_type': 'import',
                            'qkb_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                            'quickbooks_operation_message': f"Product successfully mapped with QuickBooks customer: {qkb_product_name}",
                            'process_response_message': pprint.pformat(product),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                            'fault_operation': True
                        }
                        quickbook_map_product_log_ln.append(product_log_vals)
                else:
                    mapping_vals = {
                        'product_id': product_detail.id if product_detail else False,
                        'qbo_response': pprint.pformat(product),
                    }
                    product_mapping.sudo().write(mapping_vals)

            if quickbook_map_product:
                product_mapped = self.env['qbo.product.vts'].sudo().create(quickbook_map_product)
                product_map_logger = self.env['quickbooks.log.vts.line'].sudo().create(quickbook_map_product_log_ln)

        else:
            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(quickbooks_operation_name='product',
                quickbooks_operation_type='import',instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Failed to fetch customers'
            )
            log_line = self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name='product',
                quickbooks_operation_type='import',instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Error during customer import process',
                process_response_message=pprint.pformat(product_info),log_id=log_id,fault_operation=True)

    def execute_process_of_quickbooks(self):
        res = super(QuickbooksWizardInherit, self).execute_process_of_quickbooks()
        if self.quickbook_instance_id and self.quickbook_instance_id.access_token:
            qck_url = self.quickbook_instance_id.quickbook_base_url
            company_id = self.quickbook_instance_id.realm_id
            token = self.quickbook_instance_id.access_token
            from_date = self.from_date.strftime('%Y-%m-%dT%H:%M:%S-07:00') if self.from_date else None
            to_date = self.to_date.strftime('%Y-%m-%dT%H:%M:%S-07:00') if self.to_date else None

            if self.import_operations == 'import_product':
                product_info, product_status = self.env['quickbooks.api.vts'].get_data_from_quickbooks(qck_url, 
                    company_id,token, self.import_operations, from_date=from_date, to_date=to_date)

                qk_taxes_details = self.get_product_from_quickbooks(product_info, product_status)

        return res