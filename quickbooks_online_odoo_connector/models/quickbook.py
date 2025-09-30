# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import xmltodict
from xmltodict import ParsingInterrupted

class QuickbooksConnect(models.Model):

	_inherit = 'quickbooks.connect'

	product_creation = fields.Boolean(string="Product Creation", help="Enable this option to create a product if does not exist when importing.", copy=False)
	qck_product_count = fields.Integer(string="Product Count", compute='_compute_product_count')
	company_include_tax = fields.Boolean(string="Send Invoice Tax Included",copy=False)
	auto_export_moves = fields.Boolean(string='Automatic Invoice/Bills Export to QBO',default=False)
	export_moves_point_date = fields.Datetime(string="Export Date Point")
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
		quickbook_instance = self.env['quickbooks.connect'].sudo().search([('state', '=', 'connected'),('auto_export_moves', '=', True)])
		for qbk_instance in quickbook_instance:
			if  qbk_instance.export_moves_point_date:
				invoices = self.env['account.move'].search([
					('state', '=', 'posted'),
					('invoice_date', '>=', qbk_instance.export_moves_point_date.date()),
					('invoice_date', '<=', fields.Date.today()),
					('error_in_export','=', False)])

				for inv in invoices:
					if inv.move_type == 'out_invoice':
						inv.export_invoice_quickbooks(inv)
					elif inv.move_type == 'in_invoice':
						inv.export_vendor_bill_quickbooks(inv)

