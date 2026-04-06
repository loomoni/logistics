# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta


class ApalaCustomerCredit(models.Model):
    _name = 'apala.customer.credit'
    _description = 'Customer Credit Management'
    _inherit = ['mail.thread']

    partner_id = fields.Many2one(
        'res.partner', string='Customer', required=True, tracking=True,
    )
    credit_limit = fields.Monetary(
        string='Credit Limit', tracking=True,
        currency_field='currency_id',
    )
    credit_days = fields.Integer(string='Credit Days', default=30)
    risk_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ], string='Risk Level', default='low', tracking=True)
    credit_status = fields.Selection([
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('blocked', 'Blocked'),
    ], string='Credit Status', default='active', tracking=True)

    # ── Aging Buckets (computed) ─────────────────────────────────────────
    outstanding_balance = fields.Monetary(
        string='Outstanding Balance',
        compute='_compute_aging_buckets', store=True,
        currency_field='currency_id',
    )
    credit_used_pct = fields.Float(
        string='Credit Used (%)',
        compute='_compute_aging_buckets', store=True,
    )
    invoices_0_30 = fields.Monetary(
        string='0-30 Days',
        compute='_compute_aging_buckets', store=True,
        currency_field='currency_id',
    )
    invoices_31_60 = fields.Monetary(
        string='31-60 Days',
        compute='_compute_aging_buckets', store=True,
        currency_field='currency_id',
    )
    invoices_61_90 = fields.Monetary(
        string='61-90 Days',
        compute='_compute_aging_buckets', store=True,
        currency_field='currency_id',
    )
    invoices_90_plus = fields.Monetary(
        string='90+ Days',
        compute='_compute_aging_buckets', store=True,
        currency_field='currency_id',
    )

    # ── Last Payment (computed) ──────────────────────────────────────────
    last_payment_date = fields.Date(
        string='Last Payment Date',
        compute='_compute_last_payment', store=True,
    )
    last_payment_amount = fields.Monetary(
        string='Last Payment Amount',
        compute='_compute_last_payment', store=True,
        currency_field='currency_id',
    )

    # ── Other ────────────────────────────────────────────────────────────
    notes = fields.Text(string='Notes')
    reviewed_by = fields.Many2one('hr.employee', string='Reviewed By')
    reviewed_date = fields.Date(string='Review Date')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        ('partner_uniq', 'unique(partner_id, company_id)',
         'A credit record already exists for this customer in this company.'),
    ]

    # ── Aging Computation ────────────────────────────────────────────────
    @api.depends('partner_id')
    def _compute_aging_buckets(self):
        today = fields.Date.today()
        AccountMove = self.env['account.move']
        for rec in self:
            if not rec.partner_id:
                rec.outstanding_balance = 0
                rec.credit_used_pct = 0
                rec.invoices_0_30 = 0
                rec.invoices_31_60 = 0
                rec.invoices_61_90 = 0
                rec.invoices_90_plus = 0
                continue

            invoices = AccountMove.search([
                ('partner_id', '=', rec.partner_id.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ['not_paid', 'partial']),
            ])
            bucket_0_30 = 0.0
            bucket_31_60 = 0.0
            bucket_61_90 = 0.0
            bucket_90_plus = 0.0

            for inv in invoices:
                age = (today - inv.invoice_date).days if inv.invoice_date else 0
                residual = inv.amount_residual
                if age <= 30:
                    bucket_0_30 += residual
                elif age <= 60:
                    bucket_31_60 += residual
                elif age <= 90:
                    bucket_61_90 += residual
                else:
                    bucket_90_plus += residual

            total = bucket_0_30 + bucket_31_60 + bucket_61_90 + bucket_90_plus
            rec.invoices_0_30 = bucket_0_30
            rec.invoices_31_60 = bucket_31_60
            rec.invoices_61_90 = bucket_61_90
            rec.invoices_90_plus = bucket_90_plus
            rec.outstanding_balance = total
            rec.credit_used_pct = (
                (total / rec.credit_limit * 100)
                if rec.credit_limit else 0.0
            )

    @api.depends('partner_id')
    def _compute_last_payment(self):
        AccountPayment = self.env['account.payment']
        for rec in self:
            if not rec.partner_id:
                rec.last_payment_date = False
                rec.last_payment_amount = 0
                continue
            payment = AccountPayment.search([
                ('partner_id', '=', rec.partner_id.id),
                ('payment_type', '=', 'inbound'),
                ('state', '=', 'posted'),
            ], order='date desc', limit=1)
            rec.last_payment_date = payment.date if payment else False
            rec.last_payment_amount = payment.amount if payment else 0.0

    # ── Actions ──────────────────────────────────────────────────────────
    def action_suspend(self):
        for rec in self:
            rec.credit_status = 'suspended'

    def action_block(self):
        for rec in self:
            rec.credit_status = 'blocked'

    def action_activate(self):
        for rec in self:
            rec.credit_status = 'active'

    # ── Cron ─────────────────────────────────────────────────────────────
    @api.model
    def apala_refresh_aging(self):
        """Cron: recompute aging buckets for all credit records and flag
        customers with 90+ day invoices."""
        records = self.search([])
        # Trigger recompute on stored computed fields
        records._compute_aging_buckets()
        records._compute_last_payment()

        for rec in records:
            if rec.invoices_90_plus > 0:
                rec.activity_schedule(
                    'mail.mail_activity_data_warning',
                    date_deadline=fields.Date.today(),
                    summary=_('Customer %s has overdue invoices (90+ days): '
                              '%s %s') % (
                        rec.partner_id.name,
                        rec.currency_id.symbol or '',
                        '{:,.0f}'.format(rec.invoices_90_plus),
                    ),
                )
                # Auto-escalate risk level
                if rec.risk_level != 'high':
                    rec.risk_level = 'high'
