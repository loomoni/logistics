# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ApalaTransportOrder(models.Model):
    _name = 'apala.transport.order'
    _description = 'Transport Order (Job Card)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Order Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'),
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('invoiced', 'Invoiced'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False)
    customer_id = fields.Many2one('res.partner', string='Customer', required=True, tracking=True)
    origin = fields.Char(string='Customer Reference / PO Number')
    route_id = fields.Many2one('apala.route', string='Route', required=True)
    cargo_type = fields.Selection([
        ('general', 'General Cargo'),
        ('bulk', 'Bulk'),
        ('fragile', 'Fragile'),
        ('hazardous', 'Hazardous'),
        ('refrigerated', 'Refrigerated'),
        ('livestock', 'Livestock'),
    ], string='Cargo Type', default='general')
    weight_kg = fields.Float(string='Weight (kg)')
    volume_m3 = fields.Float(string='Volume (m³)')
    pieces = fields.Integer(string='Number of Pieces')
    pickup_location = fields.Char(string='Pickup Location')
    delivery_location = fields.Char(string='Delivery Location')
    requested_date = fields.Date(string='Requested Delivery Date')
    agreed_date = fields.Date(string='Agreed Delivery Date')
    vehicle_id = fields.Many2one('fleet.vehicle', string='Assigned Vehicle', tracking=True)
    driver_id = fields.Many2one(
        'hr.employee', string='Driver', tracking=True,

    )
    trip_ids = fields.One2many('apala.trip', 'transport_order_id', string='Trips')
    manifest_ids = fields.One2many('apala.cargo.manifest', 'transport_order_id', string='Cargo Manifests')
    invoice_ids = fields.Many2many('account.move', string='Invoices', copy=False)
    invoice_count = fields.Integer(string='Invoice Count', compute='_compute_invoice_count')
    freight_charge = fields.Monetary(string='Freight Charge (TZS)')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    sale_order_id = fields.Many2one('sale.order', string='Sales Order')
    consignment_note_no = fields.Char(string='Consignment Note No.',
                                      help='Government consignment note number')
    notes = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    @api.constrains('vehicle_id', 'weight_kg')
    def _check_vehicle_payload(self):
        for rec in self:
            if rec.vehicle_id and rec.vehicle_id.max_payload_kg > 0 and rec.weight_kg > rec.vehicle_id.max_payload_kg:
                raise ValidationError(_(
                    'Cargo weight %.0f kg exceeds vehicle %s payload capacity of %.0f kg.'
                ) % (rec.weight_kg, rec.vehicle_id.name, rec.vehicle_id.max_payload_kg))

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('apala.transport.order') or _('New')
        return super().create(vals)

    def name_get(self):
        result = []
        for rec in self:
            name = '%s – %s' % (rec.name, rec.customer_id.name) if rec.customer_id else rec.name
            result.append((rec.id, name))
        return result

    def action_confirm(self):
        """Confirm the transport order. Vehicle and driver must be assigned."""
        for rec in self:
            if not rec.vehicle_id or not rec.driver_id:
                raise UserError(_('Please assign a vehicle and driver before confirming.'))
            rec.state = 'confirmed'
            # Auto-send confirmation email if configured
            auto_send = self.env['ir.config_parameter'].sudo().get_param(
                'apala_logistics.auto_send_confirmation', 'True')
            if auto_send and auto_send != 'False':
                template = self.env.ref(
                    'apala_logistics.email_template_order_confirmed', raise_if_not_found=False)
                if template:
                    try:
                        template.send_mail(rec.id, force_send=True)
                    except Exception:
                        pass

    def action_cancel(self):
        """Cancel the transport order and log the reason in chatter."""
        for rec in self:
            rec.state = 'cancelled'
            rec.message_post(body=_('Transport order cancelled.'))

    def action_create_trip(self):
        """Create a linked trip record for this transport order."""
        self.ensure_one()
        trip = self.env['apala.trip'].create({
            'transport_order_id': self.id,
            'vehicle_id': self.vehicle_id.id,
            'driver_id': self.driver_id.id,
            'route_id': self.route_id.id,
        })
        self.state = 'in_transit'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'apala.trip',
            'res_id': trip.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_invoice(self):
        """Open the invoice creation wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'apala.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_transport_order_ids': [(6, 0, self.ids)],
            },
        }

    def action_view_invoices(self):
        """Smart button action to view linked invoices."""
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('account.action_move_out_invoice_type')
        if self.invoice_count == 1:
            action['view_mode'] = 'form'
            action['res_id'] = self.invoice_ids.id
        else:
            action['domain'] = [('id', 'in', self.invoice_ids.ids)]
        return action

    @api.onchange('route_id')
    def _onchange_route_id(self):
        if self.route_id:
            self.pickup_location = self.route_id.origin_city
            self.delivery_location = self.route_id.destination_city

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        if self.sale_order_id:
            self.customer_id = self.sale_order_id.partner_id
            lines = self.sale_order_id.order_line.filtered(lambda l: l.product_id.type == 'service')
            if lines:
                self.freight_charge = sum(lines.mapped('price_subtotal'))

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values:
            return self.env.ref('mail.mt_note')
        return super()._track_subtype(init_values)
