# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductTemplate(models.Model):

	_inherit = 'product.template'

	qkb_product_ID = fields.Char(string="Quickbook Product ID")