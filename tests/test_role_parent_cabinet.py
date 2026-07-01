# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Experiential role test — PARENT portal cabinet: /my/participants.

Perspective: independent QA engineer. Proves that a portal user (parent)
can:
  1. GET /my/participants → HTTP 200 and their child's name appears in the body.
  2. GET /my/camp-day/<event_id> → HTTP 200 when the parent has a valid
     registration on that event (access gate check, distinct from
     test_portal_camp_day.py which tests the field-whitelist / isolation logic).

Does NOT duplicate test_art9_http_isolation.py (cross-parent isolation) or
test_portal_camp_day.py (whitelist + staff-field leak check).

Routes under test (controllers/portal.py):
  * GET /my/participants  — portal_my_participants(): sudo search by partner_id
  * GET /my/camp-day/<event_id> — portal_my_camp_day(): own-registration gate
"""

import datetime

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestRoleParentCabinet(HttpCase):
    """Portal parent sees their child in /my/participants and reaches /my/camp-day."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Parent partner + portal user
        cls.parent_partner = cls.env["res.partner"].create(
            {
                "name": "QA Parent Role Test",
                "email": "qa_parent_role@campscout.test",
            }
        )
        cls.portal_user = cls.env["res.users"].create(
            {
                "name": "QA Parent Role Test",
                "login": "qa_parent_role@campscout.test",
                "password": "QaParent-1234!",
                "partner_id": cls.parent_partner.id,
                "groups_id": [(6, 0, [cls.env.ref("base.group_portal").id])],
            }
        )

        # Child participant linked to this parent
        child_partner = cls.env["res.partner"].create({"name": "QA Child Uczestnik Role"})
        cls.participant = cls.env["camp.participant"].create(
            {
                "partner_id": child_partner.id,
                "parent_partner_id": cls.parent_partner.id,
                "first_name": "Janek",
                "last_name": "RoleTestKowalski",
            }
        )

        # Event with a registration for this parent — needed for /my/camp-day gate
        cls.event = cls.env["event.event"].create(
            {
                "name": "QA Parent Role Camp",
                "date_begin": datetime.datetime(2026, 7, 1, 9, 0),
                "date_end": datetime.datetime(2026, 7, 10, 18, 0),
                "date_tz": "Europe/Warsaw",
            }
        )
        cls.env["event.registration"].create(
            {
                "event_id": cls.event.id,
                "partner_id": cls.parent_partner.id,
            }
        )

    # ── 1. Parent sees their child in /my/participants ───────────────────────

    def test_parent_sees_own_child_in_participants(self):
        """GET /my/participants returns HTTP 200 and shows this parent's child."""
        self.authenticate("qa_parent_role@campscout.test", "QaParent-1234!")
        response = self.url_open("/my/participants")
        self.assertEqual(
            response.status_code,
            200,
            "/my/participants must return HTTP 200 for an authenticated portal user",
        )
        body = response.text
        self.assertIn(
            "RoleTestKowalski",
            body,
            "Parent's child last name must appear in /my/participants response body",
        )

    # ── 2. Parent reaches /my/camp-day for their own event ──────────────────

    def test_parent_reaches_camp_day_own_event(self):
        """GET /my/camp-day/<event_id> returns HTTP 200 for a registered event."""
        self.authenticate("qa_parent_role@campscout.test", "QaParent-1234!")
        response = self.url_open(f"/my/camp-day/{self.event.id}")
        self.assertEqual(
            response.status_code,
            200,
            (
                "PRODUCT FINDING: /my/camp-day/<event_id> must return 200 for a parent with "
                "a valid registration on that event. A redirect (302) means the access gate "
                "(portal_my_camp_day: `event_id not in allowed_events.ids`) is rejecting a "
                "legitimate registration."
            ),
        )
