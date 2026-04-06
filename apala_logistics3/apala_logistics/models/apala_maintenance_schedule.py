# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class ApalaMaintenanceSchedule(models.Model):
    _name = 'apala.maintenance.schedule'
    _description = 'Vehicle Maintenance Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'next_service_date asc'

    # ── Identification ───────────────────────────────────────────────────
    name = fields.Char(string='Description', required=True)
    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehicle', required=True, tracking=True,
    )
    maintenance_type = fields.Selection([
        ('routine_service', 'Routine Service'),
        ('oil_change', 'Oil Change'),
        ('tyre_rotation', 'Tyre Rotation'),
        ('brake_inspection', 'Brake Inspection'),
        ('full_service', 'Full Service'),
        ('annual_inspection', 'Annual Inspection'),
        ('other', 'Other'),
    ], string='Maintenance Type', required=True, tracking=True)

    # ── Intervals ────────────────────────────────────────────────────────
    interval_km = fields.Integer(string='Interval (km)')
    interval_days = fields.Integer(string='Interval (days)')
    last_service_km = fields.Float(string='Last Service (km)')
    last_service_date = fields.Date(string='Last Service Date')

    # ── Computed ─────────────────────────────────────────────────────────
    next_service_km = fields.Float(
        string='Next Service (km)',
        compute='_compute_next_service', store=True,
    )
    next_service_date = fields.Date(
        string='Next Service Date',
        compute='_compute_next_service', store=True,
    )
    km_remaining = fields.Float(
        string='Km Remaining',
        compute='_compute_remaining', store=True,
    )
    days_remaining = fields.Integer(
        string='Days Remaining',
        compute='_compute_remaining', store=True,
    )

    # ── Status ───────────────────────────────────────────────────────────
    state = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('overdue', 'Overdue'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
    ], string='Status', default='scheduled', tracking=True, copy=False)

    # ── Relations ────────────────────────────────────────────────────────
    job_card_id = fields.Many2one(
        'apala.vehicle.job.card', string='Job Card',
    )
    notes = fields.Text(string='Notes')
    responsible_id = fields.Many2one(
        'hr.employee', string='Responsible Person',
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    # ── Computes ─────────────────────────────────────────────────────────
    @api.depends('last_service_km', 'interval_km',
                 'last_service_date', 'interval_days')
    def _compute_next_service(self):
        for rec in self:
            rec.next_service_km = (
                (rec.last_service_km + rec.interval_km)
                if rec.interval_km else 0.0
            )
            rec.next_service_date = (
                (rec.last_service_date + relativedelta(days=rec.interval_days))
                if rec.last_service_date and rec.interval_days else False
            )

    @api.depends('next_service_km', 'next_service_date',
                 'vehicle_id', 'vehicle_id.odometer')
    def _compute_remaining(self):
        today = fields.Date.today()
        for rec in self:
            if rec.next_service_km and rec.vehicle_id:
                current_odo = rec.vehicle_id.odometer or 0.0
                rec.km_remaining = rec.next_service_km - current_odo
            else:
                rec.km_remaining = 0.0

            if rec.next_service_date:
                delta = rec.next_service_date - today
                rec.days_remaining = delta.days
            else:
                rec.days_remaining = 0

    # ── Constraints ──────────────────────────────────────────────────────
    @api.constrains('interval_km', 'interval_days')
    def _check_interval(self):
        for rec in self:
            if not rec.interval_km and not rec.interval_days:
                raise ValidationError(
                    _('You must set either Interval (km) or '
                      'Interval (days) for the maintenance schedule.'))

    # ── Cron ─────────────────────────────────────────────────────────────
    @api.model
    def apala_check_maintenance_due(self):
        """Cron: find schedules where km_remaining < 500 or days < 7 and
        post an activity reminder."""
        schedules = self.search([
            ('state', '=', 'scheduled'),
        ])
        for sched in schedules:
            sched._compute_remaining()
            due = False
            summary_parts = []
            if sched.interval_km and sched.km_remaining < 500:
                due = True
                summary_parts.append(
                    _('%.0f km remaining') % sched.km_remaining)
            if sched.interval_days and sched.days_remaining < 7:
                due = True
                summary_parts.append(
                    _('%d days remaining') % sched.days_remaining)
            if due:
                if sched.days_remaining < 0 or sched.km_remaining < 0:
                    sched.state = 'overdue'
                sched.activity_schedule(
                    'mail.mail_activity_data_warning',
                    date_deadline=sched.next_service_date
                    or fields.Date.today(),
                    summary=_('Maintenance due for %s: %s') % (
                        sched.vehicle_id.name,
                        ', '.join(summary_parts)),
                )

    # ── Actions ──────────────────────────────────────────────────────────
    def action_create_job_card(self):
        """Create a vehicle job card from this maintenance schedule."""
        self.ensure_one()
        job_card = self.env['apala.vehicle.job.card'].create({
            'vehicle_id': self.vehicle_id.id,
            'reported_problem': _('Scheduled maintenance: %s — %s') % (
                self.name,
                dict(self._fields['maintenance_type'].selection).get(
                    self.maintenance_type, ''),
            ),
            'date_opened': fields.Datetime.now(),
            'entry_datetime': fields.Datetime.now(),
        })
        self.write({
            'job_card_id': job_card.id,
            'state': 'in_progress',
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'apala.vehicle.job.card',
            'res_id': job_card.id,
            'view_mode': 'form',
            'target': 'current',
        }
