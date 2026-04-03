# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta


class HrEmployeeExtend(models.Model):
    _inherit = 'hr.employee'

    is_driver = fields.Boolean(string='Is Driver', default=False)
    driver_licence_no = fields.Char(string='Driver Licence No.')
    licence_class = fields.Selection([
        ('class_b', 'Class B'),
        ('class_c', 'Class C'),
        ('class_e', 'Class E'),
        ('class_f', 'Class F'),
    ], string='Licence Class')
    licence_expiry = fields.Date(string='Licence Expiry Date')
    psv_badge_no = fields.Char(string='PSV Badge No.')
    medical_cert_expiry = fields.Date(string='Medical Certificate Expiry')
    trip_ids = fields.One2many('apala.trip', 'driver_id', string='Trips')
    trip_count = fields.Integer(string='Trip Count', compute='_compute_trip_count')

    @api.depends('trip_ids')
    def _compute_trip_count(self):
        for emp in self:
            emp.trip_count = len(emp.trip_ids)

    @api.model
    def _check_driver_document_expiry(self):
        """Scheduled action: warn if driver licence or medical cert expires within 30 days."""
        today = fields.Date.today()
        warn_date = today + relativedelta(days=30)
        drivers = self.search([
            ('is_driver', '=', True),
            '|',
            '&', ('licence_expiry', '<=', warn_date), ('licence_expiry', '>=', today),
            '&', ('medical_cert_expiry', '<=', warn_date), ('medical_cert_expiry', '>=', today),
        ])
        for driver in drivers:
            msg_parts = []
            if driver.licence_expiry and driver.licence_expiry <= warn_date:
                msg_parts.append(_('Driver licence expires on %s') % driver.licence_expiry)
            if driver.medical_cert_expiry and driver.medical_cert_expiry <= warn_date:
                msg_parts.append(_('Medical certificate expires on %s') % driver.medical_cert_expiry)
            if msg_parts:
                driver.message_post(
                    body=_('Warning for %s: %s') % (driver.name, '; '.join(msg_parts)),
                    subject=_('Document Expiry Warning'),
                )

    @api.model
    def apala_check_driver_document_expiry(self):
        """Cron: check driver document expiry and schedule activities + email alerts."""
        alert_days = int(self.env['ir.config_parameter'].sudo().get_param(
            'apala_logistics.licence_alert_days', '30'))
        today = fields.Date.today()
        warn_date = today + relativedelta(days=alert_days)
        drivers = self.search([
            ('is_driver', '=', True),
            '|',
            '&', ('licence_expiry', '<=', warn_date), ('licence_expiry', '>=', today),
            '&', ('medical_cert_expiry', '<=', warn_date), ('medical_cert_expiry', '>=', today),
        ])
        template = self.env.ref(
            'apala_logistics.email_template_driver_expiry_alert', raise_if_not_found=False)
        for driver in drivers:
            # Schedule activities
            if driver.licence_expiry and driver.licence_expiry <= warn_date:
                driver.activity_schedule(
                    'mail.mail_activity_data_warning',
                    date_deadline=driver.licence_expiry,
                    summary=_('Driver licence expiring soon'),
                )
            if driver.medical_cert_expiry and driver.medical_cert_expiry <= warn_date:
                driver.activity_schedule(
                    'mail.mail_activity_data_warning',
                    date_deadline=driver.medical_cert_expiry,
                    summary=_('Medical certificate expiring soon'),
                )
            # Send email to managers
            if template:
                try:
                    template.send_mail(driver.id, force_send=True)
                except Exception:
                    pass
