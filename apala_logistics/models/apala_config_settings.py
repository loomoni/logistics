# -*- coding: utf-8 -*-
from odoo import models, fields


class ApalaConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Operational defaults
    default_currency_id = fields.Many2one(
        'res.currency', string='Default Currency',
        default_model='apala.transport.order')
    apala_default_route_id = fields.Many2one(
        'apala.route', string='Default Route',
        config_parameter='apala_logistics.default_route_id')
    apala_licence_alert_days = fields.Integer(
        string='Driver Licence Alert (days before expiry)',
        config_parameter='apala_logistics.licence_alert_days',
        default=30)
    apala_trip_overdue_hours = fields.Integer(
        string='Trip Overdue Threshold (hours)',
        config_parameter='apala_logistics.trip_overdue_hours',
        default=2)
    apala_auto_send_confirmation = fields.Boolean(
        string='Auto-send order confirmation email',
        config_parameter='apala_logistics.auto_send_confirmation',
        default=True)
    apala_company_tin = fields.Char(
        string='Company TIN Number',
        config_parameter='apala_logistics.company_tin')
    apala_company_vrn = fields.Char(
        string='Company VRN Number',
        config_parameter='apala_logistics.company_vrn')
