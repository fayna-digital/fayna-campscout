# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Experiential role test — PORTAL PARENT sees their child on /my/participants
and /my/camp-day/<event>.

Perspective: independent QA.  This test drives the system AS a portal user
who is the legal parent of a camp.participant and has an event.registration,
and asserts:

1. GET /my/participants → HTTP 200 + child's name visible.
2. GET /my/camp-day/<event_id> → HTTP 200 (registered event).
3. GET /my/camp-day/<other_event_id> → redirect (not the parent's event).

Route definitions (controllers/portal.py):
  * /my/participants         auth='user' → portal_my_participants()
  * /my/camp-day/<event_id>  auth='user' → portal_my_camp_day()

Access pattern: both routes use env(su=True) with explicit partner-scope
filtering — portal user has no direct ACL on camp.participant / event.event.
The security is ownership-based (parent_partner_id == request.env.user.partner_id).
"""

from datetime import timedelta

from odoo import fields
from odoo.tests.common import HttpCase, tagged

from .http_lang import REDIRECT_CODES, location_path, open_functional, strip_lang_prefix


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestRoleParentPortal(HttpCase):
    """Portal parent sees own child on /my/participants and /my/camp-day."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        now = fields.Datetime.now()
        today = fields.Date.today()

        # Create parent partner + portal user
        cls.parent_partner = cls.env["res.partner"].create(
            {
                "name": "QA Portal Parent",
                "email": "qa_parent_portal@campscout.test",
            }
        )
        cls.parent_user = cls.env["res.users"].create(
            {
                "name": "QA Portal Parent User",
                "login": "qa_parent_portal@campscout.test",
                "password": "QaParent-1234!",
                "partner_id": cls.parent_partner.id,
                "groups_id": [(6, 0, [cls.env.ref("base.group_portal").id])],
            }
        )

        # Create the camp event the parent's child is registered for
        cls.own_event = cls.env["event.event"].create(
            {
                "name": "QA Obóz Parent Portal 2026",
                "date_begin": now - timedelta(days=1),
                "date_end": now + timedelta(days=8),
            }
        )

        # Register the parent on the event (the camp.participant uses
        # parent_partner_id; event.registration uses partner_id)
        cls.env["event.registration"].create(
            {
                "event_id": cls.own_event.id,
                "partner_id": cls.parent_partner.id,
            }
        )

        # Create a partner for the child (camp.participant delegates to res.partner)
        cls.child_partner = cls.env["res.partner"].create(
            {
                "name": "QA Child Anastazja",
                "email": "qa_child_anastazja@campscout.test",
            }
        )
        # Create camp.participant linked to parent
        cls.participant = cls.env["camp.participant"].create(
            {
                "partner_id": cls.child_partner.id,
                "first_name": "Anastazja",
                "last_name": "QA",
                "parent_partner_id": cls.parent_partner.id,
            }
        )

        # Create another event the parent is NOT registered for
        cls.other_event = cls.env["event.event"].create(
            {
                "name": "QA Obóz Cudzy 2026",
                "date_begin": now - timedelta(days=1),
                "date_end": now + timedelta(days=5),
            }
        )

        # Seed a submitted daily report so /my/camp-day has content
        cls.env["camp.daily.report"].create(
            {
                "event_id": cls.own_event.id,
                "report_date": today,
                "morning_activities": "Poranny apel i gimnastyka",
                "state": "submitted",
            }
        )

    # ── 1. /my/participants → 200 + child name ────────────────────────────────

    def test_parent_sees_own_participant(self):
        """Portal parent gets HTTP 200 on /my/participants and sees their child."""
        self.authenticate("qa_parent_portal@campscout.test", "QaParent-1234!")
        resp = self.url_open("/my/participants")
        self.assertEqual(
            resp.status_code,
            200,
            f"/my/participants must return 200 for an authenticated portal parent, "
            f"got {resp.status_code}.",
        )
        self.assertIn(
            "Anastazja",
            resp.text,
            "The participant's first name must appear on /my/participants for the parent "
            "(controller filters by parent_partner_id == current user's partner).",
        )

    # ── 2. /my/camp-day/<own_event_id> → 200 ─────────────────────────────────

    def test_parent_sees_own_camp_day(self):
        """Portal parent gets HTTP 200 on /my/camp-day/<event> they're registered for."""
        self.authenticate("qa_parent_portal@campscout.test", "QaParent-1234!")
        resp = self.url_open(f"/my/camp-day/{self.own_event.id}")
        self.assertEqual(
            resp.status_code,
            200,
            f"/my/camp-day/<own_event> must return 200 for a parent with a "
            f"registration on that event, got {resp.status_code}.",
        )
        self.assertIn(
            "QA Obóz Parent Portal 2026",
            resp.text,
            "The event name must appear on the /my/camp-day page.",
        )

    # ── 3. /my/camp-day/<other_event_id> → redirect ───────────────────────────

    def test_parent_redirected_from_foreign_camp_day(self):
        """Portal parent is redirected away from an event they are NOT registered for."""
        self.authenticate("qa_parent_portal@campscout.test", "QaParent-1234!")
        resp = open_functional(self, f"/my/camp-day/{self.other_event.id}")
        self.assertIn(
            resp.status_code,
            REDIRECT_CODES,
            f"/my/camp-day/<foreign_event> must redirect a parent who is not "
            f"registered for that event, got {resp.status_code}.",
        )
        location = strip_lang_prefix(location_path(resp))
        self.assertTrue(
            location.rstrip("/").endswith("/my"),
            f"Redirect from foreign camp-day must go to /my, got {location!r}.",
        )

    # ── 4. /my/participants page renders without crash (smoke) ────────────────

    def test_participants_page_no_server_error(self):
        """GET /my/participants never returns 5xx — even with zero participants."""
        self.authenticate("qa_parent_portal@campscout.test", "QaParent-1234!")
        resp = self.url_open("/my/participants")
        self.assertLess(
            resp.status_code,
            500,
            f"/my/participants must never 5xx for a portal user, got {resp.status_code}.",
        )
