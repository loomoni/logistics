# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ApalaTrip(models.Model):
    _name = 'apala.trip'
    _description = 'Trip Execution'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Trip Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'),
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('dispatched', 'Dispatched'),
        ('en_route', 'En Route'),
        ('arrived', 'Arrived'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True, copy=False)
    transport_order_id = fields.Many2one('apala.transport.order', string='Transport Order')
    transport_order_ids = fields.Many2many('apala.transport.order', string='Transport Orders')
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', required=True, tracking=True)
    driver_id = fields.Many2one('hr.employee', string='Driver', tracking=True)
    co_driver_id = fields.Many2one('hr.employee', string='Co-Driver')
    route_id = fields.Many2one('apala.route', string='Route')
    departure_date = fields.Datetime(string='Departure Date')
    arrival_date = fields.Datetime(string='Arrival Date (Actual)', tracking=True)
    estimated_arrival = fields.Datetime(string='Estimated Arrival')
    odometer_start = fields.Float(string='Odometer Start (km)')
    odometer_end = fields.Float(string='Odometer End (km)')
    distance_km = fields.Float(string='Distance (km)', compute='_compute_distance_km', store=True)
    fuel_consumed_l = fields.Float(string='Fuel Consumed (litres)')
    expense_ids = fields.One2many('apala.trip.expense', 'trip_id', string='Trip Expenses')
    total_expenses = fields.Float(string='Total Expenses', compute='_compute_total_expenses', store=True)
    purchase_order_id = fields.Many2one('purchase.order', string='Subcontractor PO')
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    # Waypoints
    waypoint_ids = fields.One2many('apala.trip.waypoint', 'trip_id', string='Waypoints')
    # Cash advance & reconciliation
    cash_advance_amount = fields.Float(string='Cash Advance Given (TZS)')
    cash_advance_date = fields.Date(string='Cash Advance Date')
    cash_advance_issued_by = fields.Many2one('hr.employee', string='Advance Issued By')
    cash_returned_amount = fields.Float(string='Cash Returned by Driver (TZS)')
    advance_reconciled = fields.Boolean(string='Advance Reconciled', default=False)
    advance_balance = fields.Float(
        string='Advance Balance (TZS)',
        compute='_compute_advance_balance', store=True,
        help='Positive = driver owes company, Negative = company owes driver')
    # Fuel & Checklists
    pre_trip_checklist_id = fields.Many2one('apala.driver.checklist', string='Pre-Trip Checklist')
    post_trip_checklist_id = fields.Many2one('apala.driver.checklist', string='Post-Trip Checklist')
    fuel_log_ids = fields.One2many('apala.fuel.log', 'trip_id', string='Fuel Logs')
    fuel_cost_total = fields.Float(
        string='Total Fuel Cost', compute='_compute_fuel_cost', store=True)
    cost_per_km = fields.Float(
        string='Cost per km', compute='_compute_cost_per_km')
    notes = fields.Text(string='Notes')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments (POD)')

    @api.depends('odometer_end', 'odometer_start')
    def _compute_distance_km(self):
        for rec in self:
            rec.distance_km = rec.odometer_end - rec.odometer_start if rec.odometer_end else 0.0

    @api.depends('expense_ids.amount')
    def _compute_total_expenses(self):
        for rec in self:
            rec.total_expenses = sum(rec.expense_ids.mapped('amount'))

    @api.depends('cash_advance_amount', 'total_expenses', 'cash_returned_amount')
    def _compute_advance_balance(self):
        for rec in self:
            rec.advance_balance = rec.cash_advance_amount - rec.total_expenses - rec.cash_returned_amount

    @api.depends('fuel_log_ids.total_cost')
    def _compute_fuel_cost(self):
        for rec in self:
            rec.fuel_cost_total = sum(rec.fuel_log_ids.mapped('total_cost'))

    @api.depends('total_expenses', 'fuel_cost_total', 'distance_km')
    def _compute_cost_per_km(self):
        for rec in self:
            total = rec.total_expenses + rec.fuel_cost_total
            rec.cost_per_km = total / rec.distance_km if rec.distance_km else 0

    @api.constrains('odometer_end', 'odometer_start')
    def _check_odometer(self):
        for rec in self:
            if rec.odometer_end and rec.odometer_end < rec.odometer_start:
                raise ValidationError(_('Odometer end reading cannot be less than start reading.'))

    @api.constrains('vehicle_id', 'state')
    def _check_vehicle_double_booking(self):
        for rec in self:
            if rec.state in ('dispatched', 'en_route') and rec.vehicle_id:
                conflict = self.search([
                    ('vehicle_id', '=', rec.vehicle_id.id),
                    ('state', 'in', ['dispatched', 'en_route']),
                    ('id', '!=', rec.id),
                ], limit=1)
                if conflict:
                    raise ValidationError(_(
                        'Vehicle %s is already assigned to active trip %s. '
                        'Close or cancel that trip before dispatching this one.'
                    ) % (rec.vehicle_id.name, conflict.name))

    @api.constrains('driver_id', 'state')
    def _check_driver_documents(self):
        for rec in self:
            if rec.state == 'dispatched' and rec.driver_id:
                today = fields.Date.today()
                warn_date = today + timedelta(days=30)
                # Licence expiry check
                if rec.driver_id.licence_expiry:
                    if rec.driver_id.licence_expiry < today:
                        raise ValidationError(_(
                            "Driver %s's licence (class %s) expired on %s. "
                            "Update HR records before dispatch."
                        ) % (rec.driver_id.name, rec.driver_id.licence_class or '-',
                             rec.driver_id.licence_expiry))
                    elif rec.driver_id.licence_expiry < warn_date:
                        rec.message_post(body=_(
                            "Warning: Driver %s's licence expires on %s (within 30 days)."
                        ) % (rec.driver_id.name, rec.driver_id.licence_expiry))
                # Medical cert expiry check
                if rec.driver_id.medical_cert_expiry:
                    if rec.driver_id.medical_cert_expiry < today:
                        raise ValidationError(_(
                            "Driver %s's medical certificate expired on %s. "
                            "Update HR records before dispatch."
                        ) % (rec.driver_id.name, rec.driver_id.medical_cert_expiry))
                    elif rec.driver_id.medical_cert_expiry < warn_date:
                        rec.message_post(body=_(
                            "Warning: Driver %s's medical certificate expires on %s (within 30 days)."
                        ) % (rec.driver_id.name, rec.driver_id.medical_cert_expiry))

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('apala.trip') or _('New')
        trip = super().create(vals)
        # Auto-create analytic account for the trip
        if not trip.analytic_account_id:
            route_name = trip.route_id.name if trip.route_id else ''
            analytic = self.env['account.analytic.account'].create({
                'name': '%s – %s' % (trip.name, route_name),
                'company_id': self.env.company.id,
            })
            trip.analytic_account_id = analytic.id
        return trip

    def action_dispatch(self):
        """Dispatch the trip — update status and log departure."""
        for rec in self:
            if not rec.driver_id:
                raise UserError(_('Please assign a driver before dispatching.'))
            rec.state = 'dispatched'
            rec.departure_date = fields.Datetime.now()
            rec.message_post(body=_('Trip dispatched. Vehicle: %s, Driver: %s') % (
                rec.vehicle_id.name, rec.driver_id.name))
            # Update fleet vehicle odometer
            if rec.odometer_start:
                self.env['fleet.vehicle.odometer'].create({
                    'vehicle_id': rec.vehicle_id.id,
                    'value': rec.odometer_start,
                    'date': fields.Date.today(),
                })
            # Send dispatch email to customers
            template = self.env.ref(
                'apala_logistics.email_template_trip_dispatched', raise_if_not_found=False)
            if template:
                try:
                    template.send_mail(rec.id, force_send=True)
                except Exception:
                    pass

    def action_en_route(self):
        """Mark trip as en route."""
        for rec in self:
            rec.state = 'en_route'

    def action_arrive(self):
        """Mark trip as arrived and compute distance."""
        for rec in self:
            rec.state = 'arrived'
            rec.arrival_date = fields.Datetime.now()
            rec.message_post(body=_('Trip arrived. Distance: %.1f km') % rec.distance_km)

    def action_close(self):
        """Open the trip close wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'apala.trip.close.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_trip_id': self.id,
                'default_odometer_end': self.odometer_end,
                'default_fuel_consumed_l': self.fuel_consumed_l,
            },
        }

    def action_reconcile_advance(self):
        """Reconcile the cash advance for this trip."""
        self.ensure_one()
        if abs(self.advance_balance) < 0.01:
            self.advance_reconciled = True
            self.message_post(body=_('Cash advance reconciled. Balance is zero.'))
        elif self.advance_balance > 0:
            # Driver owes company
            self.message_post(body=_(
                'Driver owes company TZS %s. Please arrange deduction or recovery.'
            ) % '{:,.2f}'.format(self.advance_balance))
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Recover cash advance balance of TZS %s from driver') %
                        '{:,.2f}'.format(self.advance_balance),
            )
            self.advance_reconciled = True
        else:
            # Company owes driver
            employee = self.driver_id
            if employee:
                product = self.env.ref('hr_expense.product_product_fixed_cost',
                                       raise_if_not_found=False)
                self.env['hr.expense'].create({
                    'name': _('Advance shortfall – %s') % self.name,
                    'employee_id': employee.id,
                    'product_id': product.id if product else False,
                    'unit_amount': abs(self.advance_balance),
                    'date': fields.Date.today(),
                    'analytic_account_id': self.analytic_account_id.id
                    if self.analytic_account_id else False,
                })
            self.advance_reconciled = True
            self.message_post(body=_(
                'Company owes driver TZS %s. HR expense created for reimbursement.'
            ) % '{:,.2f}'.format(abs(self.advance_balance)))

    @api.onchange('route_id')
    def _onchange_route_id_waypoints(self):
        """Auto-populate waypoints from route waypoint_sequence."""
        if self.route_id and self.route_id.waypoint_sequence:
            new_waypoints = []
            locations = [s.strip() for s in self.route_id.waypoint_sequence.split(',') if s.strip()]
            for seq, loc in enumerate(locations, start=1):
                new_waypoints.append((0, 0, {
                    'sequence': seq * 10,
                    'location': loc,
                }))
            self.waypoint_ids = [(5, 0, 0)] + new_waypoints

    @api.model
    def apala_check_overdue_trips(self):
        """Cron: find overdue trips and post warnings."""
        overdue_hours = int(self.env['ir.config_parameter'].sudo().get_param(
            'apala_logistics.trip_overdue_hours', '2'))
        cutoff = fields.Datetime.now() - timedelta(hours=overdue_hours)
        trips = self.search([
            ('state', 'in', ['dispatched', 'en_route']),
            ('estimated_arrival', '<', cutoff),
        ])
        for trip in trips:
            trip.message_post(body=_(
                'Warning: Trip is overdue — estimated arrival was %s. '
                'Please contact driver or update arrival estimate.'
            ) % trip.estimated_arrival)
            trip.activity_schedule(
                'mail.mail_activity_data_warning',
                summary=_('Trip overdue — estimated arrival was %s') % trip.estimated_arrival,
            )

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values:
            return self.env.ref('mail.mt_note')
        return super()._track_subtype(init_values)


class ApalaTripWaypoint(models.Model):
    _name = 'apala.trip.waypoint'
    _description = 'Trip Waypoint / Intermediate Stop'
    _order = 'sequence'

    trip_id = fields.Many2one('apala.trip', string='Trip', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    location = fields.Char(string='Location', required=True)
    planned_arrival = fields.Datetime(string='Planned Arrival')
    actual_arrival = fields.Datetime(string='Actual Arrival')
    planned_depart = fields.Datetime(string='Planned Departure')
    actual_depart = fields.Datetime(string='Actual Departure')
    odometer = fields.Float(string='Odometer (km)')
    stop_type = fields.Selection([
        ('fuel', 'Fuel Stop'),
        ('delivery', 'Partial Delivery'),
        ('pickup', 'Pickup'),
        ('rest', 'Driver Rest'),
        ('checkpoint', 'Police Checkpoint'),
        ('other', 'Other'),
    ], string='Stop Type')
    notes = fields.Text(string='Notes')
