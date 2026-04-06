# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ApalaTripCloseWizard(models.TransientModel):
    _name = 'apala.trip.close.wizard'
    _description = 'Close Trip Wizard'

    trip_id = fields.Many2one('apala.trip', string='Trip', required=True)
    arrival_date = fields.Datetime(string='Arrival Date', default=fields.Datetime.now)
    odometer_end = fields.Float(string='Odometer End (km)')
    fuel_consumed_l = fields.Float(string='Fuel Consumed (litres)')
    pod_attachment = fields.Binary(string='Proof of Delivery')
    pod_filename = fields.Char(string='POD Filename')

    def action_close_trip(self):
        """Close the trip: write fields, post expenses to HR, set state = closed."""
        self.ensure_one()
        trip = self.trip_id

        if self.odometer_end and self.odometer_end < trip.odometer_start:
            raise ValidationError(_('Odometer end cannot be less than odometer start.'))

        # Write trip fields
        vals = {
            'arrival_date': self.arrival_date,
            'odometer_end': self.odometer_end,
            'fuel_consumed_l': self.fuel_consumed_l,
            'state': 'closed',
        }
        trip.write(vals)

        # Create fleet odometer record
        if self.odometer_end:
            self.env['fleet.vehicle.odometer'].create({
                'vehicle_id': trip.vehicle_id.id,
                'value': self.odometer_end,
                'date': fields.Date.today(),
            })

        # Post all trip expenses to hr.expense
        draft_expenses = trip.expense_ids.filtered(lambda e: e.state == 'draft')
        draft_expenses.action_post_to_hr_expense()

        # Auto-create expense sheet per driver
        if draft_expenses:
            employee = trip.driver_id
            if employee:
                hr_expenses = draft_expenses.mapped('hr_expense_id')
                if hr_expenses:
                    sheet = self.env['hr.expense.sheet'].create({
                        'name': _('Trip Expenses – %s') % trip.name,
                        'employee_id': employee.id,
                        'expense_line_ids': [(6, 0, hr_expenses.ids)],
                    })
                    # Auto-submit for approval
                    try:
                        sheet.action_submit_sheet()
                    except Exception:
                        pass  # Submit may require additional configuration

        # Save POD attachment
        if self.pod_attachment:
            self.env['ir.attachment'].create({
                'name': self.pod_filename or 'POD_%s' % trip.name,
                'datas': self.pod_attachment,
                'res_model': 'apala.trip',
                'res_id': trip.id,
            })

        # Update linked transport orders
        if trip.transport_order_id and trip.transport_order_id.state == 'in_transit':
            trip.transport_order_id.state = 'delivered'

        # Post chatter summary
        distance = self.odometer_end - trip.odometer_start if self.odometer_end else 0
        trip.message_post(body=_(
            'Trip closed.<br/>'
            'Distance: %.1f km<br/>'
            'Fuel consumed: %.1f litres<br/>'
            'Total expenses: %s'
        ) % (distance, self.fuel_consumed_l, trip.total_expenses))

        return {'type': 'ir.actions.act_window_close'}
