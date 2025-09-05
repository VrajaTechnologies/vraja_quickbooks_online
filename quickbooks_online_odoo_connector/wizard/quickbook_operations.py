from odoo import models, fields
from datetime import timedelta


class QuickbooksOperations(models.TransientModel):
    _name = 'quickbooks.operations'
    _description = 'Quickbooks Import Export'

    def _get_default_from_date_order(self):
        quickbook_instance_id = self.env.context.get('active_id')
        instance_id = self.env['quickbooks.connect'].search([('id', '=', quickbook_instance_id)], limit=1)
        # from_date_order = quickbook_instance_id.last_order_synced_date if quickbook_instance_id.last_order_synced_date else fields.Datetime.now() - timedelta(
        #     30)
        from_date_order = fields.Datetime.now() - timedelta(30)
        from_date_order = fields.Datetime.to_string(from_date_order)
        return from_date_order

    def _get_default_to_date(self):
        to_date = fields.Datetime.now()
        to_date = fields.Datetime.to_string(to_date)
        return to_date

    quickbook_instance_id = fields.Many2one('quickbooks.connect',string='Quickbooks Connection',default=lambda self: self.env.context.get('active_id'))
    quickbook_operation = fields.Selection([('import', 'Import')],
                                         string='Quickbooks Operations', default='import')
    import_operations = fields.Selection(
        selection=[('import_account', 'Import Account'),
                   ("import_taxes", "Import Taxes"), 
                   ("import_customers", "Import Customer")],
        string='Import Operations', default='import_customers'
    )
    
    from_date_order = fields.Datetime(string='From OrderDate', default=_get_default_from_date_order)
    to_date_order = fields.Datetime(string='To OrderDate', default=_get_default_to_date)
    quickbooks_order_id = fields.Char(string='Order IDs')

    def execute_process_of_quickbooks(self):
        print("Hello Quick Books")
