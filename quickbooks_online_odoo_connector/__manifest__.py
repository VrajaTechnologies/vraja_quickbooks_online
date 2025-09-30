# -*- coding: utf-8 -*-
{
    # App information
    'name': 'Quickbooks Online Odoo Connector ',
    'category': 'Website',
    'version': '18.0.0.0.1',
    'summary': """Quickbooks Online Odoo Connector""",
    'license': 'OPL-1',

    # Dependencies
    'depends': ["quickbooks_connector_vts","stock"],

    # Views
    'data': [
        'security/ir.model.access.csv',
        'data/quickbook_server_action.xml',
        'views/partner_view.xml',
        'views/qbo_product_map.xml',
        'wizard/quickbook_operation_view.xml',
        'views/quickbooks_view.xml',
        'views/product_template_view.xml',
        'views/account_move_view.xml',
        'views/account_payment_view.xml',
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
