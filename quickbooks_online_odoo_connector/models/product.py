# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductTemplate(models.Model):

	_inherit = 'product.template'

	qck_instance_id = fields.Many2one('quickbooks.connect',string="Quickbook Instance",copy=False)
	qkb_product_ID = fields.Char(string="Quickbook Product ID")