# -*- coding: utf-8 *-*
from odoo import models
import requests

class QuickbooksAPIVts(models.AbstractModel):
    _name = "quickbooks.api.vts"
    _description = "QuickBooks API"

    def _get_quick_book_header(self, token):
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def qb_get_request(self, qck_url, token, endpoint):
        url = f"{qck_url}/{endpoint}"
        response = requests.get(url, headers=self._get_quick_book_header(token))
        return response.json(), response.status_code

    def qb_post_request(self, qck_url, token,endpoint, payload):
        url = f"{qck_url}/{endpoint}"
        response = requests.post(url, headers=self._get_quick_book_header(token), json=payload)
        return response.json(), response.status_code