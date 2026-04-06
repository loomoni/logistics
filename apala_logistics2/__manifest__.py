# -*- coding: utf-8 -*-
{
    'name': 'Apala Logistics',
    'version': '15.0.1.1.0',
    'summary': 'Transport, Freight Forwarding & Cargo Management for Apala Logistic Co. Ltd',
    'description': 'Central Corridor logistics management: transport orders, trips, '
                   'cargo manifests, freight forwarding, customs, storage contracts, '
                   'and full integration with Accounting, HR, Fleet, and Expenses.',
    'author': 'Twende Technologies Limited',
    'website': 'https://apalalogistic.net',
    'category': 'Inventory/Delivery',
    'depends': [
        'base', 'mail', 'account', 'fleet', 'hr', 'hr_expense',
        'stock', 'sale', 'purchase', 'analytic', 'base_setup',
    ],
    'data': [
        # Security
        'security/apala_security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/apala_sequence_data.xml',
        'data/apala_tax_data.xml',
        'data/apala_product_data.xml',
        'data/apala_route_data.xml',
        'data/apala_email_templates.xml',
        'data/apala_cron_data.xml',
        # Views
        'views/apala_dashboard_views.xml',
        'views/apala_transport_order_views.xml',
        'views/apala_trip_views.xml',
        'views/apala_route_views.xml',
        'views/apala_cargo_manifest_views.xml',
        'views/apala_freight_order_views.xml',
        'views/apala_storage_contract_views.xml',
        'views/apala_customs_document_views.xml',
        'views/apala_trip_expense_views.xml',
        'views/res_partner_extend_views.xml',
        'views/apala_config_settings_views.xml',
        'views/apala_menu.xml',
        # Wizards
        'wizard/apala_invoice_wizard_views.xml',
        'wizard/apala_trip_close_wizard_views.xml',
        # Reports
        'report/report_templates.xml',
        'report/apala_waybill_report.xml',
        'report/apala_trip_expense_report.xml',
        'report/apala_freight_invoice_report.xml',
    ],
    'demo': [
        'data/apala_demo_data.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
    'auto_install': False,
}
