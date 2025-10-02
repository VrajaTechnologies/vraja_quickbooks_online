# -*- coding: utf-8 -*-
import requests
import json
import logging
from odoo import models, fields
_logger = logging.getLogger(__name__)

TAX_INCLUDED = 'TaxInclusive'
TAX_EXCLUDED = 'TaxExcluded'

class AccountMove(models.Model):

	_inherit = "account.move"

	qbk_invoice_id = fields.Char("QuickBooks Invoice ID",copy=False)
	qbk_bill_id = fields.Char("QuickBooks Bill ID",copy=False)
	error_in_export = fields.Boolean("Error in QuickBooks Export", default=False)
	is_inv_exported = fields.Boolean(string="Is Invoice Exported", default=False,copy=False)
	is_bill_exported = fields.Boolean(string="Is Vendor Bill Exported", default=False,copy=False)

	def write(self, vals):

	    res = super(AccountMove, self).write(vals)

	    for move in self:
	        if move.move_type in ('out_invoice'):
	            qbk_id_field = 'qbk_invoice_id'
	            prepare_method = '_prepare_qbo_invoice_vals'
	            url_endpoint = 'invoice'
	        elif move.move_type in ('in_invoice'):
	            qbk_id_field = 'qbk_bill_id'
	            prepare_method = '_prepare_qbo_vendor_bill_vals'
	            url_endpoint = 'bill'
	        else:
	            continue

	        qbk_id = getattr(move, qbk_id_field)
	        if not qbk_id:
	            continue

	        company = move.company_id.id if move.company_id else False
	        quickbook_instance = self.env['quickbooks.connect'].sudo().search([('state','=','connected'),('company_id', '=', company)], limit=1)

	        if not (quickbook_instance and quickbook_instance.access_token and quickbook_instance.realm_id):
	            move.message_post(body=f"QuickBooks Update Failed: Authentication required")
	            continue

	        try:
	            headers = {
	                "Authorization": f"Bearer {quickbook_instance.access_token}",
	                "Content-Type": "application/json",
	                "Accept-Encoding": "identity",
	            }

	            export_vals = getattr(move, prepare_method)(move, quickbook_instance)

	            url_get = f"{quickbook_instance.quickbook_base_url}/{quickbook_instance.realm_id}/{url_endpoint}/{qbk_id}"
	            response_get = requests.get(url_get, headers=headers)
	            response_get.raise_for_status()

	            response_data = quickbook_instance.convert_xmltodict(response_get.text)
	            existing_move = response_data.get("IntuitResponse", {}).get(url_endpoint.capitalize(), {}) or {}
	            sync_token = existing_move.get("SyncToken")

	            for addr_type in ("BillAddr", "ShipAddr"):
	                addr_id = existing_move.get(addr_type, {}).get("Id")
	                if addr_id:
	                    export_vals[addr_type] = {"Id": addr_id}

	            export_vals.update({
	                "Id": qbk_id,
	                "SyncToken": sync_token,
	            })

	            parsed_dict = json.dumps(export_vals)
	            _logger.info("Export Update Dict for %s %s: %s", move.move_type, move.name, parsed_dict)

	            url_update = f"{quickbook_instance.quickbook_base_url}/{quickbook_instance.realm_id}/{url_endpoint}"
	            result = requests.post(url_update, headers=headers, data=parsed_dict, timeout=30)

	            if result.ok:
	                decoded_update = result.text
	                quickbook_instance.convert_xmltodict(decoded_update)
	                move.message_post(body=f"{move.name} updated successfully to QuickBooks")
	            else:
	                msg = f"{result.status_code} - {result.content.decode(errors='ignore')}"
	                move.message_post(body=f"{move.move_type.capitalize()} Update Error: {msg}")

	        except requests.exceptions.RequestException as req_err:
	            move.message_post(body=f"Request error while updating {move.name}: {str(req_err)}")

	        except Exception as e:
	            move.message_post(body=f"Unexpected error while updating {move.name}: {str(e)}")

	    return res

	def _prepare_qbo_invoice_vals(self, invoice, quickbook_instance):
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

		if quickbook_instance.country_id and quickbook_instance.country_id.code == "US":
			qbo_invoice_val["GlobalTaxCalculation"] = TAX_EXCLUDED
		else:
			qbo_invoice_val["GlobalTaxCalculation"] = TAX_INCLUDED if quickbook_instance.company_include_tax else TAX_EXCLUDED

		line_number = 1
		qbk_tax_code = None

		for line in invoice.invoice_line_ids:

			tax_value = "NON"
			if line.tax_ids:
				if line.tax_ids[0].amount > 0:
					tax_value = "TAX"
				else:
					tax_value = "NON"

				if not qbk_tax_code and line.tax_ids[0].qck_taxes_ID:
					qbk_tax_code = line.tax_ids[0].qck_taxes_ID
					tax_value = "TAX"

			if qbo_invoice_val["GlobalTaxCalculation"] == TAX_INCLUDED:
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
					"TaxCodeRef": {"value": tax_value}
				}
			})
			line_number += 1

		if qbk_tax_code:
			qbo_invoice_val["TxnTaxDetail"] = {"TxnTaxCodeRef": {"value": qbk_tax_code}}

		return qbo_invoice_val

	# Export Invoice to QuickBooks
	def export_invoice_quickbooks(self, invoice):
		if invoice.state != 'posted':
			return

		if invoice.qbk_invoice_id:
			invoice.message_post(body=f"Invoice already exported to QuickBooks with ID {invoice.qbk_invoice_id}.")
			return

		company = invoice.company_id.id if invoice.company_id else False
		quickbook_instance = self.env['quickbooks.connect'].sudo().search([('state','=','connected'),('company_id', '=', company)], limit=1)

		if not quickbook_instance:
			invoice.message_post(body=f"No QuickBooks instance configured for {company} company.")
			return

		log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(
			quickbooks_operation_name="invoice",quickbooks_operation_type="export",
			instance=quickbook_instance.id,quickbooks_operation_message=f"Starting export for Invoice {invoice.name}")

		if not invoice.partner_id.qbk_id:
			qbk_id = invoice.partner_id._export_to_quickbooks(invoice.partner_id, 'customer', 'qbk_id')
			if invoice.partner_id.qbk_id:
				msg = f"Customer {invoice.partner_id.name} Created into QuickBooks."
				invoice.message_post(body=msg)
			else:
				msg = qbk_id
				invoice.message_post(body=msg)
				invoice.error_in_export = True
				self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name="invoice",
					quickbooks_operation_type="export",instance=quickbook_instance.id,
					quickbooks_operation_message=msg,process_request_message={},
					process_response_message={},log_id=log_id,fault_operation=True)
				return

		try:

			qbo_invoice_val = self._prepare_qbo_invoice_vals(invoice, quickbook_instance)

			inv_url = f"{quickbook_instance.quickbook_base_url}/{quickbook_instance.realm_id}/invoice"

			response_json, status_code = self.env['quickbooks.api.vts'].sudo().qb_post_request(quickbook_instance.access_token,
				inv_url,qbo_invoice_val)

			if status_code in (200, 201):
				invoice_data = response_json.get("Invoice", {})
				qbk_inv_id = invoice_data.get("Id")
				invoice.qbk_invoice_id = qbk_inv_id
				invoice.error_in_export = False
				invoice.is_inv_exported = True
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
				quickbooks_operation_message=f"Exception: {str(e)}",process_request_message=qbo_invoice_val,process_response_message=str(e),
				log_id=log_id,fault_operation=True)
			return None

	# Prepare QuickBooks Vendor Bill values
	def _prepare_qbo_vendor_bill_vals(self, bill, quickbook_instance, log_id=None):
		qbo_bill_val = {
			"TxnDate": str(bill.invoice_date),
			"DocNumber": bill.name,
			"VendorRef": {
				"value": bill.partner_id.qbk_vendor_id,
				"name": bill.partner_id.name,
			},
			"SalesTermRef": {
				"value": bill.invoice_payment_term_id.qck_payment_terms_ID if bill.invoice_payment_term_id else '',
			},
			"Line": [],
			"TotalAmt": float(bill.amount_total),
			"Balance": float(bill.amount_residual),
		}

		line_number = 1
		for line in bill.invoice_line_ids:

			if not line.product_id.product_tmpl_id.qkb_product_ID:
				qbk_product_id = line.product_id.product_tmpl_id.export_product_to_qbk()
				if line.product_id.product_tmpl_id.qkb_product_ID:
					msg = f"Product {line.product_id.name} Created into QuickBooks."
					bill.message_post(body=msg)
				else:
					msg = qbk_product_id
					bill.message_post(body=msg)
					bill.error_in_export = True
					self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name="bill",
						quickbooks_operation_type="export",instance=quickbook_instance.id,
						quickbooks_operation_message=msg,process_request_message={},
						process_response_message={},log_id=log_id,fault_operation=True)
					return
				
			qbo_bill_val["Line"].append({
					"DetailType": "ItemBasedExpenseLineDetail",
					"Amount": float(line.price_subtotal),
					"Description": line.name or "",
					"ItemBasedExpenseLineDetail": {
						"ItemRef": {
							"value": line.product_id.qkb_product_ID,
							"name": line.product_id.name
						},
						"Qty": line.quantity,
						"UnitPrice": float(line.price_unit),
					}
				})

		return qbo_bill_val

	"""Export vendor bill to QuickBooks"""
	def export_vendor_bill_quickbooks(self, bill):
		if bill.state != 'posted':
			return

		if bill.qbk_bill_id:
			bill.message_post(body=f"Vendor Bill already exported to QuickBooks with ID {bill.qbk_bill_id}.")
			return

		company = bill.company_id.id if bill.company_id else False
		quickbook_instance = self.env['quickbooks.connect'].sudo().search([('state','=','connected'),('company_id', '=', company)], limit=1)

		if not quickbook_instance:
			bill.message_post(body=f"No QuickBooks instance configured for {company} company.")
			return

		log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(
			quickbooks_operation_name="bill",
			quickbooks_operation_type="export",
			instance=quickbook_instance.id,
			quickbooks_operation_message=f"Starting export for Vendor Bill {bill.name}"
		)

		if not bill.partner_id.qbk_vendor_id:
			qbk_vendor_id = bill.partner_id._export_to_quickbooks(bill.partner_id, 'vendor', 'qbk_vendor_id')
			if bill.partner_id.qbk_vendor_id:
				msg = f"Vendor {bill.partner_id.name} Created into QuickBooks."
				bill.message_post(body=msg)
			else:
				msg = qbk_vendor_id
				bill.message_post(body=msg)
				bill.error_in_export = True
				self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name="bill",
					quickbooks_operation_type="export",instance=quickbook_instance.id,
					quickbooks_operation_message=msg,process_request_message={},
					process_response_message={},log_id=log_id,fault_operation=True)
				return
		
		qbo_bill_val = self._prepare_qbo_vendor_bill_vals(bill, quickbook_instance, log_id)

		try:

			bill_url = f"{quickbook_instance.quickbook_base_url}/{quickbook_instance.realm_id}/bill"

			response_json, status_code = self.env['quickbooks.api.vts'].sudo().qb_post_request(quickbook_instance.access_token,
				bill_url,qbo_bill_val)

			if status_code in (200, 201):
				bill_data = response_json.get("Bill", {})
				qbk_bill_id = bill_data.get("Id")
				bill.qbk_bill_id = qbk_bill_id
				bill.error_in_export = False
				bill.is_bill_exported = True
				bill.message_post(body=f"Exported Vendor Bill {bill.name} to QuickBooks, ID: {qbk_bill_id}")
				self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
					quickbooks_operation_name="bill",
					quickbooks_operation_type="export",
					instance=quickbook_instance.id,
					quickbooks_operation_message=f"Successfully exported Vendor Bill {bill.name}",
					process_request_message=qbo_bill_val,
					process_response_message=response_json,
					log_id=log_id
				)
				return response_json
			else:
				msg = f"Failed to export Vendor Bill {bill.name} to QuickBooks. Response: {response_json}"
				bill.message_post(body=msg)
				bill.error_in_export = True
				self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name="bill",
					quickbooks_operation_type="export",instance=quickbook_instance.id,
					quickbooks_operation_message=msg,process_request_message=qbo_bill_val,
					process_response_message=response_json,log_id=log_id,
					fault_operation=True)
				return None

		except Exception as e:
			bill.message_post(body=f"Exception while exporting Vendor Bill {bill.name} to QuickBooks: {str(e)}")
			bill.error_in_export = True
			self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(
				quickbooks_operation_name="bill",quickbooks_operation_type="export",
				instance=quickbook_instance.id,quickbooks_operation_message=f"Exception: {str(e)}",
				process_request_message=qbo_bill_val,process_response_message=str(e),
				log_id=log_id,fault_operation=True)
			return None

	def export_invoice_bill_to_quickbooks(self):
		for move in self:
			if move.move_type == 'out_invoice':
				invoice = self.export_invoice_quickbooks(move)
			elif move.move_type == 'in_invoice':
				vendor_bill = self.export_vendor_bill_quickbooks(move)