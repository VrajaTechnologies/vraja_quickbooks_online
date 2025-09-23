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
                    ('import_account', 'Import Account'),
                    ("import_taxes", "Import Taxes"),
                    ("import_payment_terms", "Import Payment Terms"),
                   ],
        string='Import Operations', default='import_customers'
    )
    
    from_date = fields.Datetime(string='From Date')
    to_date = fields.Datetime(string='To Date')
    qk_customer_type = fields.Char(string="Customer Type")

    def qk_customer_creation(self, customer, customer_type_map):
        customer_type_id = customer.get('CustomerTypeRef', {}).get('value')
        customer_type_name = customer_type_map.get(customer_type_id, '') if customer_type_id else ''
        bill_addr = customer.get('BillAddr', {})
        country_name = bill_addr.get('Country')
        country = self.env['res.country'].search([('name', '=', country_name)], limit=1)

        state_code = bill_addr.get('CountrySubDivisionCode')
        state = self.env['res.country.state'].search([('code', '=', state_code)], limit=1)

        parent_partner = False
        is_company = True
        if customer.get('ParentRef') and customer.get('ParentRef').get('value'):
            parent_qk_id = customer['ParentRef']['value']
            parent_partner = self.env['res.partner'].sudo().search([('qbk_id', '=', parent_qk_id)], limit=1)
            is_company = False

        partner_vals = {
            'name': customer.get('DisplayName', '').strip() or customer.get('CompanyName', '').strip(),
            'street': bill_addr.get('Line1', ''),
            'street2': bill_addr.get('Line2', ''),
            'state_id': state.id if state else False,
            'zip': bill_addr.get('PostalCode', ''),
            'country_id': country.id if country else False,
            'city': bill_addr.get('City', ''),
            'mobile': customer.get('PrimaryPhone', {}).get('FreeFormNumber', ''),
            'email': customer.get('PrimaryEmailAddr', {}).get('Address', ''),
            'qk_customer_type': customer_type_name,
            'qck_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
            'company_id': self.quickbook_instance_id.company_id.id if self.quickbook_instance_id.company_id else self.env.company.id,
            'is_company': is_company,
            'parent_id': parent_partner.id if parent_partner else False,
            'qbk_id': customer.get('Id'),
        }

        partner = self.env['res.partner'].create(partner_vals)
        return partner

    def get_customer_from_quickbooks(self, customer_info, cust_status, qck_url, company_id, token):

        instance_id = self.quickbook_instance_id.id if self.quickbook_instance_id else False

        if cust_status == 200 and customer_info and 'QueryResponse' in customer_info:
            customers = customer_info.get('QueryResponse', {}).get('Customer', [])
            
            customer_type_map = self.env['quickbooks.api.vts'].sudo().get_customer_types(qck_url, company_id, token)
            
            if self.qk_customer_type:
                target_type_id = next((id for id, name in customer_type_map.items() if name.lower() == self.qk_customer_type.lower()),None)
                customers = [c for c in customers if c.get('CustomerTypeRef', {}).get('value') == target_type_id] if target_type_id else []

            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(quickbooks_operation_name='customer',
                quickbooks_operation_type='import',instance=instance_id,
                quickbooks_operation_message='Quickbooks to fetch customers'
            )
            quickbook_map_customers = []
            qkb_map_customer_log_ln = []
            for customer in customers:
                qkb_cust_name = customer.get('DisplayName', '').strip()
                qkb_cust_email = customer.get('PrimaryEmailAddr', {}).get('Address', '')
                qbo_customer_id = customer.get('Id', '')

                partner = False
                if qbo_customer_id:
                    partner = self.env['res.partner'].sudo().search([('qbk_id', '=', qbo_customer_id)],limit=1)
                if not partner and qkb_cust_name:
                    partner = self.env['res.partner'].sudo().search([('name', '=', qkb_cust_name),('email', '=', qkb_cust_email)],limit=1)

                cst_create = False
                if not partner and self.quickbook_instance_id and self.quickbook_instance_id.customer_creation:
                    partner = self.qk_customer_creation(customer, customer_type_map)
                    if partner:
                        cst_create = True

                partner_mapping = self.env['qbo.partner.map.vts'].sudo().search(
                    [('quickbook_id', '=', qbo_customer_id)],limit=1)

                if not partner_mapping:
                    mapping_vals = {
                        'quickbook_instance_id': instance_id,
                        'quickbook_id': qbo_customer_id,
                        'quick_name': qkb_cust_name,
                        'partner_id': partner.id if partner else False,
                        'company_id': self.quickbook_instance_id.company_id.id if self.quickbook_instance_id.company_id else self.env.company.id,
                        'qbo_response': pprint.pformat(customer),
                    }
                    quickbook_map_customers.append(mapping_vals)
                    if not partner:
                        customer_log_val = {
                            'quickbooks_operation_name': 'customer',
                            'quickbooks_operation_type': 'import',
                            'qkb_instance_id': instance_id,
                            'quickbooks_operation_message': f"Customer doesn't match with QuickBooks customer: {qkb_cust_name}",
                            'process_response_message': pprint.pformat(customer),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                            'fault_operation': True
                        }
                        qkb_map_customer_log_ln.append(customer_log_val)
                    elif partner:
                        partner.write({'qck_instance_id':instance_id,'qbk_id':qbo_customer_id})
                        opr_msg = f"Partner successfully mapped with QuickBooks customer: {qkb_cust_name}"
                        if cst_create:
                            opr_msg = f"Customer successfully created and mapped with QuickBooks customer: {qkb_cust_name}"
                        customer_log_val = {
                            'quickbooks_operation_name': 'customer',
                            'quickbooks_operation_type': 'import',
                            'qkb_instance_id': instance_id,
                            'quickbooks_operation_message':opr_msg ,
                            'process_response_message': pprint.pformat(customer),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                        }
                        qkb_map_customer_log_ln.append(customer_log_val)
                else:
                    mapping_vals = {
                        'partner_id': partner.id if partner else False,
                        'qbo_response': pprint.pformat(customer)}
                    partner_mapping.sudo().write(mapping_vals)
                    customer_log_val = {
                            'quickbooks_operation_name': 'customer',
                            'quickbooks_operation_type': 'import',
                            'qkb_instance_id': instance_id,
                            'quickbooks_operation_message': f"Partner updated with QuickBooks customer: {qkb_cust_name}",
                            'process_response_message': pprint.pformat(customer),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                        }
                    qkb_map_customer_log_ln.append(customer_log_val)
            
            if quickbook_map_customers:
                partner_mapped = self.env['qbo.partner.map.vts'].sudo().create(quickbook_map_customers)
            if qkb_map_customer_log_ln:
                customer_map_logger = self.env['quickbooks.log.vts.line'].sudo().create(qkb_map_customer_log_ln)
        else:
            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(quickbooks_operation_name='customer',
                quickbooks_operation_type='import',instance=instance_id,
                quickbooks_operation_message='Failed to fetch customers'
            )
            log_line = self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name='customer',
                quickbooks_operation_type='import',instance=instance_id,
                quickbooks_operation_message='Error during customer import process',
                process_response_message=pprint.pformat(customer_info),log_id=log_id,fault_operation=True)

    def qk_account_creation(self, account):
        
        Account = self.env['account.account'].sudo()

        qkb_account_name = account.get('Name', '').strip()
        qkb_account_type = account.get('AccountType', '')
        qkb_account_subtype = account.get('AccountSubType', '')
        qkb_classification = account.get('Classification', '')
        account_type_map = {
            'Accounts Receivable': 'asset_receivable',
            'Accounts Payable': 'liability_payable',
            'Bank': 'asset_cash',
            'Cost of Goods Sold': 'expense_direct_cost',
            'Income': 'income',
            'Other Income': 'income_other',
            'Expense': 'expense',
            'Other Expense': 'expense',
            'Other Current Asset': 'asset_current',
            'Other Current Liability': 'liability_current',
            'Fixed Asset': 'asset_non_current',
            'Credit Card': 'liability_credit_card',
            'Long Term Liability': 'liability_non_current',
            'Equity': 'equity',
        }
        odoo_account_type = account_type_map.get(qkb_account_type, 'expense')
        account_vals = {
            'name': qkb_account_name,
            'code': self.env['ir.sequence'].next_by_code('account.account'),
            'account_type': odoo_account_type,
            'qck_instance_id':self.quickbook_instance_id.id if self.quickbook_instance_id else False,
            'company_ids': [(6, 0, [self.quickbook_instance_id.company_id.id])] if self.quickbook_instance_id.company_id else [(6, 0, [self.env.company.id])],
            'quickbooks_id': account.get('Id', ''),
            'qk_classification': account.get('Classification', ''),
            'qk_accountsubType': account.get('AccountSubType', ''),
        }
        accounts_detail = Account.create(account_vals)
        return accounts_detail

    def get_account_from_quickbooks(self, account_info, account_status):
        
        if account_status == 200 and account_info and 'QueryResponse' in account_info:

            accounts = account_info.get('QueryResponse', {}).get('Account', [])

            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(quickbooks_operation_name='account',
                quickbooks_operation_type='import',instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Quickbooks to fetch Chart of Account')
            quickbook_map_account = []
            qkb_map_account_log_ln = []
            for account in accounts:
                qkb_account_name =account.get('Name','').strip()
                qbo_account_id = account.get('Id', '')

                accounts_detail = False
                if qkb_account_name:
                    accounts_detail = self.env['account.account'].sudo().search([('name', '=', qkb_account_name)], limit=1)

                acc_create = False
                if not accounts_detail and self.quickbook_instance_id.account_creation:
                    accounts_detail = self.qk_account_creation(account)
                    if accounts_detail:
                        acc_create = True

                account_mapping = self.env['qbo.account.vts'].sudo().search([('quickbook_account_id', '=', qbo_account_id)],limit=1)

                if not account_mapping:
                    mapping_vals = {
                        'quickbook_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                        'quickbook_account_id': qbo_account_id,
                        'quickbook_account_name': qkb_account_name,
                        'account_id': accounts_detail.id if accounts_detail else False,
                        'company_id': self.quickbook_instance_id.company_id.id if self.quickbook_instance_id.company_id else self.env.company.id,
                        'qbo_response': pprint.pformat(account),
                    }
                    quickbook_map_account.append(mapping_vals)
                    if not accounts_detail:
                        account_log_val = {
                            'quickbooks_operation_name': 'account',
                            'quickbooks_operation_type': 'import',
                            'qkb_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                            'quickbooks_operation_message': f"Chart of Account doesn't match with QuickBooks Account: {qkb_account_name}",
                            'process_response_message': pprint.pformat(account),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                            'fault_operation': True
                        }
                        qkb_map_account_log_ln.append(account_log_val)
                    elif accounts_detail:
                        accounts_detail.write({'qck_instance_id':self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                                                'quickbooks_id':qbo_account_id})
                        opr_msg = f"Chart of Account successfully mapped with QuickBooks Account: {qkb_account_name}"
                        if acc_create:
                            opr_msg = f"Chart of Account successfully created and mapped with QuickBooks Account: {qkb_account_name}"
                        account_log_val = {
                            'quickbooks_operation_name': 'account',
                            'quickbooks_operation_type': 'import',
                            'qkb_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                            'quickbooks_operation_message': opr_msg,
                            'process_response_message': pprint.pformat(account),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                        }
                        qkb_map_account_log_ln.append(account_log_val)
                else:
                    mapping_vals = {
                        'account_id': accounts_detail.id if accounts_detail else False,
                        'qbo_response': pprint.pformat(account),
                    }
                    account_mapping.sudo().write(mapping_vals)
                    account_log_val = {
                            'quickbooks_operation_name': 'account',
                            'quickbooks_operation_type': 'import',
                            'qkb_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                            'quickbooks_operation_message': f"Chart of Account updated with QuickBooks Account: {qkb_account_name}",
                            'process_response_message': pprint.pformat(account),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                        }
                    qkb_map_account_log_ln.append(account_log_val)

            if quickbook_map_account:
                account_mapped = self.env['qbo.account.vts'].sudo().create(quickbook_map_account)
            if qkb_map_account_log_ln:
                account_map_logger = self.env['quickbooks.log.vts.line'].sudo().create(qkb_map_account_log_ln)
        else:
            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(quickbooks_operation_name='account',
                quickbooks_operation_type='import',instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Failed Fetch the Chart of Account Records')
            self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name='account',
                quickbooks_operation_type='import',instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Failed To Fetch Chart of Account Records',process_request_message='',
                process_response_message=pprint.pformat(account_info),log_id=log_id,fault_operation=True)

    def get_terms_from_quickbooks(self, payment_info, payment_status):

        if payment_status == 200 and payment_info and 'QueryResponse' in payment_info:
            payment_term = payment_info.get('QueryResponse', {}).get('Term', [])

            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(quickbooks_operation_name='payment_term',
                quickbooks_operation_type='import',instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Quickbooks to fetch Payment terms')
            quickbook_map_payment_term = []
            qkb_map_term_log_ln = []
            for term in payment_term:
                qkb_payment_name = term.get('Name', '').strip()
                qbo_payment_id = term.get('Id', '')

                payment_terms = False
                if qkb_payment_name:
                    payment_terms = self.env['account.payment.term'].sudo().search(['|',('name', '=', qkb_payment_name),('qck_payment_terms_ID', '=', qbo_payment_id)], limit=1)

                term_create = False
                if not payment_terms and self.quickbook_instance_id.payment_term_creation:
                    if term.get('Type') == 'DATE_DRIVEN':
                        line_ids = [(0, 0, {'delay_type': 'days_end_of_month_on_the', 'days_next_month': term.get('DayOfMonthDue', 1)})]
                    else:
                        line_ids = [(0, 0, {'delay_type': 'days_after', 'nb_days': term.get('DueDays', 0)})]
                    term_vals = {
                        'name': qkb_payment_name,
                        'qck_payment_terms_ID': qbo_payment_id,
                        'qck_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                        'line_ids': line_ids,
                        'company_id': self.quickbook_instance_id.company_id.id if self.quickbook_instance_id.company_id else self.env.company.id,
                    }
                    payment_terms = self.env['account.payment.term'].sudo().create(term_vals)
                    if payment_terms:
                        term_create = True

                payment_term_mapping = self.env['qbo.payment.terms.vts'].sudo().search([('quickbook_payment_id', '=', qbo_payment_id)],limit=1)

                if not payment_term_mapping:
                    mapping_vals = {
                        'quickbook_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                        'quickbook_payment_id': qbo_payment_id,
                        'quickbook_payment_name': qkb_payment_name,
                        'payment_id': payment_terms.id if payment_terms else False,
                        'company_id': self.quickbook_instance_id.company_id.id if self.quickbook_instance_id.company_id else self.env.company.id,
                        'qbo_response': pprint.pformat(term),
                    }
                    quickbook_map_payment_term.append(mapping_vals)
                    if not payment_terms:
                        term_log_val = {
                            'quickbooks_operation_name': 'payment_term',
                            'quickbooks_operation_type': 'import',
                            'qkb_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                            'quickbooks_operation_message': f"Payment Terms doesn't match with QuickBooks Terms: {qkb_payment_name}",
                            'process_response_message': pprint.pformat(term),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                            'fault_operation': True
                        }
                        qkb_map_term_log_ln.append(term_log_val)
                    elif payment_terms:
                        if not payment_terms.qck_instance_id:
                            payment_terms.write({'qck_instance_id':self.quickbook_instance_id.id if self.quickbook_instance_id else False})
                        opr_msg = f"Payment Terms successfully mapped with QuickBooks Terms: {qkb_payment_name}"
                        if term_create:
                            opr_msg = f"Payment Terms successfully created and mapped with QuickBooks Terms: {qkb_payment_name}"
                        term_log_val = {
                            'quickbooks_operation_name': 'payment_term',
                            'quickbooks_operation_type': 'import',
                            'qkb_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                            'quickbooks_operation_message': opr_msg,
                            'process_response_message': pprint.pformat(term),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                        }
                        qkb_map_term_log_ln.append(term_log_val)
                else:
                    mapping_vals = {
                        'payment_id': payment_terms.id if payment_terms else False,
                        'qbo_response': pprint.pformat(term),
                    }
                    payment_term_mapping.sudo().write(mapping_vals)
                    term_log_val = {
                            'quickbooks_operation_name': 'payment_term',
                            'quickbooks_operation_type': 'import',
                            'qkb_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                            'quickbooks_operation_message': f"Payment Terms updated with QuickBooks Terms: {qkb_payment_name}",
                            'process_response_message': pprint.pformat(term),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                        }
                    qkb_map_term_log_ln.append(term_log_val)

            if quickbook_map_payment_term:
                terms_mapped = self.env['qbo.payment.terms.vts'].sudo().create(quickbook_map_payment_term)
            if qkb_map_term_log_ln:
                terms_map_logger = self.env['quickbooks.log.vts.line'].sudo().create(qkb_map_term_log_ln)
        else:
            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(quickbooks_operation_name='payment_term',
                quickbooks_operation_type='import',instance=self.quickbook_instance_id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Failed to fetch payment terms')
            self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name='payment_term',
                quickbooks_operation_type='import',instance=self.quickbook_instance_id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Error during payment term import process',
                process_response_message=pprint.pformat(payment_info),log_id=log_id,fault_operation=True)

    def qk_tax_creation(self, tax, qck_url, company_id, token):

        tax_obj = self.env['account.tax']

        taxrate_map = self.env['quickbooks.api.vts'].sudo().get_tax_rates(qck_url, company_id, token)
        tax_group = self.env['account.tax.group'].sudo().search([('name', '=', 'QuickbookTax')], limit=1)
        if not tax_group:
            tax_group = self.env['account.tax.group'].sudo().create({
                'name': 'QuickbookTax',
                'country_id': self.quickbook_instance_id.country_id.id if self.quickbook_instance_id.country_id else False})

        tax_detail = False

        if 'TaxGroup' in tax and tax.get('TaxGroup'):
            tax_vals = {
                'name': tax.get('Name', ''),
                'description': tax.get('Description', ''),
                'qck_taxes_ID': tax.get('Id'),
                'amount': 0,
                'amount_type': 'group',
                'tax_group_id': tax_group.id,
                'qck_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                'company_id': self.quickbook_instance_id.company_id.id if self.quickbook_instance_id.company_id else self.env.company.id,
                'country_id': self.quickbook_instance_id.country_id.id if self.quickbook_instance_id.country_id else False
            }

            # ---------- Purchase Taxes ----------
            if tax.get('PurchaseTaxRateList') and tax['PurchaseTaxRateList'].get('TaxRateDetail', []):
                purchase_tax_rate_ids = []
                for tax_rate in tax['PurchaseTaxRateList']['TaxRateDetail']:
                    tax_rate_id = tax_rate['TaxRateRef']['value']
                    rate_info = taxrate_map.get(tax_rate_id)
                    if not rate_info:
                        continue
    
                    child_tax = tax_obj.sudo().search([
                        ('name', '=', f"{rate_info['name']} Purchase"),
                        ('type_tax_use', '=', 'purchase'),
                        ('company_id', '=', self.quickbook_instance_id.company_id.id)
                    ], limit=1)

                    if not child_tax:
                        child_tax = tax_obj.sudo().create({
                            'name': f"{rate_info['name']} Purchase",
                            'amount': rate_info['rateValue'],
                            'amount_type': 'percent',
                            'type_tax_use': 'purchase',
                            'tax_group_id': tax_group.id,
                            'qck_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                            'country_id': self.quickbook_instance_id.country_id.id if self.quickbook_instance_id.country_id else False
                        })
                    purchase_tax_rate_ids.append(child_tax.id)

                if purchase_tax_rate_ids:
                    vals = tax_vals.copy()
                    vals.update({
                        'type_tax_use': 'purchase',
                        'children_tax_ids': [(6, 0, purchase_tax_rate_ids)],
                    })
                    tax_detail = tax_obj.sudo().create(vals)

            # ---------- Sales Taxes ----------
            if tax.get('SalesTaxRateList') and tax['SalesTaxRateList'].get('TaxRateDetail', []):
                sale_tax_rate_ids = []
                for tax_rate in tax['SalesTaxRateList']['TaxRateDetail']:
                    tax_rate_id = tax_rate['TaxRateRef']['value']
                    rate_info = taxrate_map.get(tax_rate_id)
                    if not rate_info:
                        continue

                    # Search existing sale tax
                    child_tax = tax_obj.sudo().search([
                        ('name', '=', f"{rate_info['name']} Sale"),
                        ('type_tax_use', '=', 'sale'),
                        ('company_id', '=', self.quickbook_instance_id.company_id.id)
                    ], limit=1)

                    if not child_tax:
                        child_tax = tax_obj.sudo().create({
                            'name': f"{rate_info['name']} Sale",
                            'amount': rate_info['rateValue'],
                            'amount_type': 'percent',
                            'type_tax_use': 'sale',
                            'tax_group_id': tax_group.id,
                            'qck_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                            'country_id': self.quickbook_instance_id.country_id.id if self.quickbook_instance_id.country_id else False
                        })
                    sale_tax_rate_ids.append(child_tax.id)

                if sale_tax_rate_ids:
                    vals = tax_vals.copy()
                    vals.update({
                        'type_tax_use': 'sale',
                        'children_tax_ids': [(6, 0, sale_tax_rate_ids)],
                    })
                    tax_detail = tax_obj.sudo().create(vals)

        return tax_detail

    def get_taxes_from_quickbooks(self, tax_info, tax_status, qck_url, company_id, token):

        if tax_status == 200 and tax_info and 'QueryResponse' in tax_info:
            taxes = tax_info.get('QueryResponse', {}).get('TaxCode', [])

            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(quickbooks_operation_name='taxes',
                quickbooks_operation_type='import',instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Quickbooks to fetch Taxes')

            quickbook_map_taxes = []
            qkb_map_taxes_log_ln = []
            active_taxes = [tax for tax in taxes if tax.get('Active') is True]
            for tax in active_taxes:
                qkb_tax_name = tax.get('Name','')
                qbo_tax_id = tax.get('Id', '')

                tax_detail = False
                if qkb_tax_name:
                    tax_detail = self.env['account.tax'].sudo().search(['|',('name', '=', qkb_tax_name),('qck_taxes_ID', '=', qbo_tax_id)], limit=1)

                tax_created = False
                if not tax_detail and self.quickbook_instance_id.taxes_creation:
                    if 'Active' in tax and tax.get('Active') and tax.get('Taxable'):
                        tax_detail = self.qk_tax_creation(tax, qck_url, company_id, token)
                        if tax_detail:
                            tax_created = True

                tax_mapping = self.env['qbo.taxes.vts'].sudo().search([('quickbook_tax_id', '=', qbo_tax_id)],limit=1)
                if not tax_mapping:
                    mapping_vals = {
                        'quickbook_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                        'quickbook_tax_id': qbo_tax_id,
                        'quickbook_tax_name': qkb_tax_name,
                        'tax_id': tax_detail.id if tax_detail else False,
                        'company_id': self.quickbook_instance_id.company_id.id if self.quickbook_instance_id.company_id else self.env.company.id,
                        'qbo_response': pprint.pformat(tax),
                    }
                    quickbook_map_taxes.append(mapping_vals)
                    if not tax_detail:
                        taxes_log_val = {
                            'quickbooks_operation_name': 'taxes',
                            'quickbooks_operation_type': 'import',
                            'qkb_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                            'quickbooks_operation_message': f"Taxes doesn't match with QuickBooks Taxes: {qkb_tax_name}",
                            'process_response_message': pprint.pformat(tax),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                            'fault_operation': True
                        }
                        qkb_map_taxes_log_ln.append(taxes_log_val)
                    elif tax_detail:
                        if not tax_detail.qck_instance_id:
                            tax_detail.write({'qck_instance_id':self.quickbook_instance_id.id if self.quickbook_instance_id else False})
                        opr_msg = f"Taxes successfully mapped with QuickBooks Taxes: {qkb_tax_name}"
                        if tax_created:
                            opr_msg = f"Taxes successfully created and mapped with QuickBooks Taxes: {qkb_tax_name}"      
                        taxes_log_val = {
                            'quickbooks_operation_name': 'taxes',
                            'quickbooks_operation_type': 'import',
                            'qkb_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                            'quickbooks_operation_message': opr_msg,
                            'process_response_message': pprint.pformat(tax),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                        }
                        qkb_map_taxes_log_ln.append(taxes_log_val)
                else:
                    mapping_vals = {
                        'tax_id': tax_detail.id if tax_detail else False,
                        'qbo_response': pprint.pformat(tax),
                    }
                    tax_mapping.sudo().write(mapping_vals)
                    taxes_log_val = {
                        'quickbooks_operation_name': 'taxes',
                        'quickbooks_operation_type': 'import',
                        'qkb_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                        'quickbooks_operation_message': f"Taxes updated with QuickBooks Taxes: {qkb_tax_name}",
                        'process_response_message': pprint.pformat(tax),
                        'quickbooks_operation_id': log_id.id if log_id else False}
                    qkb_map_taxes_log_ln.append(taxes_log_val)

            if quickbook_map_taxes:
                taxes_mapped = self.env['qbo.taxes.vts'].sudo().create(quickbook_map_taxes)
            if qkb_map_taxes_log_ln:
                taxes_map_logger = self.env['quickbooks.log.vts.line'].sudo().create(qkb_map_taxes_log_ln)

        else:
            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(
                quickbooks_operation_name='taxes',quickbooks_operation_type='import',
                instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Failed to fetch taxes')
            self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name='taxes',
                quickbooks_operation_type='import',instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Error during taxes import process',
                process_response_message=pprint.pformat(tax_info),log_id=log_id,fault_operation=True)

    def execute_process_of_quickbooks(self):
        if self.quickbook_instance_id and self.quickbook_instance_id.access_token:
            qck_url = self.quickbook_instance_id.quickbook_base_url
            company_id = self.quickbook_instance_id.realm_id
            token = self.quickbook_instance_id.access_token
            from_date = self.from_date.strftime('%Y-%m-%dT%H:%M:%S-07:00') if self.from_date else None
            to_date = self.to_date.strftime('%Y-%m-%dT%H:%M:%S-07:00') if self.to_date else None

            if self.import_operations == 'import_customers':
                customer_info, cust_status = self.env['quickbooks.api.vts'].get_data_from_quickbooks(qck_url,company_id,
                    token,self.import_operations,from_date=from_date,to_date=to_date)
                qk_customer_details = self.get_customer_from_quickbooks(customer_info, cust_status, qck_url, company_id, token)

            elif self.import_operations == 'import_account':
                account_info, account_status = self.env['quickbooks.api.vts'].get_data_from_quickbooks(qck_url,company_id,
                    token,self.import_operations,from_date=from_date,to_date=to_date)

                qk_account_details = self.get_account_from_quickbooks(account_info, account_status)

            elif self.import_operations == 'import_payment_terms':
                payment_info, payment_status = self.env['quickbooks.api.vts'].get_data_from_quickbooks(qck_url,company_id,
                    token,self.import_operations,from_date=from_date,to_date=to_date)

                qk_payment_terms_details = self.get_terms_from_quickbooks(payment_info, payment_status)

            elif self.import_operations == 'import_taxes':
                tax_info, tax_status = self.env['quickbooks.api.vts'].get_data_from_quickbooks(qck_url,company_id,
                    token,self.import_operations,from_date=from_date,to_date=to_date)

                qk_taxes_details = self.get_taxes_from_quickbooks(tax_info, tax_status, qck_url, company_id, token)