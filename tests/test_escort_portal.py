# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""HttpCase tests for the escort (Indywidualna asysta) parent cabinet.

P3.5 coverage: controllers/escort_portal.py was the least-tested controller
(27%). Covers the list, the ownership gate on the detail page (with a body
leak check — the escort card carries the child's identity), and the POST
/submit flow that collects escort data and moves the record to 'collected'.
"""

import re
from datetime import timedelta

from odoo import fields
from odoo.tests.common import HttpCase, tagged

from .http_lang import open_functional

PARENT_A_LOGIN = "escort_parent_a@campscout.test"
PARENT_B_LOGIN = "escort_parent_b@campscout.test"
PASSWORD = "EscortQa-1234!Strong"
CHILD_A_NAME = "DzieckoEskortaA"


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestEscortPortal(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        now = fields.Datetime.now()
        cls.event = cls.env["event.event"].create(
            {
                "name": "Oboz Eskorta QA",
                "date_begin": now + timedelta(days=10),
                "date_end": now + timedelta(days=20),
            }
        )

        cls.partner_a = cls.env["res.partner"].create(
            {"name": "Escort Parent A", "email": PARENT_A_LOGIN}
        )
        cls.user_a = cls.env["res.users"].create(
            {
                "name": "Escort Parent A",
                "login": PARENT_A_LOGIN,
                "password": PASSWORD,
                "partner_id": cls.partner_a.id,
                "groups_id": [(6, 0, [cls.env.ref("base.group_portal").id])],
            }
        )
        cls.partner_b = cls.env["res.partner"].create(
            {"name": "Escort Parent B", "email": PARENT_B_LOGIN}
        )
        cls.user_b = cls.env["res.users"].create(
            {
                "name": "Escort Parent B",
                "login": PARENT_B_LOGIN,
                "password": PASSWORD,
                "partner_id": cls.partner_b.id,
                "groups_id": [(6, 0, [cls.env.ref("base.group_portal").id])],
            }
        )

        cls.child_a = (
            cls.env["camp.participant"]
            .sudo()
            .create(
                {
                    "first_name": CHILD_A_NAME,
                    "last_name": "Testowa",
                    "parent_partner_id": cls.partner_a.id,
                }
            )
        )
        cls.reg_a = cls.env["event.registration"].create(
            {
                "event_id": cls.event.id,
                "partner_id": cls.partner_a.id,
                "participant_id": cls.child_a.id,
            }
        )
        cls.escort_a = (
            cls.env["camp.escort"]
            .sudo()
            .create(
                {
                    "participant_id": cls.child_a.id,
                    "registration_id": cls.reg_a.id,
                    "direction": "oba",
                    "state": "draft",
                }
            )
        )

    # ── Own escort: list + detail ─────────────────────────────────────────

    def test_escort_list_and_detail_for_owner(self):
        self.authenticate(PARENT_A_LOGIN, PASSWORD)
        listing = self.url_open("/my/escort")
        self.assertEqual(listing.status_code, 200)
        self.assertIn(CHILD_A_NAME, listing.text)

        # RAW (без follow): раніше деталь 303-редіректила ВЛАСНИКА на список,
        # а follow-redirect робив цей тест хибно-зеленим (список теж містить
        # ім'я дитини). Тепер деталь мусить відренде́ритись сама.
        detail = open_functional(self, f"/my/escort/{self.escort_a.id}")
        self.assertEqual(detail.status_code, 200, "owner's escort detail must render, not redirect")
        self.assertIn(CHILD_A_NAME, detail.text)
        self.assertIn("csrf_token", detail.text, "collect form must be present")

    # ── Foreign escort: gate + no identity leak ──────────────────────────

    def test_foreign_escort_blocked_without_leak(self):
        self.authenticate(PARENT_B_LOGIN, PASSWORD)
        raw = open_functional(self, f"/my/escort/{self.escort_a.id}")
        self.assertIn(
            raw.status_code,
            (301, 302, 303, 307, 308),
            "foreign escort card must redirect, not render",
        )
        followed = self.url_open(f"/my/escort/{self.escort_a.id}")
        self.assertNotIn(
            CHILD_A_NAME,
            followed.text,
            "child A's identity leaked to parent B via /my/escort/<id>",
        )

    # ── POST /submit: collects data + state draft → collected ────────────

    def test_submit_collects_and_transitions(self):
        self.authenticate(PARENT_A_LOGIN, PASSWORD)
        form = self.url_open(f"/my/escort/{self.escort_a.id}").text
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', form)
        self.assertTrue(match, "escort form must carry a csrf token")

        resp = self.url_open(
            f"/my/escort/{self.escort_a.id}/submit",
            data={
                "csrf_token": match.group(1),
                "home_city": "Krakow",
                "pkp_station": "Krakow Glowny",
                "direction": "oba",
                "transport_mode": "pociag",
                "escort_person_name": "Opiekun QA",
                "escort_person_phone": "+48111222333",
                "medical_help_consent": "1",
            },
            allow_redirects=False,
        )
        self.assertIn(
            resp.status_code,
            (301, 302, 303, 307, 308),
            "successful submit must redirect back to the escort card",
        )
        escort = self.escort_a.sudo()
        escort.invalidate_recordset()
        self.assertEqual(escort.home_city, "Krakow")
        self.assertEqual(escort.pkp_station, "Krakow Glowny")
        self.assertEqual(escort.state, "collected")
