# -*- coding: utf-8 *-*
from odoo import models, fields, api


class Partner(models.Model):
    _inherit = "res.partner"

    qck_instance_id = fields.Many2one('quickbooks.connect', string="Quickbook Instance", copy=False)
    qkca_vendor_ID = fields.Char(string="Quickbook Product ID")
    qkca_customer_type = fields.Char(string="Quickbook Customer Type")
