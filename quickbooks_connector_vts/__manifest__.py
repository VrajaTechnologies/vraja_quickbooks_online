# -*- coding: utf-8 -*-pack
{
    # App information
    'name': 'Quickbooks Online Connector',
    'category': 'Website',
    'version': '18.0.0.0.1',
    'summary': """Quickbooks Online Connector""",
    'license': 'OPL-1',

    # Dependencies
    'depends': ["accountant"],

    # Views
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'wizard/quickbook_operations_view.xml',
        'views/quickbook_view.xml',
        'views/qb_account.xml',
        'views/qb_taxes.xml',
        'views/qb_payment_terms.xml',
        'views/qb_partner_mapping.xml',
        'views/quickbooks_log.xml',
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
