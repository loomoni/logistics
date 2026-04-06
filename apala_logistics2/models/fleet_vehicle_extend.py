# -*- coding: utf-8 -*-
from odoo import models, fields, api


class FleetVehicleExtend(models.Model):
    _inherit = 'fleet.vehicle'

    is_apala_vehicle = fields.Boolean(string='Apala Vehicle', default=True)
    vehicle_class = fields.Selection([
        ('prime_mover', 'Prime Mover'),
        ('rigid_truck', 'Rigid Truck'),
        ('trailer', 'Trailer'),
        ('pickup', 'Pickup'),
        ('van', 'Van'),
    ], string='Vehicle Class')
    max_payload_kg = fields.Float(string='Max Payload (kg)')
    max_volume_m3 = fields.Float(string='Max Volume (m³)')
    current_trip_id = fields.Many2one(
        'apala.trip', string='Current Trip',
        compute='_compute_current_trip',
    )
    base_location = fields.Char(string='Base Location / Yard')

    # Maintenance
    maintenance_schedule_ids = fields.One2many(
        'apala.maintenance.schedule', 'vehicle_id', string='Maintenance Schedules')
    maintenance_schedule_count = fields.Integer(
        string='Maintenance Schedules', compute='_compute_maintenance_count')
    next_service_km = fields.Float(
        string='Next Service (km)', compute='_compute_next_service')
    next_service_date = fields.Date(
        string='Next Service Date', compute='_compute_next_service')

    # Fuel
    fuel_log_ids = fields.One2many('apala.fuel.log', 'vehicle_id', string='Fuel Logs')
    avg_fuel_efficiency = fields.Float(
        string='Avg Fuel Efficiency (km/L)', compute='_compute_fuel_stats')
    total_fuel_cost_month = fields.Float(
        string='Fuel Cost This Month', compute='_compute_fuel_stats')

    # Job Cards
    job_card_ids = fields.One2many(
        'apala.vehicle.job.card', 'vehicle_id', string='Job Cards')
    job_card_count = fields.Integer(
        string='Job Cards', compute='_compute_job_card_count')
    active_job_card_id = fields.Many2one(
        'apala.vehicle.job.card', string='Active Job Card',
        compute='_compute_active_job_card')

    # DVSR Status
    current_status = fields.Selection([
        ('ready', 'Ready for Dispatch'),
        ('minor_pm', 'In Garage (Minor/PM)'),
        ('major_breakdown', 'In Garage (Major/Breakdown)'),
        ('awaiting_parts', 'Awaiting Parts/External'),
    ], string='Current Status', compute='_compute_current_status', store=True)

    @api.depends('maintenance_schedule_ids')
    def _compute_maintenance_count(self):
        for vehicle in self:
            vehicle.maintenance_schedule_count = len(vehicle.maintenance_schedule_ids)

    @api.depends('maintenance_schedule_ids.next_service_km', 'maintenance_schedule_ids.next_service_date')
    def _compute_next_service(self):
        for vehicle in self:
            upcoming = vehicle.maintenance_schedule_ids.filtered(
                lambda s: s.state in ('scheduled', 'overdue')
            ).sorted('next_service_date')
            if upcoming:
                vehicle.next_service_km = upcoming[0].next_service_km
                vehicle.next_service_date = upcoming[0].next_service_date
            else:
                vehicle.next_service_km = 0
                vehicle.next_service_date = False

    @api.depends('fuel_log_ids.litres', 'fuel_log_ids.total_cost', 'fuel_log_ids.odometer')
    def _compute_fuel_stats(self):
        today = fields.Date.today()
        month_start = today.replace(day=1)
        for vehicle in self:
            logs = vehicle.fuel_log_ids.sorted('date')
            # Avg efficiency
            if len(logs) >= 2:
                total_km = logs[-1].odometer - logs[0].odometer
                total_litres = sum(logs.mapped('litres'))
                vehicle.avg_fuel_efficiency = total_km / total_litres if total_litres else 0
            else:
                vehicle.avg_fuel_efficiency = 0
            # Monthly cost
            month_logs = vehicle.fuel_log_ids.filtered(
                lambda l: l.date and l.date >= month_start)
            vehicle.total_fuel_cost_month = sum(month_logs.mapped('total_cost'))

    @api.depends('job_card_ids')
    def _compute_job_card_count(self):
        for vehicle in self:
            vehicle.job_card_count = len(vehicle.job_card_ids)

    @api.depends('job_card_ids.state')
    def _compute_active_job_card(self):
        for vehicle in self:
            active = vehicle.job_card_ids.filtered(
                lambda jc: jc.state not in ('completed', 'dispatched', 'cancelled'))
            vehicle.active_job_card_id = active[0].id if active else False

    @api.depends('job_card_ids.state')
    def _compute_current_status(self):
        for vehicle in self:
            active = vehicle.active_job_card_id
            if active:
                if active.state == 'draft':
                    vehicle.current_status = 'awaiting_parts'
                elif active.state == 'in_progress':
                    vehicle.current_status = 'minor_pm'
                else:
                    vehicle.current_status = 'major_breakdown'
            else:
                vehicle.current_status = 'ready'

    @api.depends()
    def _compute_current_trip(self):
        Trip = self.env['apala.trip']
        for vehicle in self:
            trip = Trip.search([
                ('vehicle_id', '=', vehicle.id),
                ('state', 'in', ['dispatched', 'en_route']),
            ], limit=1, order='departure_date desc')
            vehicle.current_trip_id = trip.id if trip else False

    # -- Smart Button Actions --
    def action_view_job_cards(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Job Cards',
            'res_model': 'apala.vehicle.job.card',
            'view_mode': 'tree,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }

    def action_view_maintenance_schedules(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Maintenance Schedules',
            'res_model': 'apala.maintenance.schedule',
            'view_mode': 'tree,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }

    def action_view_fuel_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Fuel Logs',
            'res_model': 'apala.fuel.log',
            'view_mode': 'tree,form',
            'domain': [('vehicle_id', '=', self.id)],
            'context': {'default_vehicle_id': self.id},
        }
