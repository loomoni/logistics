# -*- coding: utf-8 -*-
from odoo import models, fields


class ApalaRoute(models.Model):
    _name = 'apala.route'
    _description = 'Logistics Route'
    _order = 'name'

    name = fields.Char(string='Route Name', required=True, help='e.g. Dar es Salaam – Mwanza')
    code = fields.Char(string='Route Code', help='e.g. DAR-MWZ')
    origin_city = fields.Char(string='Origin City')
    destination_city = fields.Char(string='Destination City')
    distance_km = fields.Float(string='Distance (km)')
    transit_days = fields.Integer(string='Transit Days')
    active = fields.Boolean(default=True)
    corridor = fields.Selection([
        ('central', 'Central Corridor'),
        ('northern', 'Northern Corridor'),
        ('southern', 'Southern Corridor'),
        ('lake', 'Lake Corridor'),
        ('tanga', 'Tanga Corridor'),
    ], string='Corridor')
    toll_cost = fields.Float(string='Toll Cost (TZS)')
    waypoint_sequence = fields.Char(
        string='Waypoint Sequence',
        help='Comma-separated intermediate stops, e.g. "Morogoro, Dodoma, Tabora"')
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Route code must be unique!'),
    ]
