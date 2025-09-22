# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import xmltodict
from xmltodict import ParsingInterrupted

class QuickbooksConnect(models.Model):

	_inherit = 'quickbooks.connect'

	@api.model
	def convert_xmltodict(self, response):
		"""Return dictionary object"""
		try:
			# convert xml response to OrderedDict collections, return collections.OrderedDict type
			if type(response) != dict:
				order_dict = xmltodict.parse(response)
			else:
				order_dict = response
		except ParsingInterrupted as e:
			_logger.error(e)
			raise e
		# convert OrderedDict to regular dictionary object
		response_dict = json.loads(json.dumps(order_dict))
		return response_dict