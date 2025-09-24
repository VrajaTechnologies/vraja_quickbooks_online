import requests
import json
from odoo import models, fields

class AccountMove(models.Model):

	_inherit = "account.move"

	qbk_invoice_id = fields.Char("QuickBooks Invoice ID",copy=False)
	error_in_export = fields.Boolean("Error in QuickBooks Export", default=False)

	def _prepare_qbo_invoice_vals(self, invoice, quickbook_instance, log_id):
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

		line_number = 1
		qbk_tax_code = None

		for line in invoice.invoice_line_ids:

			if not line.product_id.qkb_product_ID:
				msg = f"Product {line.product_id.name} not mapped with QuickBooks."
				invoice.message_post(body=msg)
				self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
					quickbooks_operation_name="invoice",quickbooks_operation_type="export",
					instance=quickbook_instance.id,quickbooks_operation_message=msg,
					process_request_message={},process_response_message={},
					log_id=log_id,fault_operation=True)
				continue

			tax_value = "NON"
			if line.tax_ids:
				if line.tax_ids[0].amount > 0:
					tax_value = "TAX"
				else:
					tax_value = "NON"

				if not qbk_tax_code and line.tax_ids[0].qck_taxes_ID:
					qbk_tax_code = line.tax_ids[0].qck_taxes_ID
					tax_value = "TAX"

			qbo_invoice_val["Line"].append({
				"Description": line.name,
				"Amount": float(line.price_subtotal),
				"DetailType": "SalesItemLineDetail",
				"LineNum": line_number,
				"SalesItemLineDetail": {
					"ItemRef": {
						"value": line.product_id.qkb_product_ID,
						"name": line.product_id.name,
					},
					"Qty": line.quantity,
					"UnitPrice": float(line.price_unit),
					"TaxCodeRef": {"value": tax_value}
				}
			})
			line_number += 1

		if qbk_tax_code:
		    qbo_invoice_val["TxnTaxDetail"] = {"TxnTaxCodeRef": {"value": qbk_tax_code}}

		return qbo_invoice_val

	def export_invoice_quickbooks(self, invoice):
		if invoice.state != 'posted':
			return

		if invoice.qbk_invoice_id:
			invoice.message_post(body=f"Invoice already exported to QuickBooks with ID {invoice.qbk_invoice_id}.")
			return

		company = invoice.company_id.id if invoice.company_id else False
		quickbook_instance = self.env['quickbooks.connect'].sudo().search([('company_id', '=', company)], limit=1)

		if not quickbook_instance:
			invoice.message_post(body=f"No QuickBooks instance configured for {company} company.")
			return

		log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(
			quickbooks_operation_name="invoice",
			quickbooks_operation_type="export",
			instance=quickbook_instance.id,
			quickbooks_operation_message=f"Starting export for Invoice {invoice.name}")

		try:
			if not invoice.partner_id.qbk_id:
				msg = f"Customer {invoice.partner_id.name} not mapped with QuickBooks."
				invoice.message_post(body=msg)
				invoice.error_in_export = True
				self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name="invoice",
					quickbooks_operation_type="export",instance=quickbook_instance.id,
					quickbooks_operation_message=msg,process_request_message={},
					process_response_message={},log_id=log_id,fault_operation=True)
				return

			qbo_invoice_val = self._prepare_qbo_invoice_vals(invoice, quickbook_instance, log_id)

			inv_url = f"{quickbook_instance.quickbook_base_url}/{quickbook_instance.realm_id}/invoice"

			response_json, status_code = self.env['quickbooks.api.vts'].sudo().qb_post_request(quickbook_instance.access_token,
    			inv_url,qbo_invoice_val)

			if status_code in (200, 201):
				invoice_data = response_json.get("Invoice", {})
				qbk_inv_id = invoice_data.get("Id")
				invoice.qbk_invoice_id = qbk_inv_id
				invoice.message_post(body=f"Exported Invoice {invoice.name} to QuickBooks, ID: {qbk_inv_id}")
				self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
					quickbooks_operation_name="invoice",quickbooks_operation_type="export",
					instance=quickbook_instance.id,quickbooks_operation_message=f"Successfully exported invoice {invoice.name}",
					process_request_message=qbo_invoice_val,process_response_message=response_json,
					log_id=log_id)
				return response_json
			else:

				msg = f"Failed to export Invoice {invoice.name} to QuickBooks. Response: {response_json}"
				invoice.message_post(body=msg)
				invoice.error_in_export = True
				self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name="invoice",
					quickbooks_operation_type="export",instance=quickbook_instance.id,
					quickbooks_operation_message=msg,process_request_message=qbo_invoice_val,
					process_response_message=response_json,log_id=log_id,
					fault_operation=True)
				return None

		except Exception as e:
			invoice.message_post(body=f"Exception while exporting Invoice {invoice.name} to QuickBooks: {str(e)}")
			invoice.error_in_export = True
			self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name="invoice",
				quickbooks_operation_type="export",instance=quickbook_instance.id,
				quickbooks_operation_message=f"Exception: {str(e)}",process_request_message={},process_response_message=str(e),
				log_id=log_id,fault_operation=True)
			return None

	def export_vendor_bill_quickbooks(self, move):
		print('Bill')

	def export_invoice_bill_to_quickbooks(self):
		for move in self:
			if move.move_type == 'out_invoice':
				invoice = self.export_invoice_quickbooks(move)
			elif move.move_type == 'in_invoice':
				vendor_bill = self.export_vendor_bill_quickbooks(move)