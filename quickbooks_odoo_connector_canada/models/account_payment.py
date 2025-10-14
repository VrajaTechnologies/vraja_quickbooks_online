# -*- coding: utf-8 *-*
from odoo import models, fields, api


class AccountPayment(models.Model):
    _inherit = "account.payment"

    qck_instance_id = fields.Many2one('quickbooks.connect', string="Quickbook Instance", copy=False)
    qkca_payment_ID = fields.Char(string="Quickbook Invoice ID",copy=False)
    qkca_billpay_ID = fields.Char(string="Quickbook Bill Payment ID", copy=False)