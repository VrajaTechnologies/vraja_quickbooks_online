# -*- coding: utf-8 -*-
{
    # App information
    'name': 'Quickbooks Online Odoo Connector',
    'category': 'Website',
    'version': '18.0.0.0.1',
    'summary': """Quickbooks Online Odoo Connector""",
    'license': 'OPL-1',

    # Dependencies
    'depends': ["quickbooks_connector_vts"],

    # Views
    'data': [
        # 'security/ir.model.access.csv',
        'data/quickbook_server_action.xml',
        'views/partner_view.xml',
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
