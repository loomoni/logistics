# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import models, fields, api


class ApalaDashboard(models.TransientModel):
    _name = 'apala.dashboard'
    _description = 'Apala Logistics Dashboard'

    active_trips_count = fields.Integer(
        string='Active Trips', compute='_compute_dashboard')
    pending_orders_count = fields.Integer(
        string='Pending Orders', compute='_compute_dashboard')
    overdue_trips_count = fields.Integer(
        string='Overdue Trips', compute='_compute_dashboard')
    deliveries_today = fields.Integer(
        string='Deliveries Today', compute='_compute_dashboard')
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id)
    revenue_this_month = fields.Monetary(
        string='Revenue This Month', compute='_compute_dashboard')
    expenses_this_month = fields.Monetary(
        string='Expenses This Month', compute='_compute_dashboard')
    vehicles_available = fields.Integer(
        string='Vehicles Available', compute='_compute_dashboard')
    orders_this_month = fields.Integer(
        string='Orders This Month', compute='_compute_dashboard')

    @api.depends()
    def _compute_dashboard(self):
        Trip = self.env['apala.trip']
        Order = self.env['apala.transport.order']
        Expense = self.env['apala.trip.expense']
        Vehicle = self.env['fleet.vehicle']

        today = fields.Date.today()
        now = datetime.now()
        month_start = today.replace(day=1)

        for rec in self:
            # Active trips
            rec.active_trips_count = Trip.search_count([
                ('state', 'in', ['dispatched', 'en_route']),
            ])
            # Pending orders
            rec.pending_orders_count = Order.search_count([
                ('state', 'in', ['draft', 'confirmed']),
            ])
            # Overdue trips
            rec.overdue_trips_count = Trip.search_count([
                ('state', 'in', ['dispatched', 'en_route']),
                ('estimated_arrival', '<', now),
            ])
            # Deliveries today
            rec.deliveries_today = Trip.search_count([
                ('state', '=', 'closed'),
                ('arrival_date', '>=', fields.Datetime.to_string(
                    datetime.combine(today, datetime.min.time()))),
                ('arrival_date', '<=', fields.Datetime.to_string(
                    datetime.combine(today, datetime.max.time()))),
            ])
            # Revenue this month (sum of freight charges on invoiced orders)
            invoiced_orders = Order.search([
                ('state', '=', 'invoiced'),
                ('create_date', '>=', month_start),
            ])
            rec.revenue_this_month = sum(invoiced_orders.mapped('freight_charge'))
            # Expenses this month
            expenses = Expense.search([
                ('date', '>=', month_start),
                ('date', '<=', today),
            ])
            rec.expenses_this_month = sum(expenses.mapped('amount'))
            # Vehicles available (not in active trip)
            busy_vehicle_ids = Trip.search([
                ('state', 'in', ['dispatched', 'en_route']),
            ]).mapped('vehicle_id').ids
            rec.vehicles_available = Vehicle.search_count([
                ('id', 'not in', busy_vehicle_ids),
            ])
            # Orders this month
            rec.orders_this_month = Order.search_count([
                ('create_date', '>=', month_start),
            ])

    def action_view_overdue_trips(self):
        """Open trip list filtered to overdue trips."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Overdue Trips',
            'res_model': 'apala.trip',
            'view_mode': 'tree,form',
            'domain': [
                ('state', 'in', ['dispatched', 'en_route']),
                ('estimated_arrival', '<', fields.Datetime.now()),
            ],
        }

    def action_view_active_trips(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Active Trips',
            'res_model': 'apala.trip',
            'view_mode': 'tree,form',
            'domain': [('state', 'in', ['dispatched', 'en_route'])],
        }

    def action_view_pending_orders(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Pending Orders',
            'res_model': 'apala.transport.order',
            'view_mode': 'tree,form',
            'domain': [('state', 'in', ['draft', 'confirmed'])],
        }
