# -*- coding: utf-8 -*-
from odoo import models, fields, api

class QuickbooksConnect(models.Model):

    _inherit = 'quickbooks.connect'

    qkca_product_creation = fields.Boolean(string="Product Creation",help="Enable this option to create a product if does not exist when importing.",copy=False)
    qkca_vendor_creation = fields.Boolean(string="Vendor Creation", help="Enable this option to create a vendor if does not exist when importing",copy=False)
    qkca_category_creation = fields.Boolean(string="Product Category Creation",help="Enable this option to create a product category if does not exist when importing.",copy=False)
    qca_product_count = fields.Integer(string="Product Count",compute="_compute_product_count")
    qca_vendor_count = fields.Integer(string="Vendor Count",compute="_compute_vendor_count")
    qkca_invoice_creation = fields.Boolean(string="Invoice Creation",help="Enable this option to create a invoice if does not exist when importing.",copy=False)
    qca_invoice_count = fields.Integer(string="Invoice Count", compute="_compute_invoice_count")

    def _compute_product_count(self):
        for rec in self:
            rec.qca_product_count = self.env['product.template'].sudo().search_count([('qck_instance_id', '=', rec.id)])

    def action_qkb_product(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('product.product_template_action')
        action['context'] = {}
        action['domain'] = [('qck_instance_id', '=', self.id)]
        return action

    def _compute_vendor_count(self):
        for rec in self:
            rec.qca_vendor_count = self.env['res.partner'].search_count([('qkca_vendor_ID', '!=', False)])

    def action_qkb_vendor(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.res_partner_action_customer")
        action['context'] = {}
        action['domain'] = [('qkca_vendor_ID', '!=', False)]
        return action

    def _compute_invoice_count(self):
        for rec in self:
            rec.qca_invoice_count = self.env['account.move'].search_count([('qkca_invoice_ID', '!=', False)])

    def action_qkb_invoice(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_in_invoice_type")
        action['context'] = {}
        action['domain'] = [('qkca_invoice_ID', '!=', False)]
        return action

