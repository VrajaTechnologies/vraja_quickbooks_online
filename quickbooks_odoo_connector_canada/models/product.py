# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductTemplate(models.Model):
	_inherit = 'product.template'

	qck_instance_id = fields.Many2one('quickbooks.connect', string="Quickbook Instance", copy=False)
	qkca_product_ID = fields.Char(string="Quickbook Product ID")
	qkca_product_type = fields.Char(string="Quickbook Product Type ID")
	qkca_error_in_export = fields.Boolean(string="Error In Export",copy=False)

class ProductProduct(models.Model):
    _inherit = 'product.product'

    qck_instance_id = fields.Many2one('quickbooks.connect', string="Quickbook Instance",
                                      related='product_tmpl_id.qck_instance_id', store=True)
    qkca_product_ID = fields.Char(string="Quickbook Product ID",
                                 related='product_tmpl_id.qkca_product_ID', store=True)
    qkca_product_type = fields.Char(string="Quickbook Product Type ID",
                                   related='product_tmpl_id.qkca_product_type', store=True)
    qkca_error_in_export = fields.Boolean(string="Error In Export",
                                     related='product_tmpl_id.qkca_error_in_export', store=True)

