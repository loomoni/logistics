# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ApalaFreightOrder(models.Model):
    _name = 'apala.freight.order'
    _description = 'Freight Forwarding Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Freight Order Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'),
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('booking', 'Booking'),
        ('in_transit', 'In Transit'),
        ('customs', 'Customs'),
        ('cleared', 'Cleared'),
        ('delivered', 'Delivered'),
        ('invoiced', 'Invoiced'),
    ], string='Status', default='draft', tracking=True, copy=False)
    customer_id = fields.Many2one('res.partner', string='Customer', required=True, tracking=True)
    freight_type = fields.Selection([
        ('import', 'Import'),
        ('export', 'Export'),
        ('transit', 'Transit'),
        ('cross_border', 'Cross-Border'),
    ], string='Freight Type', default='import')
    mode = fields.Selection([
        ('road', 'Road'),
        ('rail', 'Rail'),
        ('air', 'Air'),
        ('sea', 'Sea'),
        ('multimodal', 'Multimodal'),
    ], string='Transport Mode', default='road')
    origin_country = fields.Many2one('res.country', string='Origin Country')
    destination_country = fields.Many2one('res.country', string='Destination Country')
    origin_port = fields.Char(string='Origin Port / Terminal')
    destination_port = fields.Char(string='Destination Port / Terminal')
    commodity = fields.Char(string='Commodity')
    hs_code = fields.Char(string='HS Code')
    gross_weight_kg = fields.Float(string='Gross Weight (kg)')
    volume_m3 = fields.Float(string='Volume (m³)')
    incoterm_id = fields.Many2one('account.incoterms', string='Incoterm')
    customs_doc_ids = fields.One2many('apala.customs.document', 'freight_order_id', string='Customs Documents')
    transport_order_id = fields.Many2one('apala.transport.order', string='Inland Transport Order')
    bl_number = fields.Char(string='Bill of Lading Number')
    booking_ref = fields.Char(string='Booking Reference')
    etd = fields.Date(string='ETD')
    eta = fields.Date(string='ETA')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    freight_cost = fields.Monetary(string='Freight Cost (TZS)')
    customs_duty = fields.Monetary(string='Customs Duty (TZS)')
    other_charges = fields.Monetary(string='Other Charges (TZS)')
    total_cost = fields.Monetary(string='Total Cost', compute='_compute_total_cost', store=True)
    invoice_id = fields.Many2one('account.move', string='Invoice')
    notes = fields.Text(string='Notes')

    @api.depends('freight_cost', 'customs_duty', 'other_charges')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = rec.freight_cost + rec.customs_duty + rec.other_charges

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('apala.freight.order') or _('New')
        return super().create(vals)

    def action_confirm_booking(self):
        for rec in self:
            rec.state = 'booking'

    def action_in_transit(self):
        for rec in self:
            rec.state = 'in_transit'

    def action_customs(self):
        for rec in self:
            rec.state = 'customs'

    def action_cleared(self):
        for rec in self:
            rec.state = 'cleared'

    def action_delivered(self):
        for rec in self:
            rec.state = 'delivered'

    def action_create_invoice(self):
        """Create an invoice for the freight order."""
        self.ensure_one()
        product = self.env.ref('apala_logistics.product_freight_forwarding_service', raise_if_not_found=False)
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.customer_id.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id if product else False,
                'name': _('Freight Forwarding – %s') % self.name,
                'quantity': 1,
                'price_unit': self.total_cost,
            })],
        }
        invoice = self.env['account.move'].create(invoice_vals)
        self.invoice_id = invoice.id
        self.state = 'invoiced'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values:
            return self.env.ref('mail.mt_note')
        return super()._track_subtype(init_values)
