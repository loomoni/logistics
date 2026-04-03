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
