# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Responsive Sidebar',
    'version': '15.0.1.0.0',
    'live_test_url': 'https://youtu.be/HUbAghadZyM',
    'sequence': 1,
    'summary': """
       Side Menu
    """,
    'description': "It's time to bid goodbye to the boring, monotonous sidebar of Odoo which you have been using for a while and say hello to a new sidebar, which breathes life into your Odoo backend and one that you can customize and make new every day.",
    'author': 'Innoway',
    'maintainer': 'Innoway',
    'price': '15.0',
    'currency': 'EUR',
    'website': 'https://innoway-solutions.com',
    'license': 'OPL-1',
    'images': [
        'static/description/wallpaper.png'
    ],
    'depends': [
        'web'
    ],
    'data': [
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_qweb': [
            'odoo_sidebar/static/src/xml/sidebar.xml',
        ],
        'web.assets_backend': [
            'odoo_sidebar/static/src/scss/variable.scss',
            'odoo_sidebar/static/src/scss/global.scss',
            'odoo_sidebar/static/src/scss/menu.scss',
            'odoo_sidebar/static/src/js/navbar.js',
        ],
    },
    'demo': [

    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
