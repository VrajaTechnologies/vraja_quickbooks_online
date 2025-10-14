# -*- coding: utf-8 -*-
{
    # App information
    'name': 'Quickbooks Odoo Connector Canada',
    'category': 'Website',
    'version': '18.0.0.0.1',
    'summary': """Quickbooks Odoo Connector Canada""",
    'license': 'OPL-1',

    # Dependencies
    'depends': ["quickbooks_connector_vts", "stock"],

    # Views
    'data': [
        'security/ir.model.access.csv',
        'wizard/quickbook_operation_view.xml',
        'views/qkb_product_map_view.xml',
        'views/qkb_vendor_map_view.xml',
        'views/qkb_category_map.xml',
        'views/partner_view.xml',
        'views/quickbooks_view.xml',
        'views/product_termplate_view.xml',
        'views/product_category_view.xml',
        'views/qbk_invoice_map.xml',
        'views/account_move_view.xml',
        'views/account_bill_view.xml',
        'views/qkb_customer_payment_view.xml',
        'views/account_payment_view.xml',
        'views/qkb_bill_payment_map_view.xml',
    ],

    # Author
    'author': 'Vraja Technologies',
    'website': 'http://www.vrajatechnologies.com',
    'maintainer': 'Vraja Technologies',

    # Technical
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'live_test_url': 'https://www.vrajatechnologies.com/contactus',
}
