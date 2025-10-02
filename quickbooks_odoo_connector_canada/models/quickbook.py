# -*- coding: utf-8 -*-
from odoo import models, fields, api

class QuickbooksConnect(models.Model):
    _inherit = 'quickbooks.connect'

    product_creation = fields.Boolean(string="Product Creation",help="Enable this option to create a product if does not exist when importing.",copy=False)
    vendor_creation = fields.Boolean(string="Vendor Creation", help="Enable this option to create a vendor if does not exist when importing",copy=False)
    qck_product_count = fields.Integer(string="Product Count")
    qck_vendor_count = fields.Integer(string="Vendor Count")

    # def _compute_product_count(self):
    #     for rec in self:
    #         rec.qck_product_count = self.env['product.template'].search_count([('qck_instance_id', '=', rec.id)])
    #
    def action_qkb_product(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('product.product_template_action')
        action['domain'] = [('qck_instance_id', '=', self.id)]
        return action

    # def _compute_vendor_count(self):
    #     for rec in self:
    #         rec.qck_vendor_count = self.env['res.partner'].search_count([('qck_instance_id', '=', rec.id)])
    #
    def action_qkb_vendor(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id('account.res_partner_action_supplier')
        action['domain'] = [('qck_instance_id', '=', self.id)]
        return action

