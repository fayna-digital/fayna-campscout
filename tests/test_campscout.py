from odoo.tests.common import TransactionCase


class TestCampscout(TransactionCase):
    def test_portal_menu_create(self):
        menu = self.env["campscout.portal.menu"].create(
            {"region": "PL", "show_shop": True}
        )
        self.assertTrue(menu.show_shop)
