# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta


class ApalaStorageContract(models.Model):
    _name = 'apala.storage.contract'
    _description = 'Warehouse / Storage Contract'
    _inherit = ['mail.thread']
    _order = 'name desc'

    name = fields.Char(
        string='Contract Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'),
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
    ], string='Status', default='draft', tracking=True)
    customer_id = fields.Many2one('res.partner', string='Customer', required=True)
    start_date = fields.Date(string='Start Date')
    end_date = fields.Date(string='End Date')
    storage_type = fields.Selection([
        ('general', 'General'),
        ('cold_chain', 'Cold Chain'),
        ('hazardous', 'Hazardous'),
        ('bonded', 'Bonded Warehouse'),
    ], string='Storage Type', default='general')
    allocated_m2 = fields.Float(string='Allocated Area (m²)')
    allocated_m3 = fields.Float(string='Allocated Volume (m³)')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    daily_rate = fields.Monetary(string='Daily Rate per m³ (TZS)')
    handling_rate = fields.Monetary(string='Handling Rate per Event (TZS)')
    billing_cycle = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ], string='Billing Cycle', default='monthly')
    auto_renew = fields.Boolean(string='Auto Renew')
    product_id = fields.Many2one('product.product', string='Storage Service Product')
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
    invoice_ids = fields.Many2many('account.move', string='Invoices', copy=False)
    invoice_count = fields.Integer(compute='_compute_invoice_count')
    notes = fields.Text(string='Notes')

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date <= rec.start_date:
                raise ValidationError(_('Contract end date must be after start date.'))

    @api.constrains('customer_id', 'storage_type', 'state')
    def _check_unique_active_contract(self):
        for rec in self:
            if rec.state == 'active':
                conflict = self.search([
                    ('customer_id', '=', rec.customer_id.id),
                    ('storage_type', '=', rec.storage_type),
                    ('state', '=', 'active'),
                    ('id', '!=', rec.id),
                ], limit=1)
                if conflict:
                    raise ValidationError(_(
                        'An active storage contract of type "%s" already exists for customer %s (%s).'
                    ) % (rec.storage_type, rec.customer_id.name, conflict.name))

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('apala.storage.contract') or _('New')
        return super().create(vals)

    def action_activate(self):
        for rec in self:
            rec.state = 'active'

    def action_terminate(self):
        for rec in self:
            rec.state = 'terminated'

    def action_create_storage_invoice(self):
        """Create an invoice based on daily_rate * allocated_m3 * billing period days."""
        self.ensure_one()
        if not self.start_date:
            raise UserError(_('Please set a start date before invoicing.'))
        if self.billing_cycle == 'daily':
            days = 1
        elif self.billing_cycle == 'weekly':
            days = 7
        else:
            days = 30
        amount = self.daily_rate * self.allocated_m3 * days
        product = self.product_id or self.env.ref(
            'apala_logistics.product_cargo_storage_service', raise_if_not_found=False)
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer_id.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': product.id if product else False,
                'name': _('Storage – %s (%s days)') % (self.name, days),
                'quantity': 1,
                'price_unit': amount,
            })],
        })
        self.invoice_ids = [(4, invoice.id)]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_invoices(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_out_invoice_type')
        action['domain'] = [('id', 'in', self.invoice_ids.ids)]
        return action

    @api.model
    def _check_expiry(self):
        """Scheduled action: warn 7 days before contract expiry."""
        today = fields.Date.today()
        warn_date = today + relativedelta(days=7)
        contracts = self.search([
            ('state', '=', 'active'),
            ('end_date', '<=', warn_date),
            ('end_date', '>=', today),
        ])
        for contract in contracts:
            contract.message_post(
                body=_('Warning: Storage contract %s expires on %s.') % (
                    contract.name, contract.end_date),
                subject=_('Contract Expiry Warning'),
            )

    @api.model
    def apala_check_contract_expiry(self):
        """Cron: warn 7 days before contract expiry with activity and email."""
        today = fields.Date.today()
        warn_date = today + relativedelta(days=7)
        contracts = self.search([
            ('state', '=', 'active'),
            ('end_date', '<=', warn_date),
            ('end_date', '>=', today),
        ])
        template = self.env.ref(
            'apala_logistics.email_template_storage_expiry', raise_if_not_found=False)
        for contract in contracts:
            days_left = (contract.end_date - today).days
            contract.activity_schedule(
                'mail.mail_activity_data_warning',
                date_deadline=contract.end_date,
                summary=_('Storage contract expiring in %d days') % days_left,
            )
            if template and contract.customer_id.email:
                try:
                    template.send_mail(contract.id, force_send=True)
                except Exception:
                    pass

    @api.model
    def apala_auto_invoice_storage(self):
        """Cron: auto-generate monthly storage invoices on 1st of each month."""
        import calendar
        today = fields.Date.today()
        # Calculate days in previous month
        if today.month == 1:
            prev_month = 12
            prev_year = today.year - 1
        else:
            prev_month = today.month - 1
            prev_year = today.year
        days_in_prev = calendar.monthrange(prev_year, prev_month)[1]

        contracts = self.search([
            ('state', '=', 'active'),
            ('billing_cycle', '=', 'monthly'),
        ])
        for contract in contracts:
            amount = contract.daily_rate * contract.allocated_m3 * days_in_prev
            product = contract.product_id or self.env.ref(
                'apala_logistics.product_cargo_storage_service', raise_if_not_found=False)
            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': contract.customer_id.id,
                'invoice_line_ids': [(0, 0, {
                    'product_id': product.id if product else False,
                    'name': _('Storage – %s (%s/%s, %s days)') % (
                        contract.name, prev_month, prev_year, days_in_prev),
                    'quantity': 1,
                    'price_unit': amount,
                })],
            })
            contract.invoice_ids = [(4, invoice.id)]
            contract.message_post(body=_(
                'Auto-generated monthly invoice %s for %s days (TZS %s).'
            ) % (invoice.name or 'Draft', days_in_prev, '{:,.2f}'.format(amount)))
