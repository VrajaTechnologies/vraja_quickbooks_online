# -*- coding: utf-8 -*-
from odoo import models, fields
import requests
import logging

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    qbk_vendor_id = fields.Char("QuickBooks Vendor ID")
    error_in_export = fields.Boolean("Error in QuickBooks Export", default=False)

    def export_customer_to_quickbooks(self):
        for partner in self:
            roles = []
            if partner.customer_rank > 0:
                roles.append(("customer", "qbk_id"))
            if partner.supplier_rank > 0:
                roles.append(("vendor", "qbk_vendor_id"))

            if not roles:
                partner.message_post(body=f"{partner.name} is neither customer nor vendor.")
                continue

            for endpoint, qbk_field in roles:
                existing_id = getattr(partner, qbk_field)

                if existing_id:
                    msg_body = f"{partner.name} already exists in QuickBooks as {endpoint} with ID: {existing_id}."
                    partner.message_post(body=msg_body)
                    continue

                self._export_to_quickbooks(partner, endpoint, qbk_field)

    def _export_to_quickbooks(self, partner, endpoint, qbk_field):
        company = partner.company_id.id if partner.company_id else self.env.company.id
        quickbook_instance = self.env['quickbooks.connect'].sudo().search([('company_id', '=', company)], limit=1)

        if quickbook_instance:
            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(quickbooks_operation_name=endpoint,
                quickbooks_operation_type="export",instance=quickbook_instance.id,
                quickbooks_operation_message=f"Starting export for {partner.name}")

            display_name = f"{partner.name} ({endpoint.capitalize()})"

            bill_addr = {
                "Line1": partner.street,
                "Line2": partner.street2,
                "City": partner.city,
                "CountrySubDivisionCode": partner.state_id.code if partner.state_id else '',
                "PostalCode": partner.zip,
                "Country": partner.country_id.code if partner.country_id else ''}

            url = f"{quickbook_instance.quickbook_base_url}/{quickbook_instance.realm_id}/{endpoint}"
            headers = {
                        "Authorization": f"Bearer {quickbook_instance.access_token}",
                        "Accept": "application/xml",
                        "Content-Type": "application/json",
                        "Accept-Encoding": "identity"
                    }
            data = {
                "DisplayName": display_name,
                "GivenName": partner.name,
                "CompanyName": partner.parent_id.name or '',
                "PrimaryPhone": {"FreeFormNumber": partner.phone or ""},
                "PrimaryEmailAddr": {"Address": partner.email or ""},
                "Mobile": {"FreeFormNumber": partner.mobile or ""},
                "BillAddr": bill_addr,
            }

            try:
                response = requests.post(url, json=data, headers=headers)

                response_json = quickbook_instance.convert_xmltodict(response.text)
                
                if response.status_code == 200:
                    result = response_json
                    customer_data = result.get("IntuitResponse", {}).get(endpoint.capitalize(), {})
                    qbk_id = customer_data.get("Id")
                    
                    setattr(partner, qbk_field, qbk_id)

                    partner.message_post(body=f"Exported {partner.name} to QuickBooks as {endpoint}, ID: {qbk_id}")
                    self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name=endpoint,
                    quickbooks_operation_type="export",instance=quickbook_instance.id,
                    quickbooks_operation_message=f"Successfully Exported {partner.name}",process_request_message=data,
                    process_response_message=response_json,log_id=log_id)
                else:
                    partner.error_in_export = True
                    error_msg = response_json
                    if response_json.get('IntuitResponse'):
                        error_msg = response_json['IntuitResponse']['Fault']['Error']['Message']
                    partner.message_post(body=f"Failed to export {partner.name} to QuickBooks ({endpoint}). Response: {error_msg}")
                    self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name=endpoint,
                    quickbooks_operation_type="export",instance=quickbook_instance.id,
                    quickbooks_operation_message=f"Export {partner.name} Failed",process_request_message=data,
                    process_response_message=response_json,log_id=log_id,fault_operation=True)
            except Exception as e:
                partner.error_in_export = True
                partner.message_post(body=f"Exception while exporting {partner.name} to QuickBooks: {str(e)}")
                self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name=endpoint,quickbooks_operation_type="export",
                    instance=quickbook_instance.id,quickbooks_operation_message=f"Exception in {partner.name}",
                    process_request_message=data,process_response_message=str(e),
                    log_id=log_id,fault_operation=True)

        else:
            partner.message_post(body=f"No QuickBooks instance configured for {company} company.")