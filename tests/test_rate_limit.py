# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""N-9 — public-form rate-limit + retry-with-exponential-backoff.

Requirement (docs/TZ.md [N-9]):
  WHEN a bot or a single IP floods a public form (kadry-forms, /camp/vacancies),
  THEN the system rate-limits it (honeypot + IP-frequency), so it cannot spam.
  WHEN an outbound integration (KSeF, SMS, Zadarma, SendPulse) hits a transient
  failure, THEN the system retries with exponential backoff up to a cap, then
  logs and continues gracefully (never blocks the sale).

These are pure helpers in models/rate_limit.py, so they are unit-tested directly
with TransactionCase (no HTTP round-trip needed).
"""

from odoo.tests.common import TransactionCase, tagged

from ..models import rate_limit


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestPublicFormRateLimit(TransactionCase):
    """check_public_form_rate_limit: honeypot + IP-frequency gating."""

    def test_honeypot_filled_rejects(self):
        """A filled honeypot field means a bot → submission must be rejected."""
        allowed = rate_limit.check_public_form_rate_limit(
            self.env,
            "vacancy_apply",
            "203.0.113.10",
            honeypot_value="http://spam.example",
        )
        self.assertFalse(allowed, "A filled honeypot field must reject the submission.")

    def test_empty_honeypot_allows_first_submission(self):
        """A normal human (empty honeypot) is allowed within the limit."""
        allowed = rate_limit.check_public_form_rate_limit(
            self.env,
            "vacancy_apply",
            "203.0.113.20",
            honeypot_value="",
        )
        self.assertTrue(allowed, "First submission from a clean IP must be allowed.")

    def test_over_limit_rejects(self):
        """After max_per_window submissions, the same IP is rejected."""
        form = "submit_document"
        ip = "203.0.113.30"
        # Exhaust the window with the default max (5).
        for _ in range(5):
            allowed = rate_limit.check_public_form_rate_limit(self.env, form, ip, honeypot_value="")
            self.assertTrue(allowed, "Submissions within the limit must be allowed.")
        # The 6th submission within the window must be rejected.
        blocked = rate_limit.check_public_form_rate_limit(self.env, form, ip, honeypot_value="")
        self.assertFalse(blocked, "A 6th submission in the window must be rate-limited.")

    def test_different_ips_are_independent(self):
        """Rate-limit is keyed per IP, so different IPs do not share the budget."""
        form = "vacancy_apply"
        for _ in range(5):
            allowed = rate_limit.check_public_form_rate_limit(
                self.env, form, "203.0.113.40", honeypot_value=""
            )
            self.assertTrue(allowed, "Each IP has its own independent budget.")
        # A different IP is unaffected.
        other = rate_limit.check_public_form_rate_limit(
            self.env, form, "203.0.113.41", honeypot_value=""
        )
        self.assertTrue(other, "A different IP must not be affected by another IP's limit.")


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestRetryWithBackoff(TransactionCase):
    """retry_with_backoff: exponential retry, graceful degradation."""

    def test_returns_value_on_success(self):
        """A callable that succeeds on the first attempt returns its value."""
        result = rate_limit.retry_with_backoff(lambda: "ok", max_retries=2, base_delay=0)
        self.assertEqual(result, "ok")

    def test_retries_then_succeeds(self):
        """A callable that fails twice then succeeds returns the value."""
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ConnectionError("transient")
            return "recovered"

        result = rate_limit.retry_with_backoff(flaky, max_retries=3, base_delay=0, jitter=False)
        self.assertEqual(result, "recovered")
        self.assertEqual(calls["n"], 3, "Should have retried until the 3rd attempt.")

    def test_gives_up_gracefully_after_max_retries(self):
        """A persistently failing callable returns None (never raises)."""

        def always_fails():
            raise RuntimeError("permanent")

        result = rate_limit.retry_with_backoff(
            always_fails, max_retries=2, base_delay=0, jitter=False
        )
        self.assertIsNone(result, "After max_retries the helper must return None, not raise.")
