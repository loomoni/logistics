# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ApalaDailyVehicleStatus(models.Model):
    _name = 'apala.daily.vehicle.status'
    _description = 'Daily Vehicle Status Report (DVSR)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'report_date desc'

    # ── Header ───────────────────────────────────────────────────────────
    name = fields.Char(
        string='DVSR Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'),
    )
    report_date = fields.Date(
        string='Report Date', required=True,
        default=fields.Date.today, tracking=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
    ], string='Status', default='draft', tracking=True, copy=False)

    prepared_by = fields.Many2one(
        'hr.employee', string='Prepared By', required=True, tracking=True,
    )
    approved_by = fields.Many2one(
        'hr.employee', string='Approved By', tracking=True,
    )

    # ── Summary (computed) ───────────────────────────────────────────────
    total_fleet_size = fields.Integer(
        string='Total Fleet Size',
        compute='_compute_summary', store=True,
    )
    vehicles_operational = fields.Integer(
        string='Vehicles Operational',
        compute='_compute_summary', store=True,
    )
    vehicles_ready = fields.Integer(
        string='Vehicles Ready',
        compute='_compute_summary', store=True,
    )
    vehicles_minor_pm = fields.Integer(
        string='Vehicles Minor PM',
        compute='_compute_summary', store=True,
    )
    vehicles_major = fields.Integer(
        string='Vehicles Major Breakdown',
        compute='_compute_summary', store=True,
    )
    vehicles_awaiting = fields.Integer(
        string='Vehicles Awaiting Parts',
        compute='_compute_summary', store=True,
    )

    # ── Lines ────────────────────────────────────────────────────────────
    line_ids = fields.One2many(
        'apala.dvsr.vehicle.line', 'dvsr_id',
        string='Vehicle Lines',
    )

    # ── Other ────────────────────────────────────────────────────────────
    critical_blockers = fields.Text(string='Critical Blockers')
    job_card_ids = fields.Many2many(
        'apala.vehicle.job.card', string='Related Job Cards',
    )
    job_card_count = fields.Integer(
        string='Job Card Count',
        compute='_compute_job_card_count',
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    # ── Computes ─────────────────────────────────────────────────────────
    @api.depends(
        'line_ids', 'line_ids.status',
    )
    def _compute_summary(self):
        for rec in self:
            lines = rec.line_ids
            rec.total_fleet_size = len(lines)
            rec.vehicles_ready = len(
                lines.filtered(lambda l: l.status == 'ready'))
            rec.vehicles_minor_pm = len(
                lines.filtered(lambda l: l.status == 'minor_pm'))
            rec.vehicles_major = len(
                lines.filtered(lambda l: l.status == 'major_breakdown'))
            rec.vehicles_awaiting = len(
                lines.filtered(lambda l: l.status == 'awaiting_parts'))
            rec.vehicles_operational = rec.vehicles_ready

    @api.depends('job_card_ids')
    def _compute_job_card_count(self):
        for rec in self:
            rec.job_card_count = len(rec.job_card_ids)

    # ── Sequence ─────────────────────────────────────────────────────────
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'apala.daily.vehicle.status') or _('New')
        return super().create(vals)

    # ── Actions ──────────────────────────────────────────────────────────
    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(
                    _('Only draft reports can be submitted.'))
            rec.state = 'submitted'

    def action_approve(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(
                    _('Only submitted reports can be approved.'))
            rec.state = 'approved'

    # ── Cron ─────────────────────────────────────────────────────────────
    @api.model
    def apala_auto_generate_dvsr(self):
        """Cron: auto-generate a draft DVSR from current fleet status."""
        vehicles = self.env['fleet.vehicle'].search([
            ('active', '=', True),
        ])
        if not vehicles:
            return

        # Find a default preparer (first fleet manager or current user employee)
        preparer = self.env['hr.employee'].search([
            ('user_id', '=', self.env.uid),
        ], limit=1)

        dvsr = self.create({
            'report_date': fields.Date.today(),
            'prepared_by': preparer.id if preparer else False,
        })

        # Populate vehicle lines from active fleet
        open_job_cards = self.env['apala.vehicle.job.card'].search([
            ('state', 'not in', ['dispatched', 'cancelled']),
        ])
        jc_vehicle_map = {}
        for jc in open_job_cards:
            jc_vehicle_map[jc.vehicle_id.id] = jc

        line_vals = []
        for vehicle in vehicles:
            jc = jc_vehicle_map.get(vehicle.id)
            if jc:
                state_map = {
                    'draft': 'awaiting_parts',
                    'in_progress': 'major_breakdown',
                    'quality_check': 'minor_pm',
                    'completed': 'ready',
                }
                status = state_map.get(jc.state, 'ready')
                line_vals.append((0, 0, {
                    'vehicle_id': vehicle.id,
                    'status': status,
                    'job_card_id': jc.id,
                    'days_in_garage': jc.days_in_garage,
                    'reason_for_stay': jc.reported_problem[:80]
                    if jc.reported_problem else '',
                }))
            else:
                line_vals.append((0, 0, {
                    'vehicle_id': vehicle.id,
                    'status': 'ready',
                }))

        dvsr.write({
            'line_ids': line_vals,
            'job_card_ids': [(6, 0, open_job_cards.ids)],
        })
        return dvsr


class ApalaDvsrVehicleLine(models.Model):
    _name = 'apala.dvsr.vehicle.line'
    _description = 'DVSR Vehicle Line'

    dvsr_id = fields.Many2one(
        'apala.daily.vehicle.status', string='DVSR',
        required=True, ondelete='cascade',
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehicle', required=True,
    )
    status = fields.Selection([
        ('ready', 'Ready'),
        ('minor_pm', 'Minor PM'),
        ('major_breakdown', 'Major Breakdown'),
        ('awaiting_parts', 'Awaiting Parts'),
    ], string='Status', default='ready', required=True)
    reason_for_stay = fields.Char(string='Reason for Stay')
    days_in_garage = fields.Integer(string='Days in Garage')
    etc = fields.Date(string='Estimated Time of Completion')
    bottleneck = fields.Char(string='Bottleneck')
    job_card_id = fields.Many2one(
        'apala.vehicle.job.card', string='Job Card',
    )
    impact_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], string='Impact Level', default='low')
