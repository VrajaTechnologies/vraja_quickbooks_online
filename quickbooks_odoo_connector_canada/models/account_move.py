# -*- coding: utf-8 *-*
from odoo import models, fields, api


class AccountMove(models.Model):
    
    _inherit = "account.move"

    qck_instance_id = fields.Many2one('quickbooks.connect', string="Quickbook Instance", copy=False)
    qkca_invoice_ID = fields.Char(string="Quickbook Invoice ID",copy=False)
    qck_invoice_doc = fields.Char(string="Quickbook Doc-Number",copy=False)
    qkca_bill_ID = fields.Char(string="Quickbook Bill ID",copy=False)
