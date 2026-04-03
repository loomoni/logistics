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

    @api.depends()
    def _compute_current_trip(self):
        Trip = self.env['apala.trip']
        for vehicle in self:
            trip = Trip.search([
                ('vehicle_id', '=', vehicle.id),
                ('state', 'in', ['dispatched', 'en_route']),
            ], limit=1, order='departure_date desc')
            vehicle.current_trip_id = trip.id if trip else False
