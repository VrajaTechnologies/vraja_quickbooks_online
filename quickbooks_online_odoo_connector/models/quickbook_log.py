# -*- coding: utf-8 -*-
from odoo import models, fields, api
import pprint

class QuickbooksLog(models.Model):

    _inherit = 'quickbooks.log.vts'

    quickbooks_operation_name = fields.Selection(selection_add=[('vendor', 'Vendor'),('product','Product'),('invoice','Invoice'),('bill','Bill'),('billpayment','Bill Payment')], string="Process Name")

class QuickbooksLogLine(models.Model):

    _inherit = 'quickbooks.log.vts.line'

    quickbooks_operation_name = fields.Selection(selection_add=[('vendor', 'Vendor'),('product','Product'),('invoice','Invoice'),('bill','Bill'),('billpayment','Bill Payment')], string="Process Name")
