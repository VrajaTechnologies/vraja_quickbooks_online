# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError
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

    def qb_get_request(self, token, endpoint):
        try:
            response = requests.get(endpoint, headers=self._get_quick_book_header(token), timeout=10)
            response.raise_for_status()
            return response.json(), response.status_code
        except requests.exceptions.ConnectionError:
            raise UserError("Connection Error: Please check your internet connection or QuickBooks API endpoint.")
        except requests.exceptions.Timeout:
            raise UserError("Timeout Error: The request to QuickBooks API took too long. Please try again later.")
        except requests.exceptions.HTTPError as e:
            raise UserError(f"HTTP Error: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise UserError(f"Request Error: {str(e)}")

    def qb_post_request(self, token, endpoint, payload):
        try:
            response = requests.post(endpoint, headers=self._get_quick_book_header(token), json=payload, timeout=10)
            response.raise_for_status()
            return response.json(), response.status_code
        except requests.exceptions.ConnectionError:
            raise UserError("Connection Error: Please check your internet connection or QuickBooks API endpoint.")
        except requests.exceptions.Timeout:
            raise UserError("Timeout Error: The request to QuickBooks API took too long. Please try again later.")
        except requests.exceptions.HTTPError as e:
            raise UserError(f"HTTP Error: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise UserError(f"Request Error: {str(e)}")

    def get_customer_types(self, qck_url, company_id, token):
        query = "SELECT * FROM CustomerType"
        endpoint = f"{company_id}/query"
        url = f"{qck_url}/{endpoint}?query={query}"

        customer_types_response, status = self.qb_get_request(token, url)
        customer_types = customer_types_response.get('QueryResponse', {}).get('CustomerType', [])
        return {ct['Id']: ct['Name'] for ct in customer_types}

    def get_data_from_qiuckbooks(self, qck_url, company_id, token, operation, from_date=None, to_date=None,
                                 filter=None):

        if operation == 'import_customers':
            query = "SELECT * FROM Customer"
            if from_date and to_date:
                query += f" WHERE MetaData.CreateTime >= '{from_date}' AND MetaData.CreateTime <= '{to_date}'"

            endpoint = f"{company_id}/query"
            customer_url = f"{qck_url}/{endpoint}?query={query}"
            customer_info, customer_status = self.qb_get_request(token, customer_url)

        elif operation == 'import_payment_terms':
            query = 'SELECT * FROM TERM'
            if from_date and to_date:
                query += f" WHERE MetaData.CreateTime >= '{from_date}' AND MetaData.CreateTime <= '{to_date}'"
            endpoint = f"{company_id}/query"
            customer_url = f"{qck_url}/{endpoint}?query={query}"
            customer_info, customer_status = self.qb_get_request(token, customer_url)

        elif operation == 'import_taxes':
            query = 'SELECT * FROM TaxCode'
            # if from_date and to_date:
            #     query += f" WHERE MetaData.CreateTime >= '{from_date}' AND MetaData.CreateTime <= '{to_date}'"
            endpoint = f"{company_id}/query"
            customer_url = f"{qck_url}/{endpoint}?query={query}"
            customer_info, customer_status = self.qb_get_request(token, customer_url)

        return customer_info, customer_status
