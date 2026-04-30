from odoo.tests.common import TransactionCase


class TestScaffold(TransactionCase):
    """Prove the module installs cleanly and its two core models are accessible.

    The feature-flag test was removed: fayna_camp_portal is the portal module
    and is always active once installed — there is no inert mode. Real
    behaviour tests live in test_campscout.py.
    """

    def test_module_installed(self):
        mod = self.env["ir.module.module"].search([("name", "=", "fayna_camp_portal")], limit=1)
        self.assertTrue(mod.exists())
        self.assertIn(mod.state, ("installed", "to upgrade"))

    def test_portal_menu_model_exists(self):
        """campscout.portal.menu is accessible and accepts a region value."""
        menu = self.env["campscout.portal.menu"].create({"region": "PL"})
        self.assertEqual(menu.region, "PL")

    def test_portal_session_model_exists(self):
        """campscout.portal.session is accessible and stores children_count."""
        partner = self.env["res.partner"].create({"name": "Test Portal Session Partner"})
        session = self.env["campscout.portal.session"].create(
            {
                "partner_id": partner.id,
                "children_count": 2,
            }
        )
        self.assertEqual(session.children_count, 2)
