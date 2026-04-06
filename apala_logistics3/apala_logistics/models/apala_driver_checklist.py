# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ApalaDriverChecklist(models.Model):
    _name = 'apala.driver.checklist'
    _description = 'Driver Vehicle Checklist'
    _order = 'datetime desc'

    name = fields.Char(
        string='Checklist Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'),
    )
    checklist_type = fields.Selection([
        ('pre_trip', 'Pre-Trip'),
        ('post_trip', 'Post-Trip'),
    ], string='Checklist Type', required=True, default='pre_trip')

    trip_id = fields.Many2one('apala.trip', string='Trip')
    vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehicle', required=True,
    )
    driver_id = fields.Many2one(
        'hr.employee', string='Driver', required=True,
        domain=[('is_driver', '=', True)],
    )
    datetime = fields.Datetime(
        string='Date / Time', required=True,
        default=fields.Datetime.now,
    )

    # ── Check Items (Boolean + Note pairs) ───────────────────────────────
    engine_ok = fields.Boolean(string='Engine OK', default=True)
    engine_note = fields.Char(string='Engine Notes')

    brakes_ok = fields.Boolean(string='Brakes OK', default=True)
    brakes_note = fields.Char(string='Brakes Notes')

    tyres_ok = fields.Boolean(string='Tyres OK', default=True)
    tyres_note = fields.Char(string='Tyres Notes')

    lights_ok = fields.Boolean(string='Lights OK', default=True)
    lights_note = fields.Char(string='Lights Notes')

    fuel_level = fields.Selection([
        ('full', 'Full'),
        ('three_quarter', '3/4'),
        ('half', '1/2'),
        ('quarter', '1/4'),
        ('low', 'Low'),
    ], string='Fuel Level', default='half')

    oil_level_ok = fields.Boolean(string='Oil Level OK', default=True)
    coolant_ok = fields.Boolean(string='Coolant OK', default=True)
    body_damage = fields.Boolean(string='Body Damage Found')
    body_damage_desc = fields.Text(string='Body Damage Description')
    documents_ok = fields.Boolean(string='Documents OK', default=True)
    fire_extinguisher = fields.Boolean(
        string='Fire Extinguisher Present', default=True,
    )

    # ── Computed ─────────────────────────────────────────────────────────
    vehicle_fit_for_dispatch = fields.Boolean(
        string='Vehicle Fit for Dispatch',
        compute='_compute_vehicle_fit', store=True,
    )
    issues_found = fields.Text(
        string='Issues Found',
        compute='_compute_issues_found', store=True,
    )
    signature = fields.Char(string='Driver Signature')

    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    # ── Computes ─────────────────────────────────────────────────────────
    @api.depends('engine_ok', 'brakes_ok', 'tyres_ok', 'lights_ok',
                 'oil_level_ok', 'coolant_ok', 'documents_ok',
                 'fire_extinguisher')
    def _compute_vehicle_fit(self):
        for rec in self:
            rec.vehicle_fit_for_dispatch = all([
                rec.engine_ok, rec.brakes_ok, rec.tyres_ok,
                rec.lights_ok, rec.oil_level_ok, rec.coolant_ok,
                rec.documents_ok, rec.fire_extinguisher,
            ])

    @api.depends('engine_ok', 'brakes_ok', 'tyres_ok', 'lights_ok',
                 'oil_level_ok', 'coolant_ok', 'documents_ok',
                 'fire_extinguisher', 'body_damage',
                 'engine_note', 'brakes_note', 'tyres_note', 'lights_note',
                 'body_damage_desc')
    def _compute_issues_found(self):
        check_fields = [
            ('engine_ok', 'Engine', 'engine_note'),
            ('brakes_ok', 'Brakes', 'brakes_note'),
            ('tyres_ok', 'Tyres', 'tyres_note'),
            ('lights_ok', 'Lights', 'lights_note'),
            ('oil_level_ok', 'Oil Level', False),
            ('coolant_ok', 'Coolant', False),
            ('documents_ok', 'Documents', False),
            ('fire_extinguisher', 'Fire Extinguisher', False),
        ]
        for rec in self:
            issues = []
            for field_name, label, note_field in check_fields:
                if not rec[field_name]:
                    note = rec[note_field] if note_field else ''
                    issues.append(
                        '%s: FAIL%s' % (label, ' — %s' % note if note else ''))
            if rec.body_damage:
                issues.append(
                    'Body Damage: %s' % (rec.body_damage_desc or 'Yes'))
            rec.issues_found = '\n'.join(issues) if issues else False

    # ── Sequence ─────────────────────────────────────────────────────────
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'apala.driver.checklist') or _('New')
        result = super().create(vals)
        # Auto-create job card if any critical check fails
        for rec in result:
            if not rec.vehicle_fit_for_dispatch and rec.issues_found:
                self.env['apala.vehicle.job.card'].create({
                    'vehicle_id': rec.vehicle_id.id,
                    'driver_id': rec.driver_id.id,
                    'reported_problem': _(
                        'Issues found during %s checklist %s:\n%s'
                    ) % (
                        dict(rec._fields['checklist_type'].selection).get(
                            rec.checklist_type, ''),
                        rec.name,
                        rec.issues_found,
                    ),
                    'date_opened': fields.Datetime.now(),
                    'entry_datetime': fields.Datetime.now(),
                })
        return result

    def action_create_job_card(self):
        """Manually create a job card from a checklist with failed items."""
        self.ensure_one()
        problem = _(
            'Issues found during %s checklist %s:\n%s'
        ) % (
            dict(self._fields['checklist_type'].selection).get(
                self.checklist_type, ''),
            self.name,
            self.issues_found or 'See checklist for details',
        )
        job_card = self.env['apala.vehicle.job.card'].create({
            'vehicle_id': self.vehicle_id.id,
            'driver_id': self.driver_id.id,
            'reported_problem': problem,
            'date_opened': fields.Datetime.now(),
            'entry_datetime': fields.Datetime.now(),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'apala.vehicle.job.card',
            'res_id': job_card.id,
            'view_mode': 'form',
            'target': 'current',
        }
