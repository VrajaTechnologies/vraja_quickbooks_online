# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import xmltodict
from xmltodict import ParsingInterrupted

class QuickbooksConnect(models.Model):

	_inherit = 'quickbooks.connect'

	product_creation = fields.Boolean(string="Product Creation", help="Enable this option to create a product if does not exist when importing.", copy=False)
	qck_product_count = fields.Integer(string="Product Count", compute='_compute_product_count')

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
		action = self.env["ir.actions.actions"]._for_xml_id('sale.product_template_action')
		action['domain'] = [('qck_instance_id', '=', self.id)]
		return action