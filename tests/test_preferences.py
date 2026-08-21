# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""F-MY-5 — /my/preferences SMS opt-out.

Requirement (docs/TZ.md [F-MY-5]):
  WHEN батько відкриває сторінку preferences, THEN вона має бути доступною за
  URL /preferences, інакше система показує помилку 404.
  WHEN батько вимкнув SMS у /my/preferences, THEN система не надсилає SMS навіть
  для CRITICAL-подій, але надсилає email/push.

This test drives the system AS a portal parent:
  1. GET /my/preferences → HTTP 200 (page reachable, not 404).
  2. POST /my/preferences/save with sms_opt_in off → partner.sms_opt_in == False.
  3. With sms_opt_in off, the SMS recipient filter drops the partner for
     CRITICAL priority (no SMS even for critical events), while email/push
     remain unaffected (they are not gated by sms_opt_in).
"""

import re

from odoo.tests.common import HttpCase, TransactionCase, tagged

from .http_lang import REDIRECT_CODES, location_path, open_functional, strip_lang_prefix


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestPreferencesPage(HttpCase):
    """HTTP-level: /my/preferences is reachable and the save endpoint persists."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent_partner = cls.env["res.partner"].create(
            {
                "name": "QA Preferences Parent",
                "email": "qa_preferences@campscout.test",
            }
        )
        cls.parent_user = cls.env["res.users"].create(
            {
                "name": "QA Preferences Parent User",
                "login": "qa_preferences@campscout.test",
                "password": "QaPreferences-1234!",
                "partner_id": cls.parent_partner.id,
                "groups_id": [(6, 0, [cls.env.ref("base.group_portal").id])],
            }
        )

    def test_preferences_page_returns_200(self):
        """F-MY-5: /my/preferences must be reachable (HTTP 200), not 404."""
        self.authenticate("qa_preferences@campscout.test", "QaPreferences-1234!")
        resp = self.url_open("/my/preferences")
        self.assertEqual(
            resp.status_code,
            200,
            f"/my/preferences must return 200 for an authenticated portal parent, "
            f"got {resp.status_code}.",
        )

    def test_preferences_save_persists_sms_opt_out(self):
        """F-MY-5: POST /my/preferences/save with sms_opt_in off persists it."""
        self.authenticate("qa_preferences@campscout.test", "QaPreferences-1234!")
        # Default is ON.
        self.assertTrue(self.parent_partner.sms_opt_in)
        # The save route is CSRF-protected, so scrape the token from the form
        # first (same pattern as the public vacancy apply test).
        form_response = self.url_open("/my/preferences")
        self.assertEqual(form_response.status_code, 200)
        token = None
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', form_response.text)
        if match:
            token = match.group(1)
        payload = {"sms_opt_in": "", "sms_opt_in_marketing": ""}
        if token:
            payload["csrf_token"] = token
        # url_open follows redirects by default, so the POST would resolve to the
        # final 200 page. Use open_functional (allow_redirects=False) to capture
        # the controller's own redirect verdict.
        resp = open_functional(self, "/my/preferences/save", data=payload)
        self.assertIn(
            resp.status_code,
            REDIRECT_CODES,
            f"save must redirect back to /my/preferences, got {resp.status_code}.",
        )
        location = strip_lang_prefix(location_path(resp))
        self.assertTrue(
            location.rstrip("/").endswith("/my/preferences"),
            f"save must redirect to /my/preferences, got {location!r}.",
        )
        self.assertFalse(
            self.parent_partner.sms_opt_in,
            "sms_opt_in must be False after the parent opts out of SMS.",
        )


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestSmsOptOutFiltering(TransactionCase):
    """Unit-level: sms_opt_in=False drops the partner from CRITICAL SMS dispatch."""

    def setUp(self):
        super().setUp()
        self.partner = self.env["res.partner"].create(
            {
                "name": "QA OptOut Partner",
                "email": "qa_optout@campscout.test",
                "sms_opt_in": False,
            }
        )
        self.sms_model = self.env["mail.thread"]

    def test_opted_out_partner_dropped_from_critical_sms(self):
        """F-MY-5: CRITICAL SMS must NOT be sent to an opted-out partner."""
        filtered = self.sms_model._campscout_filter_sms_recipients(self.partner, "CRITICAL")
        self.assertNotIn(
            self.partner,
            filtered,
            "An opted-out partner must be dropped from CRITICAL SMS dispatch.",
        )

    def test_opted_in_partner_kept_for_critical_sms(self):
        """Control: an opted-in partner IS kept for CRITICAL SMS."""
        self.partner.sms_opt_in = True
        filtered = self.sms_model._campscout_filter_sms_recipients(self.partner, "CRITICAL")
        self.assertIn(
            self.partner,
            filtered,
            "An opted-in partner must be kept for CRITICAL SMS dispatch.",
        )
