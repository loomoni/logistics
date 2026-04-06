# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ApalaFuelLog(models.Model):
    _name = 'apala.fuel.log'
    _description = 'Fuel Log'
    _order = 'date desc'

    name = fields.Char(
        string='Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'),
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehicle', required=True, tracking=True,
    )
    driver_id = fields.Many2one(
        'hr.employee', string='Driver',
        domain=[('is_driver', '=', True)],
    )
    trip_id = fields.Many2one('apala.trip', string='Trip')

    date = fields.Date(
        string='Date', required=True, default=fields.Date.today,
    )
    odometer = fields.Float(string='Odometer (km)')
    litres = fields.Float(string='Litres')
    cost_per_litre = fields.Float(string='Cost per Litre')

    total_cost = fields.Monetary(
        string='Total Cost',
        compute='_compute_total_cost', store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    fuel_station = fields.Char(string='Fuel Station')
    receipt_ref = fields.Char(string='Receipt Reference')
    fuel_card_used = fields.Boolean(string='Fuel Card Used')
    notes = fields.Text(string='Notes')

    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    @api.depends('litres', 'cost_per_litre')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = rec.litres * rec.cost_per_litre

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'apala.fuel.log') or _('New')
        return super().create(vals)
