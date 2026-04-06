# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class ApalaCustomsDocument(models.Model):
    _name = 'apala.customs.document'
    _description = 'Customs Documentation'
    _order = 'name desc'

    name = fields.Char(
        string='Document Reference', required=True, copy=False,
        readonly=True, default=lambda self: _('New'),
    )
    freight_order_id = fields.Many2one('apala.freight.order', string='Freight Order')
    doc_type = fields.Selection([
        ('bill_of_lading', 'Bill of Lading'),
        ('packing_list', 'Packing List'),
        ('commercial_invoice', 'Commercial Invoice'),
        ('certificate_of_origin', 'Certificate of Origin'),
        ('import_permit', 'Import Permit'),
        ('export_permit', 'Export Permit'),
        ('customs_entry', 'Customs Entry'),
        ('release_order', 'Release Order'),
        ('other', 'Other'),
    ], string='Document Type')
    document_number = fields.Char(string='Document Number')
    issue_date = fields.Date(string='Issue Date')
    expiry_date = fields.Date(string='Expiry Date')
    issuing_authority = fields.Char(string='Issuing Authority')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='pending')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    notes = fields.Text(string='Notes')

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('apala.customs.document') or _('New')
        return super().create(vals)
