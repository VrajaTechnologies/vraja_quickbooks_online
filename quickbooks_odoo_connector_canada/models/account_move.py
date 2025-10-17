# -*- coding: utf-8 *-*
from odoo import models, fields, api
from odoo.release import product_name

TAX_INCLUDED = 'TaxInclusive'
TAX_EXCLUDED = 'TaxExcluded'


class AccountMove(models.Model):
    
    _inherit = "account.move"

    qck_instance_id = fields.Many2one('quickbooks.connect', string="Quickbook Instance", copy=False)
    qkca_invoice_ID = fields.Char(string="Quickbook Invoice ID",copy=False)
    qck_invoice_doc = fields.Char(string="Quickbook Doc-Number",copy=False)
    is_export_error = fields.Boolean(string="Error in QuickBooks Export", default=False)
    is_inv_qkca_exported = fields.Boolean(string="Is Invoice Exported", default=False, copy=False)
    # is_bill_qkca_exported =fields.Boolean("Is Bill Exported")
    qck_bill_doc = fields.Char(string="Quickbook Bill Doc-Number")
    qkca_bill_ID = fields.Char(string="Quickbook Bill ID",copy=False)

    def _prepare_qkca_invoice_vals(self, invoice, quickbook_instance):
        qbo_invoice_val = {
                "TxnDate": str(invoice.invoice_date),
                "DocNumber": invoice.name,
                "CustomerRef": {
                    "value": invoice.partner_id.qbk_id,
                    "name": invoice.partner_id.name,
                },
                "SalesTermRef": {
                    "value": invoice.invoice_payment_term_id.qck_payment_terms_ID if invoice.invoice_payment_term_id else '',
                },
                "Line": [],
                "TotalAmt": float(invoice.amount_total),
                "Balance": float(invoice.amount_residual),
            }

        if quickbook_instance.country_id and quickbook_instance.country_id.code == "CA":
            qbo_invoice_val["GlobalTaxCalculation"] = "TaxExcluded"
        else:
            qbo_invoice_val["GlobalTaxCalculation"] = TAX_INCLUDED if quickbook_instance.company_included_tax else TAX_EXCLUDED

        line_number = 1
        qbk_tax_code = None

        for line in invoice.invoice_line_ids:
            tax_value = "NON"
            if line.tax_ids:
                if line.tax_ids[0].qck_taxes_ID:
                    tax_value = line.tax_ids[0].qck_taxes_ID

                    if not qbk_tax_code:
                        qbk_tax_code = tax_value

                elif line.tax_ids[0].amount > 0:
                    tax_value = "TAX"
                else:
                    tax_value = "NON"

            if qbo_invoice_val["GlobalTaxCalculation"] == "TaxIncluded":
                line_amount = float(line.price_total)
            else:
                line_amount = float(line.price_subtotal)

            qbo_invoice_val["Line"].append({
                "Description": line.name,
                "Amount": line_amount,
                "DetailType": "SalesItemLineDetail",
                "LineNum": line_number,
                "SalesItemLineDetail": {
                    "Qty": line.quantity,
                    "UnitPrice": float(line.price_unit),
                    "TaxCodeRef": {"value": tax_value},
                }
            })
            line_number += 1

        if qbk_tax_code:
            qbo_invoice_val["TxnTaxDetail"] = {"TxnTaxCodeRef": {"value": qbk_tax_code}}

        return qbo_invoice_val

    def export_invoice_to_quickbooks_ca(self, invoice):
        if invoice.state != 'posted':
            return

        if invoice.qkca_invoice_ID:
            invoice.message_post(body=f"Invoice already exported to QuickBooks with ID {invoice.qkca_invoice_ID}.")
            return

        company = invoice.company_id.id if invoice.company_id else False
        quickbook_instance = self.env['quickbooks.connect'].sudo().search([('state', '=', 'connected'), ('company_id', '=', company)], limit=1)

        if not quickbook_instance:
            invoice.message_post(body=f"No QuickBooks instance configured for {company} company.")
            return

        log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(
            quickbooks_operation_name="invoice", quickbooks_operation_type="export",
            instance=quickbook_instance.id, quickbooks_operation_message=f"Starting export for Invoice {invoice.name}")

        if not invoice.partner_id.qbk_id:
            qbk_id = invoice.partner_id.export_to_quickbooks_ca(invoice.partner_id, 'customer', 'qbk_id')
            if invoice.partner_id.qbk_id:
                msg = f"Customer {invoice.partner_id.name} Created into QuickBooks, ID: {invoice.partner_id.qbk_id}"
                invoice.message_post(body=msg)
            else:
                msg = qbk_id
                invoice.message_post(body=msg)
                invoice.is_export_error = True
                self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                    quickbooks_operation_name="invoice",
                    quickbooks_operation_type="export", instance=quickbook_instance.id,
                    quickbooks_operation_message=msg, process_request_message={},
                    process_response_message={}, log_id=log_id, fault_operation=True)
                return

        try:
            qbo_invoice_val = self._prepare_qkca_invoice_vals(invoice, quickbook_instance)

            inv_url = f"{quickbook_instance.quickbook_base_url}/{quickbook_instance.realm_id}/invoice"

            response_json, status_code = self.env['quickbooks.api.vts'].sudo().qb_post_request(
                quickbook_instance.access_token,
                inv_url, qbo_invoice_val)

            if status_code in (200, 201):
                invoice_data = response_json.get("Invoice", {})
                qbk_inv_id = invoice_data.get("Id")
                invoice.qkca_invoice_ID = qbk_inv_id
                invoice.is_export_error = False
                invoice.is_inv_qkca_exported = True
                invoice.message_post(body=f"Exported Invoice {invoice.name} to QuickBooks, ID: {qbk_inv_id}")
                self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                    quickbooks_operation_name="invoice", quickbooks_operation_type="export",
                    instance=quickbook_instance.id,
                    quickbooks_operation_message=f"Successfully exported invoice {invoice.name}",
                    process_request_message=qbo_invoice_val, process_response_message=response_json,
                    log_id=log_id)
                return response_json
            else:

                msg = f"Failed to export Invoice {invoice.name} to QuickBooks. Response: {response_json}"
                invoice.message_post(body=msg)
                invoice.is_export_error = True
                self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                    quickbooks_operation_name="invoice",
                    quickbooks_operation_type="export", instance=quickbook_instance.id,
                    quickbooks_operation_message=msg, process_request_message=qbo_invoice_val,
                    process_response_message=response_json, log_id=log_id,
                    fault_operation=True)
                return None

        except Exception as e:
            invoice.message_post(body=f"Exception while exporting Invoice {invoice.name} to QuickBooks: {str(e)}")
            invoice.is_export_error = True
            self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
                quickbooks_operation_name="invoice",
                quickbooks_operation_type="export", instance=quickbook_instance.id,
                quickbooks_operation_message=f"Exception: {str(e)}", process_request_message=qbo_invoice_val,
                process_response_message=str(e),
                log_id=log_id, fault_operation=True)
            return None

    def export_bill_to_quickbook_ca(self,move):
        print('Yaxit')

    def export_invoice_and_bill_to_quickbooks_ca(self):
        for move in self:
            if move.move_type == 'out_invoice':
                invoice = self.export_invoice_to_quickbooks_ca(move)
            elif move.move_type == 'in_invoice':
                vendor_bill = self.export_bill_to_quickbook_ca(move)
