from odoo import models, fields

class AccountMove(models.Model):

	_inherit = "account.move"

	def export_invoice_quickbooks(self, move):
		print("Aashish Invoice")

	def export_vendor_bill_quickbooks(self, move):
		print('Aashish Bill')

	def export_invoice_bill_to_quickbooks(self):
		for move in self:
			if move.move_type == 'out_invoice':
				invoice = self.export_invoice_quickbooks(move)
			elif move.move_type == 'in_invoice':
				vendor_bill = self.export_vendor_bill_quickbooks(move)