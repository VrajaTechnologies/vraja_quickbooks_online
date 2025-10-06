from odoo import models, fields, api
from datetime import timedelta, datetime
import pprint

class QuickbooksWizardInherit(models.TransientModel):
    _inherit = "quickbooks.operations"

    import_operations = fields.Selection(selection_add=[("import_vendor", "Import Vendor"),("import_pro_category", "Import Product Category"),("import_ca_product", "Import Product")])

    def _prepare_product_creation(self, product):
        product_type = product.get('Type')

        type_mapping = {
            'Inventory': (True, 'consu'),
            'NonInventory': (False, 'consu'),
            'Service': (False, 'service'),
            'Assembly': (False, 'combo'),
        }

        is_storable, qk_product_type = type_mapping.get(product_type, (False, 'consu'))

        def find_account(ref):
            return (self.env['account.account'].sudo().search([('quickbooks_id', '=', ref.get('value'))], limit=1) if ref else False)

        income_account = find_account(product.get('IncomeAccountRef'))
        expense_account = find_account(product.get('ExpenseAccountRef'))

        parent_ref = product.get('ParentRef')
        category = False
        if parent_ref:
            category = self.env['product.category'].sudo().search([('qkca_category_ID', '=', parent_ref.get('value'))], limit=1)

        product_val = {
            'name': product.get('Name', ''),
            'description_sale': product.get('Description', ''),
            'list_price': product.get('UnitPrice', 0.0),
            'standard_price': product.get('PurchaseCost', 0.0),
            'is_storable': is_storable,
            'type': qk_product_type,
            'qkca_product_type': product_type,
            'qkca_product_ID': product.get('Id', ''),
            'qck_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
            'company_id': self.quickbook_instance_id.company_id.id if self.quickbook_instance_id.company_id else False,
            'property_account_income_id': income_account.id if income_account else False,
            'property_account_expense_id': expense_account.id if expense_account else False,
            'categ_id': category.id if category else False,
        }

        product_detail = self.env['product.template'].sudo().create(product_val)

        return product_detail

    def get_ca_product_from_quickbooks(self, product_info, product_status):

        if product_status == 200 and product_info and 'QueryResponse' in product_info:
            product_item = product_info.get('QueryResponse').get('Item')

            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(
                quickbooks_operation_name='product',quickbooks_operation_type='import',
                instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Quickbooks to fetch Items')

            quickbook_map_product = []
            quickbook_map_product_log_ln = []
            for product in product_item:

                if product.get('Type') == 'Category':
                    continue

                qkb_product_name = product.get('Name', '').strip()
                qkb_product_id = product.get('Id', '')

                product_detail = False
                if qkb_product_name:
                    product_detail = self.env['product.template'].sudo().search(['|', ('name', '=', qkb_product_name),('qkca_product_ID','=',qkb_product_id)], limit=1)

                pr_created = False
                if not product_detail and self.quickbook_instance_id.qkca_product_creation:
                    product_detail = self._prepare_product_creation(product)
                    pr_created = True

                product_mapping =self.env['qbo.product.ca.map.vts'].sudo().search([('quickbook_product_id', '=', qkb_product_id)],limit=1)
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
                        product_detail.write({'qck_instance_id':self.quickbook_instance_id.id if self.quickbook_instance_id else False,'qkca_product_ID':qkb_product_id})
                        opr_message = f"Product successfully mapped with QuickBooks product: {qkb_product_name}"
                        if pr_created:
                            opr_message = f"Product successfully created and mapped with QuickBooks product: {qkb_product_name}"
                        product_log_vals = {
                            'quickbooks_operation_name': 'product',
                            'quickbooks_operation_type': 'import',
                            'qkb_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                            'quickbooks_operation_message': opr_message,
                            'process_response_message': pprint.pformat(product),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                        }
                        quickbook_map_product_log_ln.append(product_log_vals)
                else:
                    mapping_vals = {
                        'product_id': product_detail.id if product_detail else False,
                        'qbo_response': pprint.pformat(product),
                    }
                    if product_detail and qkb_product_id:
                        product_detail.qkca_product_ID = qkb_product_id
                        product_detail.qck_instance_id = self.quickbook_instance_id.id if self.quickbook_instance_id else False
                    product_mapping.sudo().write(mapping_vals)
                    product_log_vals = {
                            'quickbooks_operation_name': 'product',
                            'quickbooks_operation_type': 'import',
                            'qkb_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                            'quickbooks_operation_message': f"Product updated with QuickBooks product: {qkb_product_name}",
                            'process_response_message': pprint.pformat(product),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                        }
                    quickbook_map_product_log_ln.append(product_log_vals)

            if quickbook_map_product:
                product_mapped = self.env['qbo.product.ca.map.vts'].sudo().create(quickbook_map_product)
            if quickbook_map_product_log_ln:
                product_map_logger = self.env['quickbooks.log.vts.line'].sudo().create(quickbook_map_product_log_ln)

        else:
            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(quickbooks_operation_name='product',
                quickbooks_operation_type='import',instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Failed to fetch Products'
            )
            log_line = self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name='product',
                quickbooks_operation_type='import',instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Error during products import process',
                process_response_message=pprint.pformat(product_info),log_id=log_id,fault_operation=True)

    def qbk_ca_vendor_creation(self,vendor):

        bill_addr = vendor.get('BillAddr', {})

        country_name = bill_addr.get('Country')
        country = self.env['res.country'].search([('name', '=', country_name)], limit=1)

        state_code = bill_addr.get('CountrySubDivisionCode')
        state = self.env['res.country.state'].search([('code', '=', state_code)], limit=1)

        parent_vendor = False
        is_company = True
        if vendor.get('ParentRef') and vendor.get('ParentRef').get('value'):
            parent_qk_id = vendor['ParentRef']['value']
            parent_vendor = self.env['res.partner'].sudo().search([('qkca_vendor_ID', '=', parent_qk_id)], limit=1)
            is_company = False

        vendor_vals = {
            'name': vendor.get('DisplayName', '').strip() or vendor.get('CompanyName', '').strip(),
            'street': bill_addr.get('Line1', ''),
            'street2': bill_addr.get('Line2', ''),
            'state_id': state.id if state else False,
            'zip': bill_addr.get('PostalCode', ''),
            'country_id': country.id if country else False,
            'city': bill_addr.get('City', ''),
            'mobile': vendor.get('PrimaryPhone', {}).get('FreeFormNumber', ''),
            'email': vendor.get('PrimaryEmailAddr', {}).get('Address', ''),
            'qck_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
            'company_id': self.quickbook_instance_id.company_id.id if self.quickbook_instance_id.company_id else self.env.company.id,
            'is_company': is_company,
            'parent_id': parent_vendor.id if parent_vendor else False,
            'qkca_vendor_ID': vendor.get('Id'),
        }
        vendor = self.env['res.partner'].create(vendor_vals)
        return vendor

    def get_vendor_from_quickbooks(self, vendor_info, vendor_status):

        if vendor_status == 200 and vendor_info and 'QueryResponse' in vendor_info:
            vendor_details = vendor_info.get('QueryResponse').get('Vendor')

            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(
                quickbooks_operation_name='vendor', quickbooks_operation_type='import',
                instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Quickbooks to fetch Vendors')

            quickbook_map_vendor = []
            quickbook_map_vendor_log_ln = []

            for vendor in vendor_details:
                qkb_vendor_name = vendor.get('DisplayName').strip()
                qkb_vendor_id = vendor.get('Id', '')
                qkb_vnd_email = vendor.get('PrimaryEmailAddr', {}).get('Address', '')

                vendor_detail = False
                if qkb_vendor_name:
                    vendor_detail = self.env['res.partner'].sudo().search(['|', ('name', '=', qkb_vendor_name), ('qkca_vendor_ID', '=', qkb_vendor_id)], limit=1)

                if not vendor_detail and qkb_vnd_email:
                    vendor_detail = self.env['res.partner'].sudo().search([('name', '=', qkb_vendor_name),('email', '=', qkb_vnd_email)],limit=1)

                vendor_created = False
                if not vendor_detail and self.quickbook_instance_id.qkca_vendor_creation:
                    vendor_detail = self.qbk_ca_vendor_creation(vendor)
                    vendor_created = True

                vendor_mapping = self.env['qbo.vendor.ca.map.vts'].sudo().search([('quickbook_vendor_id', '=', qkb_vendor_id)], limit=1)
                
                if not vendor_mapping:
                    mapping_vals = {
                        'quickbook_vendor_name': qkb_vendor_name,
                        'quickbook_vendor_id': qkb_vendor_id,
                        'quickbook_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                        'vendor_id': vendor_detail.id if vendor_detail else False,
                        'company_id': self.quickbook_instance_id.company_id.id if self.quickbook_instance_id.company_id else self.env.company.id,
                        'qbo_response': pprint.pformat(vendor),
                    }
                    quickbook_map_vendor.append(mapping_vals)
                    if not vendor_detail:
                        vendor_log_vals = {
                            'quickbooks_operation_name': 'vendor',
                            'quickbooks_operation_type': 'import',
                            'qkb_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                            'quickbooks_operation_message': f"Vendor doesn't match with QuickBooks Vendor: {qkb_vendor_name}",
                            'process_response_message': pprint.pformat(vendor),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                            'fault_operation': True
                        }
                        quickbook_map_vendor_log_ln.append(vendor_log_vals)

                    elif vendor_detail:
                        vendor_detail.write(
                            {'qck_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                             'qkca_vendor_ID': qkb_vendor_id})

                        vc_message = f"Vendor successfully mapped with QuickBooks Vendor: {qkb_vendor_name}"
                        if vendor_created:
                            vc_message = f"Vendor successfully created and mapped with QuickBooks vendor: {qkb_vendor_name}"

                        vendor_log_vals = {
                            'quickbooks_operation_name': 'vendor','quickbooks_operation_type': 'import',
                            'qkb_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                            'quickbooks_operation_message': vc_message,'process_response_message': pprint.pformat(vendor),
                            'quickbooks_operation_id': log_id.id if log_id else False,
                        }
                        quickbook_map_vendor_log_ln.append(vendor_log_vals)
                else:
                    mapping_vals = {
                        'vendor_id': vendor_detail.id if vendor_detail else False,
                        'qbo_response': pprint.pformat(vendor),
                    }
                    if vendor_detail and qkb_vendor_id:
                        vendor_detail.qkca_vendor_ID = qkb_vendor_id
                        vendor_detail.qck_instance_id = self.quickbook_instance_id.id if self.quickbook_instance_id else False
                    vendor_mapping.sudo().write(mapping_vals)
                    vendor_log_vals = {
                        'quickbooks_operation_name': 'vendor',
                        'quickbooks_operation_type': 'import',
                        'qkb_instance_id': self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                        'quickbooks_operation_message': f"Vendor updated with QuickBooks Vendor: {qkb_vendor_name}",
                        'process_response_message': pprint.pformat(vendor),
                        'quickbooks_operation_id': log_id.id if log_id else False,
                    }
                    quickbook_map_vendor_log_ln.append(vendor_log_vals)

            if quickbook_map_vendor:
                vendor_mapped = self.env['qbo.vendor.ca.map.vts'].sudo().create(quickbook_map_vendor)
            if quickbook_map_vendor_log_ln:
                vendor_map_logger = self.env['quickbooks.log.vts.line'].sudo().create(quickbook_map_vendor_log_ln)
        else:
            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(
                quickbooks_operation_name='vendor',
                quickbooks_operation_type='import',
                instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Failed to fetch Vendor'
                )
            log_line = self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                quickbooks_operation_name='vendor',
                quickbooks_operation_type='import',
                instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Error during vendor import process',
                process_response_message=pprint.pformat(vendor_info), log_id=log_id, fault_operation=True)

    def _prepare_category_creation(self, category_data):

        ProductCategory = self.env['product.category'].sudo()

        qkb_category_id = category_data.get('Id')
        qkb_category_name = category_data.get('Name', '').strip()

        category = ProductCategory.search(['|', ('name', '=', qkb_category_name),('qkca_category_ID', '=', qkb_category_id)], limit=1)
        if category:
            return category

        parent_category = False
        parent_ref = category_data.get('ParentRef')
        if parent_ref:
            parent_category = ProductCategory.search([('qkca_category_ID', '=', parent_ref.get('value'))], limit=1)
            if not parent_category:
                parent_category = self._prepare_category_creation({'Id': parent_ref.get('value'),
                    'Name': parent_ref.get('name'),})

        category_vals = {
            'name': qkb_category_name,
            'qkca_category_ID': qkb_category_id,
            'parent_id': parent_category.id if parent_category else False,\
            'qck_instance_id':self.quickbook_instance_id.id if self.quickbook_instance_id else False,
        }
        category = ProductCategory.create(category_vals)

        return category


    def get_category_from_quickbooks(self, category_info, category_status):

        if category_status == 200 and category_info and 'QueryResponse' in category_info:
            category_items = category_info['QueryResponse'].get('Item', [])
            instance_id = getattr(self.quickbook_instance_id, 'id', False)
            company_id = self.quickbook_instance_id.company_id.id if self.quickbook_instance_id.company_id else self.env.company.id

            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(
                quickbooks_operation_name='product_category',quickbooks_operation_type='import',
                instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='QuickBooks to fetch Categories')

            quickbook_map_category, quickbook_map_category_log_ln = [], []

            for category in category_items:
                qkb_category_name = (category.get('Name') or '').strip()
                qkb_category_id = category.get('Id')

                category_detail = False
                if qkb_category_name:
                    category_detail = self.env['product.category'].sudo().search([
                        '|', ('name', '=', qkb_category_name), ('qkca_category_ID', '=', qkb_category_id)
                    ], limit=1)

                cat_created = False
                if not category_detail and self.quickbook_instance_id.qkca_category_creation:
                    category_detail = self._prepare_category_creation(category)
                    cat_created = True

                category_mapping = self.env['qbo.category.ca.map.vts'].sudo().search([('quickbook_category_id', '=', qkb_category_id)], limit=1)
                qbo_response = pprint.pformat(category)

                if not category_mapping:

                    mapping_vals = {
                        'quickbook_instance_id': instance_id,'quickbook_category_id': qkb_category_id,
                        'quickbook_category_name': qkb_category_name,'category_id': getattr(category_detail, 'id', False),
                        'company_id': company_id,'qbo_response': qbo_response}
                    quickbook_map_category.append(mapping_vals)

                    if not category_detail:
                        log_message = f"Category doesn't match with QuickBooks Category: {qkb_category_name}"
                        fault = True
                    else:
                        log_message = f"{'Category successfully created and ' if cat_created else ''}mapped with QuickBooks category: {qkb_category_name}"
                        category_detail.write({
                            'qck_instance_id': instance_id,
                            'qkca_category_ID': qkb_category_id})
                        fault = False

                    quickbook_map_category_log_ln.append({'quickbooks_operation_name': 'product_category',
                        'quickbooks_operation_type': 'import','qkb_instance_id': instance_id,
                        'quickbooks_operation_message': log_message,'process_response_message': qbo_response,
                        'quickbooks_operation_id': log_id.id if log_id else False,'fault_operation': fault})

                else:

                    if category_detail and qkb_category_id:
                        category_detail.write({
                            'qkca_category_ID': qkb_category_id,
                            'qck_instance_id': instance_id})

                    category_mapping.sudo().write({
                        'category_id': getattr(category_detail, 'id', False),'quickbook_instance_id': instance_id,
                        'qbo_response': qbo_response})

                    quickbook_map_category_log_ln.append({'quickbooks_operation_name': 'product_category',
                        'quickbooks_operation_type': 'import','qkb_instance_id': instance_id,
                        'quickbooks_operation_message': f"Category updated with QuickBooks category: {qkb_category_name}",
                        'process_response_message': qbo_response,
                        'quickbooks_operation_id': log_id.id if log_id else False})

            if quickbook_map_category:
                self.env['qbo.category.ca.map.vts'].sudo().create(quickbook_map_category)
            if quickbook_map_category_log_ln:
                self.env['quickbooks.log.vts.line'].sudo().create(quickbook_map_category_log_ln)

        else:
            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(
                quickbooks_operation_name='product_category',quickbooks_operation_type='import',
                instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Failed to fetch Categories')

            self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                quickbooks_operation_name='product_category',quickbooks_operation_type='import',
                instance=self.quickbook_instance_id.id if self.quickbook_instance_id else False,
                quickbooks_operation_message='Error during categories import process',
                process_response_message=pprint.pformat(category_info),log_id=log_id,fault_operation=True)


    def execute_process_of_quickbooks(self):
        res = super(QuickbooksWizardInherit, self).execute_process_of_quickbooks()
        if self.quickbook_instance_id and self.quickbook_instance_id.access_token:
            qck_url = self.quickbook_instance_id.quickbook_base_url
            company_id = self.quickbook_instance_id.realm_id
            token = self.quickbook_instance_id.access_token
            from_date = self.from_date.strftime('%Y-%m-%dT%H:%M:%S-07:00') if self.from_date else None
            to_date = self.to_date.strftime('%Y-%m-%dT%H:%M:%S-07:00') if self.to_date else None

            if self.import_operations == 'import_ca_product':
                product_info, product_status = self.env['quickbooks.api.vts'].sudo().get_data_from_quickbooks(qck_url,
                    company_id,token, self.import_operations, from_date=from_date, to_date=to_date)

                qk_product_details = self.get_ca_product_from_quickbooks(product_info, product_status)

            if self.import_operations == 'import_vendor':
                vendor_info, vendor_status = self.env['quickbooks.api.vts'].sudo().get_data_from_quickbooks(qck_url,
                    company_id,token, self.import_operations, from_date=from_date, to_date=to_date)

                qk_vendor_details = self.get_vendor_from_quickbooks(vendor_info, vendor_status)

            if self.import_operations == 'import_pro_category':
                category_info, category_status = self.env['quickbooks.api.vts'].sudo().get_data_from_quickbooks(qck_url,
                    company_id,token, self.import_operations, from_date=from_date, to_date=to_date)

                qk_category_details = self.get_category_from_quickbooks(category_info, category_status)

        return res