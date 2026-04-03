odoo.define('odoo_sidebar.SideBar', function (require) {
    "use strict";
    var Widget = require('web.Widget');
    var SideBar = Widget.extend({

        init: function (parent, menuData) {
            this._super.apply(this, arguments);
            this._apps = _.map(menuData.children, function (appMenuData) {
                return {
                    actionID: parseInt(appMenuData.action.split(',')[1]),
                    menuID: appMenuData.id,
                    name: appMenuData.name,
                    xmlID: appMenuData.xmlid,
                    web_icon_data: appMenuData.web_icon_data,
                    icon: appMenuData.icon,
                };
            });
        },
    });

    return SideBar;
});
