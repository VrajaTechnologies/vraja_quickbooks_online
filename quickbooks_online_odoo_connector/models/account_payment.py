# -*- coding: utf-8 -*-
import requests
import json
import logging
from odoo import models, fields, _

_logger = logging.getLogger(__name__)

class AccountPayment(models.Model):
    _inherit = "account.payment"

    qk_bill_payment_ID = fields.Char(string="QuickBooks Bill Payment ID")
    qk_payment_ID = fields.Char(string="QuickBooks Payment ID")
    error_in_export = fields.Boolean(string="Error In Export")
    is_inv_pay_exported = fields.Boolean(string="Is Invoice Payment Exported", default=False)
    is_bill_pay_exported = fields.Boolean(string="Is Bill Payment Exported", default=False)

    def write(self, vals):
        res = super(AccountPayment, self).write(vals)

        payment_type_map = {'inbound': {'qbk_id_field': 'qk_payment_ID', 'url_endpoint': 'payment'},
                            'outbound': {'qbk_id_field': 'qk_bill_payment_ID', 'url_endpoint': 'billpayment'}}

        for payment in self:
            payment_type_info = payment_type_map.get(payment.payment_type)
            if not payment_type_info:
                continue

            qbk_id = getattr(payment, payment_type_info['qbk_id_field'], None)
            if not qbk_id:
                continue

            company = payment.company_id.id if payment.company_id else False
            quickbook_instance = self.env['quickbooks.connect'].sudo().search([('company_id', '=', company),('state','=','connected')], limit=1)

            if not (quickbook_instance and quickbook_instance.access_token and quickbook_instance.realm_id):
                payment.message_post(body="QuickBooks Payment Update Failed: Authentication required")
                continue

            try:
                headers = {"Authorization": f"Bearer {quickbook_instance.access_token}",
                            "Content-Type": "application/json",
                            "Accept-Encoding": "identity",}

                payment_account = payment.journal_id.default_account_id

                if payment.payment_type == 'inbound':
                    payment_payload, endpoint = self._prepare_payment_payload(payment)
                else:
                    if payment_account and not payment_account.quickbooks_id:
                        payment.message_post(body=f"Account {payment_account.display_name} not mapped with QuickBooks.")
                        continue

                    payment_payload, endpoint = self._prepare_billpayment_payload(payment, payment_account)

                url_get = f"{quickbook_instance.quickbook_base_url}/{quickbook_instance.realm_id}/{payment_type_info['url_endpoint']}/{qbk_id}"
                response_get = requests.get(url_get, headers=headers)
                response_get.raise_for_status()

                response_data = quickbook_instance.convert_xmltodict(response_get.text).get("IntuitResponse", {})
                existing_payment = response_data.get('BillPayment' if payment.payment_type == 'outbound' else 'Payment', {}) or {}
                sync_token = existing_payment.get("SyncToken", "0")

                payment_payload.update({"Id": qbk_id, "SyncToken": sync_token})

                parsed_dict = json.dumps(payment_payload)
                _logger.info("Export Update Dict for Payment %s: %s", payment.name, parsed_dict)
                
                url_update = f"{quickbook_instance.quickbook_base_url}/{quickbook_instance.realm_id}/{payment_type_info['url_endpoint']}"
                result = requests.post(url_update, headers=headers, data=parsed_dict)
                update_result_res = quickbook_instance.convert_xmltodict(result.text)

                if result.ok:
                    payment.message_post(body=f"{payment.name} updated successfully to QuickBooks")
                else:
                    fault = update_result_res.get("IntuitResponse", {}).get("Fault", {})
                    error = fault.get("Error", {})
                    combined_msg = error.get("Message", "")
                    if error.get("Detail"):
                        combined_msg += f": {error.get('Detail')}"
                    payment.message_post(body=f"Payment Update Error: {combined_msg}")

            except requests.exceptions.RequestException as req_err:
                payment.message_post(body=f"Request error while updating {payment.name}: {req_err}")
            except Exception as e:
                payment.message_post(body=f"Unexpected error while updating {payment.name}: {e}")

        return res

    def _prepare_billpayment_payload(self, payment, payment_account):

        bill_payment_payload = {"DocNumber": payment.name,
                "VendorRef": {"value": payment.partner_id.qbk_vendor_id or "",
                            "name": payment.partner_id.name},
                "PayType": "CreditCard" if payment.payment_method_line_id.payment_method_id.code == "credit" else "Check",
                "TxnDate": str(payment.date),
                "TotalAmt": payment.amount,
                "PrivateNote": payment.memo or "",
                "Line":[]}

        for bill in self.reconciled_bill_ids.sudo().filtered(lambda inv: inv.move_type == "in_invoice"):
            bill_val = {
                    "Amount": bill.amount_total,
                    "LinkedTxn": [{"TxnId": str(bill.qbk_bill_id or ""),
                                "TxnType": "Bill"}]}

            bill_payment_payload['Line'].append(bill_val)

        if payment.payment_method_line_id.payment_method_id.code == 'credit':
            bill_payment_payload.update({
                        "CreditCardPayment": {
                            "CCAccountRef": {
                                "name": payment_account.name,
                                "value": payment_account.quickbooks_id}}})
        else:
            bill_payment_payload.update({
                        "CheckPayment": {
                            "BankAccountRef": {
                                "name": payment_account.name,
                                "value": payment_account.quickbooks_id}}})

        return bill_payment_payload, "billpayment"

    def export_bill_payment_qbo(self, payment):
        if payment.qk_bill_payment_ID:
            payment.message_post(body=f"Bill Payment already exported to QuickBooks with ID {payment.qk_bill_payment_ID}.")
            return

        company = payment.company_id.id if payment.company_id else False
        quickbook_instance = self.env['quickbooks.connect'].sudo().search([('state','=','connected'),('company_id', '=', company)], limit=1)

        if not quickbook_instance:
            payment.message_post(body=f"No QuickBooks instance configured for {company} company.")
            return

        log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(quickbooks_operation_name="billpayment",
            quickbooks_operation_type="export",instance=quickbook_instance.id,
            quickbooks_operation_message=f"Starting export for Bill Payment {payment.name}")

        if not payment.partner_id.qbk_vendor_id:
            qbk_vendor_id = payment.partner_id._export_to_quickbooks(payment.partner_id, 'vendor', 'qbk_vendor_id')
            if payment.partner_id.qbk_vendor_id:
                msg = f"Vendor {payment.partner_id.name} Created into QuickBooks."
                payment.message_post(body=msg)
            else:
                msg = qbk_vendor_id
                payment.message_post(body=msg)
                payment.error_in_export = True
                self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name="billpayment",
                    quickbooks_operation_type="export",instance=quickbook_instance.id,
                    quickbooks_operation_message=msg,process_request_message={},
                    process_response_message={},log_id=log_id,fault_operation=True)
                return

        payment_account = payment.journal_id.default_account_id


        if payment_account and not payment_account.quickbooks_id:
            msg = f"Account {payment_account.display_name} not mapped with QuickBooks."
            payment.message_post(body=msg)
            self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                quickbooks_operation_name="invoice",quickbooks_operation_type="export",
                instance=quickbook_instance.id,quickbooks_operation_message=msg,
                process_request_message={},process_response_message={},
                log_id=log_id,fault_operation=True)
            return

        bill_payment_payload, endpoint = self._prepare_billpayment_payload(payment, payment_account)
        
        try:

            billp_url = f"{quickbook_instance.quickbook_base_url}/{quickbook_instance.realm_id}/{endpoint}"

            response_json, status_code = self.env['quickbooks.api.vts'].sudo().qb_post_request(
                quickbook_instance.access_token, billp_url, bill_payment_payload)

            if status_code == 200:
                billp_data = response_json.get("BillPayment", {})
                qbk_bp_id = billp_data.get("Id")
                payment.qk_bill_payment_ID = qbk_bp_id
                payment.error_in_export = False
                payment.is_bill_pay_exported = True
                payment.message_post(body=f"Exported Bill Payment {payment.name} to QuickBooks, ID: {qbk_bp_id}")
                self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                    quickbooks_operation_name="billpayment",quickbooks_operation_type="export",
                    instance=quickbook_instance.id,quickbooks_operation_message=f"Successfully exported Bill Payment {payment.name}",
                    process_request_message=bill_payment_payload,process_response_message=response_json,log_id=log_id)
                return response_json
            else:
                msg = f"Failed to export Bill Payment {payment.name} to QuickBooks. Response: {response_json}"
                payment.message_post(body=msg)
                payment.error_in_export = True
                self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                    quickbooks_operation_name="billpayment",quickbooks_operation_type="export",
                    instance=quickbook_instance.id,quickbooks_operation_message=msg,
                    process_request_message=bill_payment_payload,process_response_message=response_json,
                    log_id=log_id,fault_operation=True)
                return None

        except Exception as e:
            payment.message_post(body=f"Exception while exporting Bill Payment {payment.name} to QuickBooks: {str(e)}")
            payment.error_in_export = True
            self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                quickbooks_operation_name="billpayment",quickbooks_operation_type="export",
                instance=quickbook_instance.id,quickbooks_operation_message=f"Exception: {str(e)}",
                process_request_message=bill_payment_payload,process_response_message=str(e),
                log_id=log_id,fault_operation=True)
            
            return None

    def _prepare_payment_payload(self, payment):

        payment_payload = {
            "CustomerRef": {
                "value": payment.partner_id.qbk_id or "",
                "name": payment.partner_id.name
            },
            "PaymentRefNum": payment.name,
            "TotalAmt": payment.amount,
            "TxnDate": str(payment.date),
            "PrivateNote": payment.memo or "",
            "Line": []
        }

        for inv in payment.reconciled_invoice_ids.filtered(lambda m: m.move_type == 'out_invoice'):
            if inv.qbk_invoice_id:
                line_val = {
                    "Amount": inv.amount_residual if payment.amount != inv.amount_total else inv.amount_total,
                    "LinkedTxn": [{
                        "TxnId": str(inv.qbk_invoice_id),
                        "TxnType": "Invoice"
                    }]
                }
                payment_payload["Line"].append(line_val)

        payment_account = payment.journal_id.default_account_id
        if payment_account and payment_account.quickbooks_id:
            payment_payload["DepositToAccountRef"] = {
                "value": payment_account.quickbooks_id,
                "name": payment_account.name}

        return payment_payload, "payment"

    def export_payment_qbo(self, payment):

        if payment.qk_payment_ID:
            payment.message_post(body=f"Payment already exported to QuickBooks with ID {payment.qk_payment_ID}.")
            return

        company = payment.company_id.id if payment.company_id else False
        quickbook_instance = self.env['quickbooks.connect'].sudo().search([('company_id', '=', company)], limit=1)

        if not quickbook_instance:
            payment.message_post(body=f"No QuickBooks instance configured for {company} company.")
            return

        log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(
            quickbooks_operation_name="payment",quickbooks_operation_type="export",
            instance=quickbook_instance.id,quickbooks_operation_message=f"Starting export for Payment {payment.name}"
        )

        if not payment.partner_id.qbk_id:
            qbk_id = payment.partner_id._export_to_quickbooks(payment.partner_id, 'customer', 'qbk_id')
            if payment.partner_id.qbk_id:
                msg = f"Customer {payment.partner_id.name} Created into QuickBooks."
                payment.message_post(body=msg)
            else:
                msg = qbk_id
                payment.message_post(body=msg)
                payment.error_in_export = True
                self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name="payment",
                    quickbooks_operation_type="export",instance=quickbook_instance.id,
                    quickbooks_operation_message=msg,process_request_message={},
                    process_response_message={},log_id=log_id,fault_operation=True)
                return

        payment_payload, endpoint = self._prepare_payment_payload(payment)

        try:
            payment_url = f"{quickbook_instance.quickbook_base_url}/{quickbook_instance.realm_id}/{endpoint}"

            response_json, status_code = self.env['quickbooks.api.vts'].sudo().qb_post_request(
                quickbook_instance.access_token, payment_url, payment_payload)

            if status_code == 200:
                payment_data = response_json.get("Payment", {})
                qk_payment_id = payment_data.get("Id")
                payment.qk_payment_ID = qk_payment_id
                payment.error_in_export = False
                payment.is_inv_pay_exported = True
                payment.message_post(body=f"Exported Payment {payment.name} to QuickBooks, ID: {qk_payment_id}")
                self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                    quickbooks_operation_name="payment",quickbooks_operation_type="export",
                    instance=quickbook_instance.id,quickbooks_operation_message=f"Successfully exported Payment {payment.name}",
                    process_request_message=payment_payload,process_response_message=response_json,
                    log_id=log_id)
                return response_json
            else:
                msg = f"Failed to export Payment {payment.name} to QuickBooks. Response: {response_json}"
                payment.message_post(body=msg)
                payment.error_in_export = True
                self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                    quickbooks_operation_name="payment",quickbooks_operation_type="export",
                    instance=quickbook_instance.id,quickbooks_operation_message=msg,
                    process_request_message=payment_payload,process_response_message=response_json,
                    log_id=log_id,fault_operation=True)
                return None

        except Exception as e:
            payment.message_post(body=f"Exception while exporting Payment {payment.name} to QuickBooks: {str(e)}")
            payment.error_in_export = True
            self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                quickbooks_operation_name="payment",quickbooks_operation_type="export",
                instance=quickbook_instance.id,quickbooks_operation_message=f"Exception: {str(e)}",
                process_request_message=payment_payload,process_response_message=str(e),
                log_id=log_id,fault_operation=True)
            return None

    def export_payment_to_quickbooks(self):
        for payment in self:
            if payment.payment_type == "outbound":
                export_bill_payment = self.export_bill_payment_qbo(payment)
            elif payment.payment_type == "inbound":
                export_payment = self.export_payment_qbo(payment)
            


