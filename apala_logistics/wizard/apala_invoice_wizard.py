# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ApalaInvoiceWizard(models.TransientModel):
    _name = 'apala.invoice.wizard'
    _description = 'Create Invoice Wizard'

    transport_order_ids = fields.Many2many('apala.transport.order', string='Transport Orders')
    invoice_date = fields.Date(string='Invoice Date', default=fields.Date.today)
    payment_term_id = fields.Many2one('account.payment.term', string='Payment Terms')
    notes = fields.Text(string='Notes')

    def action_create_invoice(self):
        """Create account.move (out_invoice) with one line per transport order."""
        self.ensure_one()
        if not self.transport_order_ids:
            raise UserError(_('Please select at least one transport order.'))

        product = self.env.ref(
            'apala_logistics.product_freight_transport_service', raise_if_not_found=False)

        invoice_lines = []
        for order in self.transport_order_ids:
            invoice_lines.append((0, 0, {
                'product_id': product.id if product else False,
                'name': _('Freight Transport – %s') % order.name,
                'quantity': 1,
                'price_unit': order.freight_charge,
            }))

        # Use the customer from the first transport order
        partner = self.transport_order_ids[0].customer_id

        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': self.invoice_date,
            'invoice_payment_term_id': self.payment_term_id.id if self.payment_term_id else False,
            'narration': self.notes,
            'invoice_line_ids': invoice_lines,
        }

        invoice = self.env['account.move'].create(invoice_vals)

        # Link invoice back to transport orders
        for order in self.transport_order_ids:
            order.invoice_ids = [(4, invoice.id)]
            order.state = 'invoiced'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }
