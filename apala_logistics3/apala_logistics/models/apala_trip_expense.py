# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ApalaTripExpense(models.Model):
    _name = 'apala.trip.expense'
    _description = 'Trip Expense Line'
    _order = 'date desc, id desc'

    trip_id = fields.Many2one('apala.trip', string='Trip', required=True, ondelete='cascade')
    expense_type = fields.Selection([
        ('fuel', 'Fuel'),
        ('toll', 'Toll'),
        ('meal_allowance', 'Meal Allowance'),
        ('accommodation', 'Accommodation'),
        ('repair', 'Repair'),
        ('tyre', 'Tyre'),
        ('driver_advance', 'Driver Advance'),
        ('loading_charge', 'Loading Charge'),
        ('police_clearance', 'Police Clearance'),
        ('other', 'Other'),
    ], string='Expense Type', required=True)
    description = fields.Char(string='Description')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    amount = fields.Monetary(string='Amount (TZS)')
    date = fields.Date(string='Date', default=fields.Date.today)
    employee_id = fields.Many2one('hr.employee', string='Employee')
    receipt_ref = fields.Char(string='Receipt Reference')
    hr_expense_id = fields.Many2one('hr.expense', string='HR Expense', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
    ], string='Status', default='draft')

    def action_post_to_hr_expense(self):
        """Create hr.expense record linked to the employee and trip analytic account."""
        for rec in self:
            if rec.state == 'posted':
                continue
            employee = rec.employee_id or rec.trip_id.driver_id
            if not employee:
                raise UserError(_('No employee set for expense line: %s') % rec.description)
            product = self.env.ref('hr_expense.product_product_fixed_cost', raise_if_not_found=False)
            expense_vals = {
                'name': '%s – %s' % (rec.trip_id.name, rec.description or rec.expense_type),
                'employee_id': employee.id,
                'product_id': product.id if product else False,
                'unit_amount': rec.amount,
                'date': rec.date or fields.Date.today(),
                'analytic_account_id': rec.trip_id.analytic_account_id.id if rec.trip_id.analytic_account_id else False,
            }
            hr_expense = self.env['hr.expense'].create(expense_vals)
            rec.hr_expense_id = hr_expense.id
            rec.state = 'posted'
