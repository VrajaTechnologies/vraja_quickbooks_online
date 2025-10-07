# -*- coding: utf-8 *-*
from odoo import models, fields, api


class Partner(models.Model):
    _inherit = "res.partner"

    qkca_vendor_ID = fields.Char(string="Quickbook Vendor ID",copy=False)
    qkca_vendor_type = fields.Char(string="Quickbook Vendor Type",copy=False)
