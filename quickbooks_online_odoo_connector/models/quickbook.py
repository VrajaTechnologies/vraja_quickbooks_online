# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import xmltodict
from xmltodict import ParsingInterrupted

class QuickbooksConnect(models.Model):

	_inherit = 'quickbooks.connect'

	product_creation = fields.Boolean(string="Product Creation", help="Enable this option to create a product if does not exist when importing.",copy=False)

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