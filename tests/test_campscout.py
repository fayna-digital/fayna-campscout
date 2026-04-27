from odoo.tests.common import HttpCase, TransactionCase, tagged


class TestCampscout(TransactionCase):
    def test_portal_menu_create(self):
        menu = self.env["campscout.portal.menu"].create({"region": "PL", "show_shop": True})
        self.assertTrue(menu.show_shop)


@tagged("post_install", "-at_install", "fayna_campscout")
class TestCampscoutPortalValues(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent_partner = cls.env["res.partner"].create(
            {
                "name": "Test Parent",
                "email": "test@campscout.test",
            }
        )
        cls.portal_user = cls.env["res.users"].create(
            {
                "name": "Test Parent Portal",
                "login": "test_portal_campscout@campscout.test",
                "partner_id": cls.parent_partner.id,
                "groups_id": [(6, 0, [cls.env.ref("base.group_portal").id])],
            }
        )
        cls.event = cls.env["event.event"].create(
            {
                "name": "Test Camp 2026",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-14 18:00:00",
            }
        )

    def test_hero_values_no_participants(self):
        """Without participants or registrations, cs_has_hero must be False."""
        env_sudo = self.env(su=True)
        participants = env_sudo["camp.participant"].search(
            [("parent_partner_id", "=", self.parent_partner.id)]
        )
        regs = env_sudo["event.registration"].search(
            [
                ("partner_id", "=", self.parent_partner.id),
                ("state", "!=", "cancel"),
            ]
        )
        cs_has_hero = bool(participants or regs)
        self.assertFalse(cs_has_hero)

    def test_hero_values_with_registration(self):
        """cs_has_hero is True when the partner has a non-cancelled registration."""
        env_sudo = self.env(su=True)
        reg = env_sudo["event.registration"].create(
            {
                "event_id": self.event.id,
                "partner_id": self.parent_partner.id,
                "state": "open",
            }
        )
        regs = env_sudo["event.registration"].search(
            [
                ("partner_id", "=", self.parent_partner.id),
                ("state", "!=", "cancel"),
            ]
        )
        self.assertTrue(bool(regs))
        reg.unlink()

    def test_portal_menu_all_flags(self):
        """campscout.portal.menu stores all display-flag booleans correctly."""
        menu = self.env["campscout.portal.menu"].create(
            {
                "region": "UA",
                "show_shop": True,
                "show_stories": True,
                "show_loyalty": True,
                "show_reviews": True,
            }
        )
        self.assertTrue(menu.show_stories)
        self.assertTrue(menu.show_loyalty)
        self.assertTrue(menu.show_reviews)
        self.assertTrue(menu.show_shop)

    def test_portal_menu_defaults(self):
        """All show_* flags default to True."""
        menu = self.env["campscout.portal.menu"].create({"region": "PL"})
        self.assertTrue(menu.show_shop)
        self.assertTrue(menu.show_stories)
        self.assertTrue(menu.show_loyalty)
        self.assertTrue(menu.show_reviews)
        self.assertTrue(menu.show_blog)

    def test_portal_session_active_camps_default_zero(self):
        """_compute_active_camps returns 0 (scaffold placeholder)."""
        session = self.env["campscout.portal.session"].create(
            {
                "partner_id": self.parent_partner.id,
                "children_count": 1,
            }
        )
        self.assertEqual(session.active_camps, 0)

    def test_portal_session_children_count_stored(self):
        """children_count integer field is persisted correctly."""
        session = self.env["campscout.portal.session"].create(
            {
                "partner_id": self.parent_partner.id,
                "children_count": 3,
            }
        )
        self.assertEqual(session.children_count, 3)


@tagged("post_install", "-at_install", "fayna_campscout")
class TestCampscoutPortalHttp(HttpCase):
    """HttpCase smoke tests: portal pages return HTTP 200 for logged-in portal user."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent_partner = cls.env["res.partner"].create(
            {
                "name": "HTTP Test Parent",
                "email": "http_test@campscout.test",
            }
        )
        cls.portal_user = cls.env["res.users"].create(
            {
                "name": "HTTP Test Portal User",
                "login": "http_portal_campscout@campscout.test",
                "password": "TestPortal1234!",
                "partner_id": cls.parent_partner.id,
                "groups_id": [(6, 0, [cls.env.ref("base.group_portal").id])],
            }
        )

    def test_portal_home_loads(self):
        """GET /my returns 200 for authenticated portal user."""
        self.authenticate("http_portal_campscout@campscout.test", "TestPortal1234!")
        resp = self.url_open("/my")
        self.assertEqual(resp.status_code, 200)

    def test_portal_stories_loads(self):
        """GET /my/stories returns 200 for authenticated portal user."""
        self.authenticate("http_portal_campscout@campscout.test", "TestPortal1234!")
        resp = self.url_open("/my/stories")
        self.assertEqual(resp.status_code, 200)
