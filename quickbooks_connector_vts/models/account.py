# -*- coding: utf-8 *-*
from odoo import models, fields, api

class Account(models.Model):

	_inherit = "account.account"

	qck_instance_id = fields.Many2one('quickbooks.connect',string="Quickbook Instance",copy=False)
	quickbooks_id = fields.Char(string="Quickbook ID",copy=False)
	qk_classification = fields.Char(string="Classification")
	qk_accountsubType = fields.Char(string="Account SubType")

class PaymentTerms(models.Model):

	_inherit = 'account.payment.term'

	qck_instance_id = fields.Many2one('quickbooks.connect',string="Quickbook Instance",copy=False)
	qck_payment_terms_ID = fields.Char(string="Quickbook Terms ID")

class Taxes(models.Model):

	_inherit = 'account.tax'

	qck_instance_id = fields.Many2one('quickbooks.connect',string="Quickbook Instance",copy=False)
	qck_taxes_ID = fields.Char(string="Quickbook Taxes ID")
