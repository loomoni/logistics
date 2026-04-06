# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ApalaSparePartInventory(models.Model):
    _name = 'apala.spare.part'
    _description = 'Spare Part Inventory'
    _order = 'name'

    name = fields.Char(string='Part Name', required=True)
    part_code = fields.Char(string='Part Code')
    part_type = fields.Selection([
        ('engine', 'Engine'),
        ('transmission', 'Transmission'),
        ('electrical', 'Electrical'),
        ('brakes', 'Brakes'),
        ('suspension', 'Suspension'),
        ('body', 'Body'),
        ('tyres', 'Tyres'),
        ('lubricants', 'Lubricants'),
        ('filters', 'Filters'),
        ('other', 'Other'),
    ], string='Part Type', default='other')

    vehicle_ids = fields.Many2many(
        'fleet.vehicle', string='Compatible Vehicles',
    )
    uom = fields.Selection([
        ('pieces', 'Pieces'),
        ('litres', 'Litres'),
        ('kg', 'Kg'),
        ('metres', 'Metres'),
        ('set', 'Set'),
    ], string='Unit of Measure', default='pieces')

    qty_on_hand = fields.Float(string='Qty on Hand', default=0.0)
    qty_minimum = fields.Float(string='Minimum Qty', default=0.0)
    qty_on_order = fields.Float(
        string='Qty on Order',
        compute='_compute_qty_on_order', store=True,
    )
    unit_cost = fields.Float(string='Unit Cost')
    total_value = fields.Monetary(
        string='Total Value',
        compute='_compute_total_value', store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    supplier_id = fields.Many2one(
        'res.partner', string='Supplier',
        domain=[('supplier_rank', '>', 0)],
    )
    last_restocked = fields.Date(string='Last Restocked')
    location = fields.Char(string='Storage Location')
    notes = fields.Text(string='Notes')

    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    # ── Computes ─────────────────────────────────────────────────────────
    @api.depends('qty_on_hand', 'unit_cost')
    def _compute_total_value(self):
        for rec in self:
            rec.total_value = rec.qty_on_hand * rec.unit_cost

    @api.depends()
    def _compute_qty_on_order(self):
        """Sum pending purchase order lines matching this part name."""
        PurchaseLine = self.env['purchase.order.line']
        for rec in self:
            lines = PurchaseLine.search([
                ('name', 'ilike', rec.name),
                ('order_id.state', 'in', ['draft', 'sent', 'to approve']),
            ])
            rec.qty_on_order = sum(lines.mapped('product_qty'))

    # ── Constraints ──────────────────────────────────────────────────────
    @api.constrains('qty_on_hand')
    def _check_qty_on_hand(self):
        for rec in self:
            if rec.qty_on_hand < 0:
                raise ValidationError(
                    _('Quantity on hand cannot be negative for part "%s".')
                    % rec.name)

    # ── Cron ─────────────────────────────────────────────────────────────
    @api.model
    def apala_check_stock_levels(self):
        """Cron: check parts below minimum stock and create alerts."""
        parts = self.search([])
        template = self.env.ref(
            'apala_logistics.email_template_low_stock_alert',
            raise_if_not_found=False,
        )
        for part in parts:
            if part.qty_minimum and part.qty_on_hand < part.qty_minimum:
                part.activity_schedule(
                    'mail.mail_activity_data_warning',
                    date_deadline=fields.Date.today(),
                    summary=_('Low stock: %s (%.0f on hand, min %.0f)')
                    % (part.name, part.qty_on_hand, part.qty_minimum),
                )
                if template:
                    try:
                        template.send_mail(part.id, force_send=True)
                    except Exception:
                        pass

    # ── Actions ──────────────────────────────────────────────────────────
    def action_reorder(self):
        """Create a draft purchase order for this spare part."""
        self.ensure_one()
        if not self.supplier_id:
            raise ValidationError(
                _('Please set a supplier before reordering.'))
        product = self.env.ref(
            'apala_logistics.product_spare_part_generic',
            raise_if_not_found=False,
        )
        reorder_qty = max(self.qty_minimum - self.qty_on_hand, 1)
        po = self.env['purchase.order'].create({
            'partner_id': self.supplier_id.id,
            'order_line': [(0, 0, {
                'name': self.name,
                'product_id': product.id if product else False,
                'product_qty': reorder_qty,
                'price_unit': self.unit_cost,
                'date_planned': fields.Datetime.now(),
            })],
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'current',
        }
