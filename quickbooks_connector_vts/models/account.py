# -*- coding: utf-8 *-*
from odoo import models, fields, api

class Account(models.Model):

	_inherit = "account.account"

	qck_instance_id = fields.Many2one('quickbooks.connect',string="Quickbook Instance",copy=False)

class PaymentTerms(models.Model):

	_inherit = 'account.payment.term'

	qck_instance_id = fields.Many2one('quickbooks.connect',string="Quickbook Instance",copy=False)

class PaymentTerms(models.Model):

	_inherit = 'account.payment.term'

	qck_instance_id = fields.Many2one('account.tax',string="Quickbook Instance",copy=False)