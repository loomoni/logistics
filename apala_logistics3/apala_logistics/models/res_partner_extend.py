# -*- coding: utf-8 -*-
from odoo import models, fields


class ResPartnerExtend(models.Model):
    _inherit = 'res.partner'

    tin_number = fields.Char(string='TIN Number',
                             help='Tanzania Revenue Authority TIN')
    vrn_number = fields.Char(string='VRN Number',
                             help='VAT Registration Number')
    is_transporter = fields.Boolean(string='Is Transporter',
                                    help='Third-party carrier flag')
    credit_profile_id = fields.Many2one(
        'apala.customer.credit', string='Credit Profile',
        compute='_compute_credit_profile', store=False)
    credit_status = fields.Selection(
        related='credit_profile_id.credit_status', string='Credit Status', readonly=True)
    outstanding_balance = fields.Monetary(
        related='credit_profile_id.outstanding_balance', string='Outstanding Balance', readonly=True)

    def _compute_credit_profile(self):
        CreditProfile = self.env['apala.customer.credit']
        for partner in self:
            profile = CreditProfile.search([
                ('partner_id', '=', partner.id)], limit=1)
            partner.credit_profile_id = profile.id if profile else False
