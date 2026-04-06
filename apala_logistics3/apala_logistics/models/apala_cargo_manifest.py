# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ApalaCargoManifest(models.Model):
    _name = 'apala.cargo.manifest'
    _description = 'Cargo Manifest / Waybill'
    _inherit = ['mail.thread']
    _order = 'name desc'

    name = fields.Char(
        string='Manifest Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'),
    )
    transport_order_id = fields.Many2one('apala.transport.order', string='Transport Order')
    shipper_id = fields.Many2one('res.partner', string='Shipper')
    consignee_id = fields.Many2one('res.partner', string='Consignee')
    manifest_date = fields.Date(string='Manifest Date', default=fields.Date.today)
    line_ids = fields.One2many('apala.cargo.manifest.line', 'manifest_id', string='Cargo Lines')
    total_weight_kg = fields.Float(string='Total Weight (kg)', compute='_compute_totals', store=True)
    total_pieces = fields.Integer(string='Total Pieces', compute='_compute_totals', store=True)
    special_instructions = fields.Text(string='Special Instructions')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('delivered', 'Delivered'),
    ], string='Status', default='draft', tracking=True)
    stock_picking_id = fields.Many2one('stock.picking', string='Warehouse Receipt')
    qr_code_data = fields.Char(
        string='QR Code Data', compute='_compute_qr_code_data')

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Waybill number must be unique!'),
    ]

    def _compute_qr_code_data(self):
        for rec in self:
            to = rec.transport_order_id
            rec.qr_code_data = (
                "APALA|%s|%s|%s|%s|%s|%sKG" % (
                    rec.name or '',
                    to.name if to else '',
                    to.route_id.name if to and to.route_id else '',
                    to.driver_id.name if to and to.driver_id else '',
                    to.vehicle_id.license_plate if to and to.vehicle_id else '',
                    rec.total_weight_kg,
                )
            )

    @api.depends('line_ids.weight_kg', 'line_ids.quantity')
    def _compute_totals(self):
        for rec in self:
            rec.total_weight_kg = sum(rec.line_ids.mapped('weight_kg'))
            rec.total_pieces = int(sum(rec.line_ids.mapped('quantity')))

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('apala.cargo.manifest') or _('New')
        return super().create(vals)

    def action_issue(self):
        for rec in self:
            rec.state = 'issued'

    def action_deliver(self):
        for rec in self:
            rec.state = 'delivered'


class ApalaCargoManifestLine(models.Model):
    _name = 'apala.cargo.manifest.line'
    _description = 'Cargo Manifest Line'

    manifest_id = fields.Many2one('apala.cargo.manifest', string='Manifest', ondelete='cascade')
    description = fields.Char(string='Cargo Description', required=True)
    quantity = fields.Float(string='Quantity', default=1.0)
    unit = fields.Selection([
        ('pieces', 'Pieces'),
        ('kg', 'Kilograms'),
        ('tonnes', 'Tonnes'),
        ('bags', 'Bags'),
        ('drums', 'Drums'),
        ('cartons', 'Cartons'),
        ('pallets', 'Pallets'),
    ], string='Unit', default='pieces')
    weight_kg = fields.Float(string='Weight (kg)')
    volume_m3 = fields.Float(string='Volume (m³)')
    declared_value = fields.Float(string='Declared Value (TZS)')
