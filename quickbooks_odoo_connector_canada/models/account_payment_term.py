# -*- coding: utf-8 *-*
from odoo import models, fields, api


class AccountPayment(models.Model):
    _inherit = "account.payment.term"

    is_export_error = fields.Boolean("Error in QuickBooks Export", default=False)
    is_payment_term_qbca_exported = fields.Boolean(string="Exported Payment Term", default=False)

    def _prepare_qkca_payment_term_vals(self, payment):
        payment_term_payload={
                "DueDays": payment.line_ids[0].nb_days if payment.line_ids else 0,
                "Name": payment.name,
                "DiscountPercent" :payment.line_ids[0].value_amount if payment.line_ids else 0
        }

        return payment_term_payload,"term"


    def export_payment_term_to_qkca(self):
        for payment in self:
            if payment.qck_payment_terms_ID:
                return

            company = payment.company_id.id if payment.company_id else False
            quickbook_instance = self.env['quickbooks.connect'].sudo().search([('state', '=', 'connected'),('company_id', '=', company)], limit=1)

            if not quickbook_instance:
                return

            log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(
                quickbooks_operation_name="payment_term", quickbooks_operation_type="export",
                instance=quickbook_instance.id,
                quickbooks_operation_message=f"Starting export for Payment Term {payment.name}"
            )

            payment_term_payload, endpoint = self._prepare_qkca_payment_term_vals(payment)

            try:
                payment_term_url = f"{quickbook_instance.quickbook_base_url}/{quickbook_instance.realm_id}/{endpoint}"

                response_json, status_code = self.env['quickbooks.api.vts'].sudo().qb_post_request(
                    quickbook_instance.access_token, payment_term_url, payment_term_payload)

                if status_code == 200:
                    payment_data = response_json.get("Term", {})
                    qk_payment_id = payment_data.get("Id")
                    payment.qck_payment_terms_ID = qk_payment_id
                    payment.is_export_error = False
                    payment.is_payment_term_qbca_exported = True
                    # payment.message_post(body=f"Exported Payment Term {payment.name} to QuickBooks, ID: {qk_payment_id}")
                    self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                        quickbooks_operation_name="payment_term", quickbooks_operation_type="export",
                        instance=quickbook_instance.id,
                        quickbooks_operation_message=f"Successfully exported Payment {payment.name}",
                        process_request_message=payment_term_payload, process_response_message=response_json,
                        log_id=log_id)
                    return response_json
                else:
                    msg = f"Failed to export Payment Term {payment.name} to QuickBooks. Response: {response_json}"
                    # payment.message_post(body=msg)
                    payment.is_export_error = True
                    self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                        quickbooks_operation_name="payment_term", quickbooks_operation_type="export",
                        instance=quickbook_instance.id, quickbooks_operation_message=msg,
                        process_request_message=payment_term_payload, process_response_message=response_json,
                        log_id=log_id, fault_operation=True)
                    return None

            except Exception as e:
                payment.is_export_error = True
                self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                    quickbooks_operation_name="payment_term", quickbooks_operation_type="export",
                    instance=quickbook_instance.id, quickbooks_operation_message=f"Exception: {str(e)}",
                    process_request_message=payment_term_payload, process_response_message=str(e),
                    log_id=log_id, fault_operation=True)
                return None



