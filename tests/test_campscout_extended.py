"""
Extended tests for fayna_campscout — portal session, menu, isolation,
session fields, and integration with event.registration.

Target: bring total test count to 20+.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_campscout")
class TestCampscoutPortalSession(TransactionCase):
    """Tests for campscout.portal.session model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a = cls.env["res.partner"].create(
            {"name": "Session Parent A", "email": "session_a@campscout.test"}
        )
        cls.partner_b = cls.env["res.partner"].create(
            {"name": "Session Parent B", "email": "session_b@campscout.test"}
        )

    def test_session_create_minimal(self):
        """A session record can be created with only partner_id."""
        session = self.env["campscout.portal.session"].create(
            {"partner_id": self.partner_a.id}
        )
        self.assertTrue(session.id)
        self.assertEqual(session.partner_id, self.partner_a)

    def test_session_children_count_zero_by_default(self):
        """children_count defaults to 0 when not specified."""
        session = self.env["campscout.portal.session"].create(
            {"partner_id": self.partner_a.id}
        )
        self.assertEqual(session.children_count, 0)

    def test_session_unread_messages_field(self):
        """unread_messages integer field stores correctly."""
        session = self.env["campscout.portal.session"].create(
            {
                "partner_id": self.partner_a.id,
                "unread_messages": 5,
            }
        )
        self.assertEqual(session.unread_messages, 5)

    def test_session_pending_actions_field(self):
        """pending_actions integer field stores correctly."""
        session = self.env["campscout.portal.session"].create(
            {
                "partner_id": self.partner_a.id,
                "pending_actions": 2,
            }
        )
        self.assertEqual(session.pending_actions, 2)

    def test_session_isolation_per_partner(self):
        """Two partners have separate sessions — no data leakage."""
        session_a = self.env["campscout.portal.session"].create(
            {"partner_id": self.partner_a.id, "children_count": 1}
        )
        session_b = self.env["campscout.portal.session"].create(
            {"partner_id": self.partner_b.id, "children_count": 3}
        )
        self.assertNotEqual(session_a.partner_id, session_b.partner_id)
        self.assertEqual(session_a.children_count, 1)
        self.assertEqual(session_b.children_count, 3)

    def test_compute_active_camps_returns_int(self):
        """_compute_active_camps always returns an integer (not None/False)."""
        session = self.env["campscout.portal.session"].create(
            {"partner_id": self.partner_b.id}
        )
        # active_camps is a computed field returning 0 (scaffold placeholder)
        self.assertIsInstance(session.active_camps, int)

    def test_session_last_login_field_nullable(self):
        """last_login Datetime field can be left empty."""
        session = self.env["campscout.portal.session"].create(
            {"partner_id": self.partner_a.id}
        )
        self.assertFalse(session.last_login)

    def test_session_write_children_count(self):
        """children_count can be updated after creation."""
        session = self.env["campscout.portal.session"].create(
            {"partner_id": self.partner_a.id, "children_count": 0}
        )
        session.write({"children_count": 4})
        self.assertEqual(session.children_count, 4)


@tagged("post_install", "-at_install", "fayna_campscout")
class TestCampscoutPortalMenuExtended(TransactionCase):
    """Extended tests for campscout.portal.menu."""

    def test_menu_region_stored(self):
        """Region value is stored as-is (case-sensitive string)."""
        menu = self.env["campscout.portal.menu"].create({"region": "UA"})
        self.assertEqual(menu.region, "UA")

    def test_menu_sequence_default(self):
        """Default sequence is 10."""
        menu = self.env["campscout.portal.menu"].create({"region": "PL"})
        self.assertEqual(menu.sequence, 10)

    def test_menu_custom_links_text(self):
        """custom_links Text field stores arbitrary JSON string."""
        links = '[{"label": "Shop", "url": "/shop"}]'
        menu = self.env["campscout.portal.menu"].create(
            {"region": "PL", "custom_links": links}
        )
        self.assertEqual(menu.custom_links, links)

    def test_menu_show_blog_default_true(self):
        """show_blog defaults to True."""
        menu = self.env["campscout.portal.menu"].create({"region": "PL"})
        self.assertTrue(menu.show_blog)

    def test_multiple_regions_coexist(self):
        """PL and UA menus can coexist independently."""
        menu_pl = self.env["campscout.portal.menu"].create(
            {"region": "PL", "show_shop": True, "show_stories": False}
        )
        menu_ua = self.env["campscout.portal.menu"].create(
            {"region": "UA", "show_shop": False, "show_stories": True}
        )
        self.assertTrue(menu_pl.show_shop)
        self.assertFalse(menu_pl.show_stories)
        self.assertFalse(menu_ua.show_shop)
        self.assertTrue(menu_ua.show_stories)
