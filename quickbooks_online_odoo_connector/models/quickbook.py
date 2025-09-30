# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import xmltodict
from xmltodict import ParsingInterrupted
from dateutil.relativedelta import relativedelta

class QuickbooksConnect(models.Model):

	_inherit = 'quickbooks.connect'

	product_creation = fields.Boolean(string="Product Creation", help="Enable this option to create a product if does not exist when importing.", copy=False)
	qck_product_count = fields.Integer(string="Product Count", compute='_compute_product_count')
	company_include_tax = fields.Boolean(string="Send Invoice Tax Included",copy=False)
	auto_export_moves = fields.Boolean(string='Automatic Invoice/Bills Export to QBO',default=False,help="Allow automatic export invoices from the beginning of the 'Export Date Point'.")
	export_moves_point_date = fields.Date(string="Export Date Point",default=fields.Date.today(),help="Invoices/Bills export date point.")
	exp_qbk_moves_next_call_point = fields.Datetime(string="Next Export Point",compute="_compute_moves_next_exp_call")

	def _compute_moves_next_exp_call(self):
		cron = self.env.ref('quickbooks_online_odoo_connector.excute_export_moves_to_quickbooks',raise_if_not_found=False,)
		value = cron.nextcall if cron else False
		for rec in self:
			rec.exp_qbk_moves_next_call_point = value

	"""Return dictionary object"""
	@api.model
	def convert_xmltodict(self, response):
		try:
			if type(response) != dict:
				order_dict = xmltodict.parse(response)
			else:
				order_dict = response
		except ParsingInterrupted as e:
			_logger.error(e)
			raise e

		response_dict = json.loads(json.dumps(order_dict))
		return response_dict

	def _compute_product_count(self):
		for rec in self:
			rec.qck_product_count = self.env['product.template'].search_count([('qck_instance_id', '=', rec.id)])


	def action_qck_product(self):
		self.ensure_one()
		action = self.env["ir.actions.actions"]._for_xml_id('product.product_template_action')
		action['domain'] = [('qck_instance_id', '=', self.id)]
		return action

	def export_account_moves_to_qbk(self):
		
		QBConnect = self.env['quickbooks.connect'].sudo()
		AccountMove = self.env['account.move'].sudo()
		quickbook_instances = QBConnect.search([('state', '=', 'connected'),('auto_export_moves', '=', True)])
		for qbk in quickbook_instances:
			if qbk.export_moves_point_date:
				base_domain = [('state', '=', 'posted'),('invoice_date', '>=', qbk.export_moves_point_date),
								('error_in_export', '=', False),('company_id', '=', qbk.company_id.id)]

				invoices = AccountMove.search(base_domain + [('move_type', '=', 'out_invoice'),
					('is_inv_exported', '=', False)])
				for inv in invoices:
					inv.export_invoice_quickbooks(inv)

				bills = AccountMove.search(base_domain + [('move_type', '=', 'in_invoice'),
					('is_bill_exported', '=', False)])
				
				for bill in bills:
					bill.export_vendor_bill_quickbooks(bill)

				all_moves = invoices | bills

				if all_moves:
					last_date = max(all_moves.mapped('invoice_date'))
					qbk.export_moves_point_date = last_date + relativedelta(days=1)