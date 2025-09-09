from odoo import models, fields
from datetime import timedelta, datetime
import pprint


class QuickbooksOperations(models.TransientModel):
    _name = 'quickbooks.operations'
    _description = 'Quickbooks Import Export'

    def _get_default_from_date_order(self):
        quickbook_instance_id = self.env.context.get('active_id')
        instance_id = self.env['quickbooks.connect'].search([('id', '=', quickbook_instance_id)], limit=1)
        from_date_order = fields.Datetime.now() - timedelta(30)
        from_date_order = fields.Datetime.to_string(from_date_order)
        return from_date_order

    def _get_default_to_date(self):
        to_date = fields.Datetime.now()
        to_date = fields.Datetime.to_string(to_date)
        return to_date

    quickbook_instance_id = fields.Many2one('quickbooks.connect',string='Quickbooks Connection',default=lambda self: self.env.context.get('active_id'))
    quickbook_operation = fields.Selection([('import', 'Import')],
                                         string='Quickbooks Operations', default='import')
    import_operations = fields.Selection(
        selection=[("import_customers", "Import Customer"),
                    ("import_taxes", "Import Taxes"),
                    ("import_payment_terms", "Import Payment Terms"),
                    ('import_account', 'Import Account'),
                   ],
        string='Import Operations', default='import_customers'
    )
    
    from_date = fields.Datetime(string='From Date', default=_get_default_from_date_order)
    to_date = fields.Datetime(string='To Date', default=_get_default_to_date)
    qk_customer_type = fields.Char(string="Customer Type")

    def execute_process_of_quickbooks(self):
        if self.quickbook_instance_id and self.quickbook_instance_id.access_token:
            qck_url = self.quickbook_instance_id.quickbook_base_url
            company_id = self.quickbook_instance_id.realm_id
            token = self.quickbook_instance_id.access_token
            from_date = self.from_date.strftime('%Y-%m-%dT%H:%M:%S-07:00') if self.from_date else None
            to_date = self.to_date.strftime('%Y-%m-%dT%H:%M:%S-07:00') if self.to_date else None

            if self.import_operations == 'import_customers':
                customer_info, cust_status = self.env['quickbooks.api.vts'].get_data_from_qiuckbooks(
                    qck_url,
                    company_id,
                    token,
                    self.import_operations,
                    from_date=from_date,
                    to_date=to_date
                )

                if cust_status == 200 and customer_info and 'QueryResponse' in customer_info:
                    customers = customer_info.get('QueryResponse', {}).get('Customer', [])
                    
                    if self.qk_customer_type:
                        customer_type_map = self.env['quickbooks.api.vts'].get_customer_types(qck_url, company_id, token)
                        target_type_id = next((id for id, name in customer_type_map.items() if name.lower() == self.qk_customer_type.lower()),None)
                        customers = [c for c in customers if c.get('CustomerTypeRef', {}).get('value') == target_type_id] if target_type_id else []

                    # log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(
                    #     quickbooks_operation_name='customer',
                    #     quickbooks_operation_type='import',
                    #     instance=self.quickbook_instance_id if self.quickbook_instance_id else False,
                    #     quickbooks_operation_message='Quickbooks to fetch customers'
                    # )
                    quickbook_map_customers = []
                    qkb_map_customer_log_ln = []
                    for customer in customers:
                        qkb_cust_email = ''
                        if customer.get('PrimaryEmailAddr', ''):
                            qkb_cust_email = customer.get('PrimaryEmailAddr', {}).get('Address', '')
                        qkb_cust_name = customer.get('FullyQualifiedName', '')
                        qbo_customer_id = customer.get('Id', '')

                        partner = False
                        if qkb_cust_name or qkb_cust_email:
                            partner = self.env['res.partner'].sudo().search(
                                ['|', ('name', '=', qkb_cust_name), ('email', '=', qkb_cust_email)],limit=1)
                        
                        partner_mapping = self.env['qbo.partner.map.vts'].sudo().search(
                            [('quickbook_id', '=', qbo_customer_id)],
                            limit=1
                        )
                        
                        if not partner_mapping:
                            mapping_vals = {
                                'quickbook_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                                'quickbook_id': qbo_customer_id,
                                'quick_name': qkb_cust_name,
                                'partner_id': partner.id if partner else False,
                                'company_id': self.quickbook_instance_id.company_id.id if self.quickbook_instance_id.company_id else self.env.company.id,
                                'qbo_response': pprint.pformat(str(customer)),
                            }
                            quickbook_map_customers.append(mapping_vals)
                            # if not partner:
                            #     customer_log_val = {
                            #         'quickbooks_operation_name': 'customer',
                            #         'quickbooks_operation_type': 'import',
                            #         'qkb_instance_id': self.quickbook_instance_id if self.quickbook_instance_id else False,
                            #         'quickbooks_operation_message': f"Partner doesn't match with QuickBooks customer: {qkb_cust_name}",
                            #         'process_response_message': pprint.pformat(customer_info),
                            #         'quickbooks_operation_id': log_id.id if log_id else False,
                            #         'fault_operation': True
                            #     }
                            #     qkb_map_customer_log_ln.append(customer_log_val)
                            # elif partner:
                            #     customer_log_val = {
                            #         'quickbooks_operation_name': 'customer',
                            #         'quickbooks_operation_type': 'import',
                            #         'qkb_instance_id': self.quickbook_instance_id if self.quickbook_instance_id else False,
                            #         'quickbooks_operation_message': f"Partner successfully mapped with QuickBooks customer: {qkb_cust_name}",
                            #         'process_response_message': pprint.pformat(customer_info),
                            #         'quickbooks_operation_id': log_id.id if log_id else False,
                            #         'fault_operation': False
                            #     }
                            #     qkb_map_customer_log_ln.append(customer_log_val)
                        else:
                            mapping_vals = {
                                'partner_id': partner.id if partner else False,
                                'qbo_response': pprint.pformat(str(customer)),
                            }
                            partner_mapping.sudo().write(mapping_vals)
                    
                    if quickbook_map_customers:
                        self.env['qbo.partner.map.vts'].sudo().create(quickbook_map_customers)


                else:
                    log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(
                        quickbooks_operation_name='customer',
                        quickbooks_operation_type='import',
                        instance=self.quickbook_instance_id if self.quickbook_instance_id else False,
                        quickbooks_operation_message='Failed to fetch customers'
                    )
                    
                    self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                        quickbooks_operation_name='customer',
                        quickbooks_operation_type='import',
                        instance=self.quickbook_instance_id if self.quickbook_instance_id else False,
                        quickbooks_operation_message='Error during customer import process',
                        process_request_message='',
                        process_response_message=pprint.pformat(customer_info),
                        log_id=log_id,
                        fault_operation=True
                    )

