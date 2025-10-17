# -*- coding: utf-8 -*-
from odoo import models, fields, api
import json
import xmltodict
from xmltodict import ParsingInterrupted


class QuickbooksConnect(models.Model):

    _inherit = 'quickbooks.connect'

    qkca_product_creation = fields.Boolean(string="Product Creation",help="Enable this option to create a product if does not exist when importing.",copy=False)
    qkca_vendor_creation = fields.Boolean(string="Vendor Creation", help="Enable this option to create a vendor if does not exist when importing",copy=False)
    qkca_category_creation = fields.Boolean(string="Product Category Creation",help="Enable this option to create a product category if does not exist when importing.",copy=False)
    qca_product_count = fields.Integer(string="Product Count",compute="_compute_product_count")
    qca_vendor_count = fields.Integer(string="Vendor Count",compute="_compute_vendor_count")
    qkca_invoice_creation = fields.Boolean(string="Invoice Creation",help="Enable this option to create a invoice if does not exist when importing.",copy=False)
    qkca_bill_creation = fields.Boolean(string="Bill Creation",help="Enable this option to create a bill if does not exist when importing.",copy=False)
    qca_invoice_count = fields.Integer(string="Invoice Count", compute="_compute_invoice_count")
    qca_bill_count = fields.Integer(string="Bill Count",compute="_compute_bill_count")
    qkca_payment_creation = fields.Boolean(string="Customer Payment Creation", help="Enable this option to create a customer payment if does not exist when importing",copy=False)
    qca_payment_count =  fields.Integer(string="Customer Payment Count",compute="_compute_payment_count")
    qkca_bill_payment_creation = fields.Boolean(string="Bill Payment Creation",help="Enable this option to create a Vendor Bill if does not exist when importing.",copy=False)
    qca_billpayment_count = fields.Integer(string="Vendor Bill Payment Count", compute="_compute_billpayment_count")
    company_included_tax = fields.Boolean(string="Send Invoice Tax Included", copy=False)

    def _compute_product_count(self):
        for rec in self:
            rec.qca_product_count = self.env['product.template'].sudo().search_count([('qck_instance_id', '=', rec.id)])

    def action_qkb_product(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('sale.product_template_action')
        action['context'] = {}
        action['domain'] = [('qck_instance_id', '=', self.id)]
        return action

    def _compute_vendor_count(self):
        for rec in self:
            rec.qca_vendor_count = self.env['res.partner'].search_count([('qkca_vendor_ID', '!=', False)])

    def action_qkb_vendor(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.res_partner_action_supplier")
        action['context'] = {}
        action['domain'] = [('qkca_vendor_ID', '!=', False)]
        return action

    def _compute_invoice_count(self):
        for rec in self:
            rec.qca_invoice_count = self.env['account.move'].search_count([('qkca_invoice_ID', '!=', False)])

    def action_qkb_invoice(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        # action['context'] = {}
        action['domain'] = [('qkca_invoice_ID', '!=', False)]
        return action

    def _compute_bill_count(self):
        for rec in self:
            rec.qca_bill_count = self.env['account.move'].search_count([('qkca_bill_ID', '!=', False)])

    def action_qkb_bill(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_in_invoice_type")
        # action['context'] = {}
        action['domain'] = [('qkca_bill_ID', '!=', False)]
        return action

    def _compute_payment_count(self):
        for rec in self:
            rec.qca_payment_count = self.env['account.payment'].search_count([('qkca_payment_ID', '!=', False)])

    def action_qkb_customer_payment(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_account_payments")
        action['context'] = {}
        action['domain'] = [('qkca_payment_ID', '!=', False)]
        return action

    def _compute_billpayment_count(self):
        for rec in self:
            rec.qca_billpayment_count = self.env['account.payment'].search_count([('qkca_billpay_ID', '!=', False)])

    def action_qkb_bill_payment(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_account_payments_payable")
        action['context'] = {}
        action['domain'] = [('qkca_billpay_ID', '!=', False)]
        return action


    @api.model
    def convert_response_xmltodict(self, response):
        try:
            if type(response) != dict:
                order_dict = xmltodict.parse(response)
            else:
                order_dict = response
        except ParsingInterrupted as e:
            _logger.error(e)
            raise e

        response_dict = json.loads(json.dumps(order_dict))
        return response_dict

