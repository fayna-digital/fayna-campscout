"""HttpCase tests for /my/camp-day/<event_id> — «Dzień w obozie».

Covers TZ_SPRINT_2026-06-10 §7:

* a parent with a registration on the event gets HTTP 200 and sees the
  event name + parent-facing daily report content;
* an event the parent has NO registration on redirects back to /my;
* staff-only camp.daily.report fields (health_incidents et al.) are NOT
  present in the response — the controller passes whitelist dicts only.
"""

from datetime import timedelta

from odoo import fields
from odoo.tests.common import HttpCase, tagged

HEALTH_SENTINEL = "SEKRET-ZDROWOTNY-NIE-DLA-RODZICOW"
KIEROWNIK_SENTINEL = "SEKRET-KIEROWNIKA-PRYWATNY"


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestPortalCampDay(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        now = fields.Datetime.now()
        today = fields.Date.today()

        cls.parent_partner = cls.env["res.partner"].create(
            {
                "name": "CampDay Test Parent",
                "email": "campday_parent@campscout.test",
            }
        )
        cls.portal_user = cls.env["res.users"].create(
            {
                "name": "CampDay Test Portal User",
                "login": "campday_parent@campscout.test",
                "password": "TestCampDay1234!",
                "partner_id": cls.parent_partner.id,
                "groups_id": [(6, 0, [cls.env.ref("base.group_portal").id])],
            }
        )

        # Own event — the parent has a registration here
        cls.event_own = cls.env["event.event"].create(
            {
                "name": "Oboz CampDay Wlasny",
                "date_begin": now - timedelta(days=2),
                "date_end": now + timedelta(days=5),
            }
        )
        cls.env["event.registration"].create(
            {
                "event_id": cls.event_own.id,
                "partner_id": cls.parent_partner.id,
            }
        )

        # Foreign event — no registration for this parent
        cls.event_other = cls.env["event.event"].create(
            {
                "name": "Oboz CampDay Cudzy",
                "date_begin": now - timedelta(days=2),
                "date_end": now + timedelta(days=5),
            }
        )

        # Daily report with both public and staff-only content
        cls.daily_report = cls.env["camp.daily.report"].create(
            {
                "event_id": cls.event_own.id,
                "report_date": today,
                "weather": "Slonecznie, 24C",
                "weather_condition": "sunny",
                "morning_activities": "Poranna gimnastyka nad jeziorem",
                "afternoon_activities": "Warsztaty survivalowe",
                "evening_activities": "Ognisko i piosenki",
                "meals_summary": "Obiad: pomidorowa, kotlet, kompot",
                "health_incidents": HEALTH_SENTINEL,
                "kierownik_notes": KIEROWNIK_SENTINEL,
                "state": "submitted",
            }
        )

        # Published public story with the same date
        cls.story = cls.env["camp.story"].create(
            {
                "event_id": cls.event_own.id,
                "date": today,
                "title": "Wielka przygoda nad jeziorem",
                "content": "<p>Dzieci zdobyly nowa sprawnosc.</p>",
                "state": "published",
                "public": True,
            }
        )

    def test_parent_sees_own_event_camp_day(self):
        """Parent with a registration: 200 + event name + report content."""
        self.authenticate("campday_parent@campscout.test", "TestCampDay1234!")
        resp = self.url_open(f"/my/camp-day/{self.event_own.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Oboz CampDay Wlasny", resp.text)
        self.assertIn("Poranna gimnastyka nad jeziorem", resp.text)
        self.assertIn("Obiad: pomidorowa, kotlet, kompot", resp.text)
        self.assertIn("Wielka przygoda nad jeziorem", resp.text)

    def test_foreign_event_redirects_to_my(self):
        """Event without the parent's registration → redirect to /my."""
        self.authenticate("campday_parent@campscout.test", "TestCampDay1234!")
        resp = self.url_open(f"/my/camp-day/{self.event_other.id}", allow_redirects=False)
        self.assertIn(resp.status_code, (301, 302, 303, 307, 308))
        location = resp.headers.get("Location", "")
        self.assertTrue(
            location.rstrip("/").endswith("/my"),
            f"Expected redirect to /my, got {location!r}",
        )

    def test_staff_only_fields_not_leaked(self):
        """health_incidents / kierownik_notes never reach the parent page."""
        self.authenticate("campday_parent@campscout.test", "TestCampDay1234!")
        resp = self.url_open(f"/my/camp-day/{self.event_own.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(HEALTH_SENTINEL, resp.text)
        self.assertNotIn(KIEROWNIK_SENTINEL, resp.text)

    def test_draft_report_hidden(self):
        """Draft daily reports are excluded from the parent timeline."""
        draft_sentinel = "SZKIC-RAPORTU-NIEPUBLIKOWANY"
        self.env["camp.daily.report"].create(
            {
                "event_id": self.event_own.id,
                "report_date": fields.Date.today() + timedelta(days=1),
                "morning_activities": draft_sentinel,
                "state": "draft",
            }
        )
        self.authenticate("campday_parent@campscout.test", "TestCampDay1234!")
        resp = self.url_open(f"/my/camp-day/{self.event_own.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(draft_sentinel, resp.text)
