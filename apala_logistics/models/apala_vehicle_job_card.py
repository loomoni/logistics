# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ApalaVehicleJobCard(models.Model):
    _name = 'apala.vehicle.job.card'
    _description = 'Vehicle Job Card'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_opened desc'

    # ── Header ───────────────────────────────────────────────────────────
    name = fields.Char(
        string='Job Card Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'),
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('quality_check', 'Quality Check'),
        ('completed', 'Completed'),
        ('dispatched', 'Dispatched'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False)

    date_opened = fields.Datetime(
        string='Date Opened', required=True,
        default=fields.Datetime.now,
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehicle', required=True, tracking=True,
    )
    odometer_reading = fields.Float(string='Odometer Reading (km)')
    driver_id = fields.Many2one(
        'hr.employee', string='Driver',
        domain=[('is_driver', '=', True)], tracking=True,
    )
    driver_contact = fields.Char(string='Driver Contact')
    entry_datetime = fields.Datetime(string='Entry Date/Time')

    # ── Problem ──────────────────────────────────────────────────────────
    reported_problem = fields.Text(string='Reported Problem', required=True)

    # ── Inspection ───────────────────────────────────────────────────────
    inspection_line_ids = fields.One2many(
        'apala.job.card.inspection.line', 'job_card_id',
        string='Inspection Lines',
    )
    mechanic_id = fields.Many2one(
        'hr.employee', string='Assigned Mechanic', tracking=True,
    )
    inspection_date = fields.Date(string='Inspection Date')
    estimated_repair_hours = fields.Float(string='Estimated Repair Hours')

    # ── Parts ────────────────────────────────────────────────────────────
    part_line_ids = fields.One2many(
        'apala.job.card.part.line', 'job_card_id',
        string='Parts Required',
    )
    total_parts_cost = fields.Float(
        string='Total Parts Cost',
        compute='_compute_total_parts_cost', store=True,
    )

    # ── Approval ─────────────────────────────────────────────────────────
    approved_by = fields.Many2one('hr.employee', string='Approved By')
    approval_date = fields.Date(string='Approval Date')
    approval_notes = fields.Text(string='Approval Notes')

    # ── Work Progress ────────────────────────────────────────────────────
    progress_line_ids = fields.One2many(
        'apala.job.card.progress.line', 'job_card_id',
        string='Work Progress',
    )

    # ── Quality Check ────────────────────────────────────────────────────
    test_drive_done = fields.Boolean(string='Test Drive Done')
    fault_resolved = fields.Boolean(string='Fault Resolved')
    no_leak_observed = fields.Boolean(string='No Leak Observed')
    vehicle_cleaned = fields.Boolean(string='Vehicle Cleaned')
    quality_checked_by = fields.Many2one(
        'hr.employee', string='Quality Checked By',
    )
    quality_check_date = fields.Date(string='Quality Check Date')
    completion_notes = fields.Text(string='Completion Notes')

    # ── Dispatch ─────────────────────────────────────────────────────────
    dispatch_datetime = fields.Datetime(string='Dispatch Date/Time')
    released_by = fields.Many2one('hr.employee', string='Released By')
    dispatch_status = fields.Selection([
        ('roadworthy', 'Roadworthy'),
        ('conditional', 'Conditional Release'),
        ('pending_parts', 'Pending Parts'),
    ], string='Dispatch Status')
    dispatch_remarks = fields.Text(string='Dispatch Remarks')

    # ── Computed / Relations ─────────────────────────────────────────────
    days_in_garage = fields.Integer(
        string='Days in Garage',
        compute='_compute_days_in_garage', store=True,
    )
    dvsr_id = fields.Many2one(
        'apala.daily.vehicle.status', string='DVSR',
    )
    transport_order_id = fields.Many2one(
        'apala.transport.order', string='Transport Order',
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    # ── Computes ─────────────────────────────────────────────────────────
    @api.depends('part_line_ids.total_cost')
    def _compute_total_parts_cost(self):
        for rec in self:
            rec.total_parts_cost = sum(rec.part_line_ids.mapped('total_cost'))

    @api.depends('entry_datetime', 'dispatch_datetime', 'state')
    def _compute_days_in_garage(self):
        for rec in self:
            if rec.entry_datetime:
                end = rec.dispatch_datetime or fields.Datetime.now()
                delta = end - rec.entry_datetime
                rec.days_in_garage = max(delta.days, 0)
            else:
                rec.days_in_garage = 0

    # ── Sequence ─────────────────────────────────────────────────────────
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'apala.vehicle.job.card') or _('New')
        return super().create(vals)

    # ── Actions ──────────────────────────────────────────────────────────
    def action_start(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft job cards can be started.'))
            rec.state = 'in_progress'

    def action_quality(self):
        for rec in self:
            if rec.state != 'in_progress':
                raise UserError(
                    _('Only in-progress job cards can move to quality check.'))
            rec.state = 'quality_check'

    def action_complete(self):
        for rec in self:
            if rec.state != 'quality_check':
                raise UserError(
                    _('Only job cards in quality check can be completed.'))
            rec.state = 'completed'

    def action_dispatch(self):
        for rec in self:
            if rec.state != 'completed':
                raise UserError(
                    _('Only completed job cards can be dispatched.'))
            if not any([
                rec.test_drive_done, rec.fault_resolved,
                rec.no_leak_observed, rec.vehicle_cleaned,
            ]):
                raise ValidationError(
                    _('At least one quality check must be passed before '
                      'dispatching the vehicle.'))
            rec.dispatch_datetime = fields.Datetime.now()
            rec.state = 'dispatched'
            # Create odometer log entry
            if rec.odometer_reading and rec.vehicle_id:
                self.env['fleet.vehicle.odometer'].create({
                    'vehicle_id': rec.vehicle_id.id,
                    'value': rec.odometer_reading,
                    'date': fields.Date.today(),
                    'driver_id': rec.driver_id.id if rec.driver_id else False,
                })

    def action_cancel(self):
        for rec in self:
            if rec.state == 'dispatched':
                raise UserError(
                    _('Dispatched job cards cannot be cancelled.'))
            rec.state = 'cancelled'

    # ── Constraints ──────────────────────────────────────────────────────
    @api.constrains('dispatch_datetime', 'entry_datetime')
    def _check_dates(self):
        for rec in self:
            if rec.dispatch_datetime and rec.entry_datetime:
                if rec.dispatch_datetime < rec.entry_datetime:
                    raise ValidationError(
                        _('Dispatch date cannot be earlier than the entry '
                          'date.'))

    # ── Mail Tracking ────────────────────────────────────────────────────
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values:
            return self.env.ref('mail.mt_note')
        return super()._track_subtype(init_values)


class ApalaJobCardInspectionLine(models.Model):
    _name = 'apala.job.card.inspection.line'
    _description = 'Job Card Inspection Line'

    job_card_id = fields.Many2one(
        'apala.vehicle.job.card', string='Job Card',
        required=True, ondelete='cascade',
    )
    area = fields.Selection([
        ('engine', 'Engine'),
        ('cooling_system', 'Cooling System'),
        ('electrical', 'Electrical'),
        ('brakes', 'Brakes'),
        ('suspension', 'Suspension'),
        ('tyres', 'Tyres'),
        ('body', 'Body'),
        ('other', 'Other'),
    ], string='Inspection Area', required=True)
    findings = fields.Text(string='Findings')
    action_needed = fields.Boolean(string='Action Needed')
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string='Priority', default='medium')


class ApalaJobCardPartLine(models.Model):
    _name = 'apala.job.card.part.line'
    _description = 'Job Card Part Line'

    job_card_id = fields.Many2one(
        'apala.vehicle.job.card', string='Job Card',
        required=True, ondelete='cascade',
    )
    product_id = fields.Many2one('product.product', string='Product')
    part_name = fields.Char(string='Part Name', required=True)
    quantity = fields.Float(string='Quantity', default=1.0)
    unit = fields.Selection([
        ('pieces', 'Pieces'),
        ('litres', 'Litres'),
        ('kg', 'Kg'),
        ('metres', 'Metres'),
        ('set', 'Set'),
    ], string='Unit', default='pieces')
    unit_cost = fields.Float(string='Unit Cost')
    total_cost = fields.Float(
        string='Total Cost', compute='_compute_total_cost', store=True,
    )
    sourced_from = fields.Selection([
        ('stock', 'Stock'),
        ('purchase', 'Purchase'),
        ('external', 'External'),
    ], string='Sourced From', default='stock')
    received = fields.Boolean(string='Received')

    @api.depends('quantity', 'unit_cost')
    def _compute_total_cost(self):
        for line in self:
            line.total_cost = line.quantity * line.unit_cost


class ApalaJobCardProgressLine(models.Model):
    _name = 'apala.job.card.progress.line'
    _description = 'Job Card Progress Line'
    _order = 'date asc'

    job_card_id = fields.Many2one(
        'apala.vehicle.job.card', string='Job Card',
        required=True, ondelete='cascade',
    )
    date = fields.Date(
        string='Date', required=True, default=fields.Date.today,
    )
    work_done = fields.Text(string='Work Done', required=True)
    parts_used = fields.Char(string='Parts Used')
    mechanic_id = fields.Many2one('hr.employee', string='Mechanic')
    vehicle_status = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('awaiting_parts', 'Awaiting Parts'),
        ('completed', 'Completed'),
    ], string='Vehicle Status', default='in_progress')
    remarks = fields.Text(string='Remarks')
    hours_worked = fields.Float(string='Hours Worked')
