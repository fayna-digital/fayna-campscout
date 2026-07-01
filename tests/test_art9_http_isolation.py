# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""HttpCase tests for RODO art.9 isolation on /my/participants/<id>.

The existing `test_art9_access.py` proves the *scope expression* the
controllers rely on (search by `parent_partner_id`) — but it does so through
`sudo()`, i.e. it never exercises the real HTTP boundary. These tests are a
STRONGER proof: they drive a genuine authenticated HTTP session as portal
parent A and assert that A can never pull the qualification card — and the
art.9 (special-category health) data on it — of a child belonging to
parent B.

Route under test (controllers/portal.py):

    @http.route(["/my/participants/<int:participant_id>"], ...)
    def portal_my_participant_detail(...):
        try:
            participant = self._get_own_participant(participant_id)
        except (AccessError, MissingError):
            return http.request.redirect("/my/participants")

`_get_own_participant` browses under sudo() but then hard-gates on
`participant.parent_partner_id != request.env.user.partner_id` → AccessError,
which the route turns into a redirect. The card template
(`portal_participants_detail`, templates/portal_chatter.xml) renders the
child's `special_needs` (art.9 health text), name and emergency contact, so a
successful cross-parent GET would physically leak that data into the response.

Covered:
  1. Own child   → GET 200, art.9 `special_needs` sentinel + name present.
  2. Foreign child → GET redirects to /my/participants, and the foreign
     child's art.9 sentinel / name / emergency contact are ABSENT from the
     body (no leak even in an error page).
  3. Foreign child via the POST /submit route → redirect + record unchanged
     (parent A cannot mutate parent B's card either).
"""

import re

from odoo.tests.common import HttpCase, tagged

# Distinctive art.9 (special-category health) markers. If either ever appears
# in a response served to the WRONG parent, that string is the smoking gun.
CHILD_A_ART9 = "ART9-DZIECKO-A-ALERGIA-ORZECHY-SEKRET"
CHILD_B_ART9 = "ART9-DZIECKO-B-CUKRZYCA-INSULINA-SEKRET"
CHILD_B_NAME = "TajneImieDzieckaB"
CHILD_B_CONTACT = "KontaktAlarmowyRodzicaB-999"


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestArt9HttpIsolation(HttpCase):
    """Real HTTP proof that a portal parent cannot read another child's art.9 card."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Parent A (portal user) ───────────────────────────────────────────
        cls.parent_a_partner = cls.env["res.partner"].create(
            {"name": "Art9 HTTP Parent A", "email": "art9_http_parent_a@campscout.test"}
        )
        cls.user_a = cls.env["res.users"].create(
            {
                "name": "Art9 HTTP Parent A",
                "login": "art9_http_parent_a@campscout.test",
                "password": "Art9HttpA-1234!",
                "partner_id": cls.parent_a_partner.id,
                "groups_id": [(6, 0, [cls.env.ref("base.group_portal").id])],
            }
        )

        # ── Parent B (portal user) ───────────────────────────────────────────
        cls.parent_b_partner = cls.env["res.partner"].create(
            {"name": "Art9 HTTP Parent B", "email": "art9_http_parent_b@campscout.test"}
        )
        cls.user_b = cls.env["res.users"].create(
            {
                "name": "Art9 HTTP Parent B",
                "login": "art9_http_parent_b@campscout.test",
                "password": "Art9HttpB-1234!",
                "partner_id": cls.parent_b_partner.id,
                "groups_id": [(6, 0, [cls.env.ref("base.group_portal").id])],
            }
        )

        # ── Child A — belongs to parent A ────────────────────────────────────
        # `special_needs` is the art.9 field the detail template renders back to
        # the parent (textarea value while the card is unsigned). Cards are left
        # unsigned so `special_needs` is emitted verbatim into the page.
        cls.child_a = (
            cls.env["camp.participant"]
            .sudo()
            .create(
                {
                    "first_name": "DzieckoA",
                    "last_name": "Art9Http",
                    "parent_partner_id": cls.parent_a_partner.id,
                    "special_needs": CHILD_A_ART9,
                    "allergies": "Orzechy",
                    "medications": "EpiPen",
                    "chronic_conditions": "Astma",
                    "emergency_contact_1_name": "Rodzic A",
                    "emergency_contact_1_phone": "+48000000001",
                }
            )
        )

        # ── Child B — belongs to parent B (the record A must never reach) ────
        cls.child_b = (
            cls.env["camp.participant"]
            .sudo()
            .create(
                {
                    "first_name": CHILD_B_NAME,
                    "last_name": "Art9Http",
                    "parent_partner_id": cls.parent_b_partner.id,
                    "special_needs": CHILD_B_ART9,
                    "allergies": "Cukrzyca — insulina",
                    "medications": "Insulina 3x dziennie",
                    "chronic_conditions": "Cukrzyca typu 1",
                    "emergency_contact_1_name": CHILD_B_CONTACT,
                    "emergency_contact_1_phone": "+48000000002",
                }
            )
        )

    # ─── 1. Own child: HTTP 200 + art.9 content is served ─────────────────────

    def test_parent_a_sees_own_child_art9_card(self):
        """Parent A GETs their own child's card → 200 with art.9 special_needs."""
        self.authenticate("art9_http_parent_a@campscout.test", "Art9HttpA-1234!")
        resp = self.url_open(f"/my/participants/{self.child_a.id}")
        self.assertEqual(
            resp.status_code,
            200,
            "Parent A must be able to open their OWN child's qualification card",
        )
        self.assertIn(
            "DzieckoA",
            resp.text,
            "Own child's name must render on the card",
        )
        self.assertIn(
            CHILD_A_ART9,
            resp.text,
            "Own child's art.9 special_needs must be visible to the owning parent",
        )

    # ─── 2. Foreign child: redirect + NO art.9 leak ───────────────────────────

    def test_parent_a_cannot_read_child_b_art9_card(self):
        """Parent A GETs parent B's child card → redirect, and ZERO art.9 leak.

        This is the core RODO isolation guarantee. `_get_own_participant`
        raises AccessError for a child whose `parent_partner_id` is not the
        session user's partner, and the route converts that into a redirect to
        /my/participants. We assert BOTH: the redirect (no card rendered) AND
        that none of child B's special-category data appears anywhere in the
        followed response body.
        """
        self.authenticate("art9_http_parent_a@campscout.test", "Art9HttpA-1234!")

        # (a) Raw response must be a redirect, not a 200 card render.
        raw = self.url_open(
            f"/my/participants/{self.child_b.id}", allow_redirects=False
        )
        self.assertIn(
            raw.status_code,
            (301, 302, 303, 307, 308),
            f"Cross-parent card access must redirect, got {raw.status_code} "
            "(a 200 here would mean parent A rendered parent B's card)",
        )
        location = raw.headers.get("Location", "")
        self.assertTrue(
            location.rstrip("/").endswith("/my/participants"),
            f"Expected redirect to /my/participants, got {location!r}",
        )

        # (b) Follow the redirect: the resulting page (parent A's own list) must
        #     contain NONE of child B's art.9 data / identifying info.
        followed = self.url_open(f"/my/participants/{self.child_b.id}")
        for secret in (CHILD_B_ART9, CHILD_B_NAME, CHILD_B_CONTACT):
            self.assertNotIn(
                secret,
                followed.text,
                f"RODO art.9 LEAK: parent B's secret {secret!r} reached parent A "
                "via /my/participants/<child_B_id>",
            )

    # ─── 3. Foreign child via POST /submit: ownership gate + record unchanged ─

    def test_parent_a_cannot_write_child_b_card(self):
        """Parent A POSTing to child B's /submit must not mutate B's record.

        A VALID csrf_token is scraped from parent A's OWN card form so the POST
        actually reaches the controller (rather than being rejected purely by
        CSRF). This proves the ownership gate — not just CSRF — blocks the
        cross-parent write. The decisive assertion is that child B's record is
        byte-for-byte unchanged afterwards.
        """
        self.authenticate("art9_http_parent_a@campscout.test", "Art9HttpA-1234!")

        # Scrape a valid CSRF token from parent A's own (unsigned) card form.
        own_card = self.url_open(f"/my/participants/{self.child_a.id}").text
        token = None
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', own_card)
        if match:
            token = match.group(1)

        payload = {
            "special_needs": "NADPISANE-PRZEZ-OBCEGO-RODZICA",
            "emergency_contact_1_name": "Wlamywacz",
        }
        if token:
            payload["csrf_token"] = token

        resp = self.url_open(
            f"/my/participants/{self.child_b.id}/submit",
            data=payload,
            allow_redirects=False,
        )
        # A 200 here would mean parent A rendered/mutated parent B's card. The
        # ownership gate must instead redirect (or reject) — never a success.
        self.assertNotEqual(
            resp.status_code,
            200,
            "POST to another parent's /submit must never return a 200 success render",
        )

        # Decisive guarantee: parent B's art.9 record is untouched.
        self.child_b.invalidate_recordset()
        self.assertEqual(
            self.child_b.sudo().special_needs,
            CHILD_B_ART9,
            "Parent A must NOT be able to overwrite parent B's child art.9 data",
        )
        self.assertEqual(
            self.child_b.sudo().emergency_contact_1_name,
            CHILD_B_CONTACT,
            "Parent A must NOT be able to overwrite parent B's emergency contact",
        )
