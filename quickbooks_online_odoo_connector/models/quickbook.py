# -*- coding: utf-8 *-*
from odoo import models, fields, api, _
import requests
import base64
from odoo.exceptions import UserError


class QuickbooksConnect(models.Model):

    _name = 'quickbooks.connect'
    _description = "Quickbooks Connect"

    name = fields.Char(string="Name")
    client_id = fields.Char(string="Client ID",copy=False)
    client_secret = fields.Char(string="Client Secret",copy=False)
    redirect_url = fields.Char(string="Redirect URL",copy=False)
    environment = fields.Selection([('sandbox','Sandbox'),('production','Production')],default="sandbox",string="Environment")
    qk_company_id = fields.Many2one('quickbooks.company.vts',string="Quickbooks Company")
    access_token = fields.Char(string="Access token")
    refresh_token = fields.Char(string="Refresh token")
    realm_id = fields.Char(string="Realm ID")
    state = fields.Selection([('connecting','Connecting'),('connected','Connected'),('failed','Failed')],string="State",default="connecting")
    reason = fields.Text(string="Reason")
    quickbook_base_url = fields.Char(string="URL")
    company_id = fields.Many2one('res.company',string="Company",default=lambda self: self.env.user.company_id)

    def action_quickbook_open_instance_view_form(self):
        form_id = self.sudo().env.ref('quickbooks_online_odoo_connector.quickbooks_connect_form_view')
        action = {
            'name': _('Quickbooks Instance'),
            'view_id': False,
            'res_model': 'quickbooks.connect',
            'context': self._context,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(form_id.id, 'form')],
            'type': 'ir.actions.act_window',
        }
        return action

    @api.onchange('environment')
    def change_quick_environment(self):
        if self.environment == 'production':
            self.quickbook_base_url = "https://quickbooks.api.intuit.com/v3/company"
        elif self.environment == 'sandbox':
            self.quickbook_base_url = "https://sandbox-quickbooks.api.intuit.com/v3/company"

    def action_connect_quickbooks(self):
        auth_url = (
            f"https://appcenter.intuit.com/connect/oauth2"
            f"?client_id={self.client_id}"
            f"&response_type=code"
            f"&scope=com.intuit.quickbooks.accounting"
            f"&redirect_uri={self.redirect_url}"
            f"&state={self.id}"
        )
        return {
            "type": "ir.actions.act_url",
            "url": auth_url,
            "target": "self",
        }

    def reconnect_quickbook(self):
        self.state = 'connecting'
        self.access_token = ''

    def refresh_access_token(self):
        quick_connects = self if self else self.env['quickbooks.connect'].search([])
        for rec in quick_connects:
            token_url = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
            client_creds = f"{rec.client_id}:{rec.client_secret}"
            auth_header = base64.b64encode(client_creds.encode()).decode()

            headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {auth_header}"
            }
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": rec.refresh_token
            }

            try:
                response = requests.post(token_url, headers=headers, data=payload, timeout=30)
                if response.status_code == 200:
                    tokens = response.json()
                    rec.write({
                        "access_token": tokens.get("access_token"),
                        "refresh_token": tokens.get("refresh_token"),
                    })
                else:
                    rec.write({"reason": response.text})
            except requests.exceptions.RequestException as e:
                rec.write({"reason": str(e)})