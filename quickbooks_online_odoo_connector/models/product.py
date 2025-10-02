# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductTemplate(models.Model):
	_inherit = 'product.template'

	qck_instance_id = fields.Many2one('quickbooks.connect', string="Quickbook Instance", copy=False)
	qkb_product_ID = fields.Char(string="Quickbook Product ID")
	qck_product_type = fields.Char(string="Quickbook Product Type ID")
	error_in_export = fields.Boolean(string="Error In Export",copy=False)

	def _prepare_product_payload(self):
		product_payload = {
			"Name": self.name,
			"ExpenseAccountRef": {
				"value": str(self.property_account_expense_id.id) if self.property_account_expense_id else "80",
				"name": self.property_account_expense_id.name if self.property_account_expense_id else "Cost of Goods Sold"
			}
		}

		income_account_ref = {
			"value": str(self.property_account_income_id.id) if self.property_account_income_id else "79",
			"name": self.property_account_income_id.name if self.property_account_income_id else "Sales of Product Income"
		}

		if self.type == "service":
			product_payload.update({
				"Type": "Service",
				"IncomeAccountRef": income_account_ref,
			})

		elif self.is_storable:
			product_payload.update({
				"Type": "Inventory",
				"TrackQtyOnHand": True,
				"QtyOnHand": max(1.0, float(self.qty_available) if self.qty_available else 1.0),
				"IncomeAccountRef": income_account_ref,
				"AssetAccountRef": {"value": "81", "name": "Inventory Asset"},
				"InvStartDate": fields.Date.today().strftime("%Y-%m-%d")})

		else:
			product_payload["Type"] = "NonInventory"

		return product_payload

	def export_product_to_qbk(self):
		self.ensure_one()

		if self.qkb_product_ID:
			self.message_post(body=f"Product already exported to QuickBooks with ID {self.qkb_product_ID}.")
			return

		company = self.company_id.id or self.env.company.id
		quickbook_instance = self.env['quickbooks.connect'].sudo().search([('state', '=', 'connected'), ('company_id', '=', company)], limit=1)

		if not quickbook_instance:
			msg = f"No QuickBooks instance configured for {company} company."
			self.message_post(body=msg)
			return msg

		log_id = self.env['quickbooks.log.vts'].sudo().generate_quickbooks_logs(quickbooks_operation_name="product",
			quickbooks_operation_type="export",instance=quickbook_instance.id,
			quickbooks_operation_message=f"Starting export for Product {self.name}")

		payload = self._prepare_product_payload()
		qb_api = self.env['quickbooks.api.vts'].sudo()
		qb_log = self.env['quickbooks.log.vts.line'].sudo()

		try:
			pro_url = f"{quickbook_instance.quickbook_base_url}/{quickbook_instance.realm_id}/item"
			response_json, status_code = qb_api.qb_post_request(quickbook_instance.access_token, pro_url, payload)

			if status_code in (200, 201):
				product_data = response_json.get("Item", {})
				qkb_product_id = product_data.get("Id")
				self.write({'qkb_product_ID': qkb_product_id,
					'qck_instance_id': quickbook_instance.id,
					'error_in_export': False})
				self.message_post(body=f"Exported Product {self.name} to QuickBooks, ID: {qkb_product_id}")

				qb_log.generate_quickbooks_process_line(quickbooks_operation_name="product",
					quickbooks_operation_type="export",instance=quickbook_instance.id,
					quickbooks_operation_message=f"Successfully exported Product {self.name}",
					process_request_message=payload,process_response_message=response_json,
					log_id=log_id)
				return qkb_product_id
			else:
				msg = f"Failed to export Product {self.name} to QuickBooks. Response: {response_json}"
				self.message_post(body=msg)
				self.error_in_export = True

				qb_log.generate_quickbooks_process_line(quickbooks_operation_name="product",
					quickbooks_operation_type="export",instance=quickbook_instance.id,
					quickbooks_operation_message=msg,process_request_message=payload,
					process_response_message=response_json,log_id=log_id,fault_operation=True)
				return msg

		except Exception as e:
			msg = f"Exception while exporting product {self.name} to QuickBooks: {str(e)}"
			self.message_post(body=msg)
			self.error_in_export = True
			qb_log.generate_quickbooks_process_line(quickbooks_operation_name="product",quickbooks_operation_type="export",
				instance=quickbook_instance.id,quickbooks_operation_message=f"Exception: {str(e)}",
				process_request_message=payload,process_response_message=str(e),
				log_id=log_id,fault_operation=True)
			return msg


	def export_product_to_quickbooks(self):
		for product in self:
			product.export_product_to_qbk()

class ProductProduct(models.Model):
    _inherit = 'product.product'

    qck_instance_id = fields.Many2one('quickbooks.connect', string="Quickbook Instance",
                                      related='product_tmpl_id.qck_instance_id', store=True)
    qkb_product_ID = fields.Char(string="Quickbook Product ID",
                                 related='product_tmpl_id.qkb_product_ID', store=True)
    qck_product_type = fields.Char(string="Quickbook Product Type ID",
                                   related='product_tmpl_id.qck_product_type', store=True)
    error_in_export = fields.Boolean(string="Error In Export",
                                     related='product_tmpl_id.error_in_export', store=True)

