from odoo import models, fields


class AccountPayment(models.Model):

	_inherit = "account.payment"

	qk_bill_payment_ID = fields.Char(string="Quickbook Bill Payment ID")
	qk_payment_ID = fields.Char(string="Quickbook Payment ID")
	error_in_export = fields.Boolean(string="Error In Export")

	def _prepare_billpayment_payload(self, payment):

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
								"TxnType": "Bill"}]
					}

			bill_payment_payload['Line'].append(bill_val)

		if payment.payment_method_line_id.payment_method_id.code == 'credit':
			bill_payment_payload.update({
						"CreditCardPayment": {
							"CCAccountRef": {
								"name": payment.journal_id.name,
								"value": '35'}}})
		else:
			bill_payment_payload.update({
						"CheckPayment": {
							"BankAccountRef": {
								"name": payment.journal_id.name,
								"value": '35'}}})

		return bill_payment_payload, "billpayment"

	def export_bill_payment_qbo(self, payment):
		if payment.qk_bill_payment_ID:
			payment.message_post(body=f"Bill Payment already exported to QuickBooks with ID {payment.qk_bill_payment_ID}.")
			return

		company = payment.company_id.id if payment.company_id else False
		quickbook_instance = self.env['quickbooks.connect'].sudo().search([('company_id', '=', company)], limit=1)

		if not quickbook_instance:
			payment.message_post(body=f"No QuickBooks instance configured for {company} company.")
			return

		log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(quickbooks_operation_name="billpayment",
			quickbooks_operation_type="export",instance=quickbook_instance.id,
			quickbooks_operation_message=f"Starting export for Bill Payment {payment.name}")

		try:
			if not payment.partner_id.qbk_vendor_id:
				msg = f"Vendor {payment.partner_id.name} not mapped with QuickBooks."
				payment.message_post(body=msg)
				payment.error_in_export = True
				self.env['quickbooks.log.vts.line'].sudo().generate_quickbooks_process_line(quickbooks_operation_name="billpayment",
					quickbooks_operation_type="export",instance=quickbook_instance.id,
					quickbooks_operation_message=msg,process_request_message={},process_response_message={},
					log_id=log_id,fault_operation=True)
				return

			bill_payment_payload, endpoint = self._prepare_billpayment_payload(payment)

			print("TESTt==",bill_payment_payload)

			billp_url = f"{quickbook_instance.quickbook_base_url}/{quickbook_instance.realm_id}/{endpoint}"

			response_json, status_code = self.env['quickbooks.api.vts'].sudo().qb_post_request(
				quickbook_instance.access_token, billp_url, bill_payment_payload)

			print("Hello Aasishshih",response_json)

			if status_code in (200, 201):
				billp_data = response_json.get("BillPayment", {})
				qbk_bp_id = billp_data.get("Id")
				payment.qk_bill_payment_ID = qbk_bp_id
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
				process_request_message={},process_response_message=str(e),
				log_id=log_id,fault_operation=True)
			
			return None

	def export_payment_qbo(self, payment):
		print("Hello AAshishs")
		# payment_payload, endpoint = self._prepare_payment_payload(payment)

	def export_payment_to_quickbooks(self):
		for payment in self:
			if payment.payment_type == "outbound":
				export_bill_payment = self.export_bill_payment_qbo(payment)
			elif payment.payment_type == "inbound":
				export_payment = self.export_payment_qbo(payment)
			


