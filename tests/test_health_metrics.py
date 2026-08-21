# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Tests for NFR 5a — N-6 health-check + N-7 observability (controllers/health.py).

Covers:
  1. ``GET /healthz`` → 200 "ok" (liveness), no auth required.
  2. ``GET /readyz``  → 200 "ready" when DB + ir_cron table present.
  3. ``GET /metrics`` → 200 Prometheus-text body with the SLI counters.
  4. ``bump_counter`` increments a stored counter and is idempotent/never raises.
"""

from odoo.addons.fayna_camp_portal.controllers.health import bump_counter
from odoo.tests.common import HttpCase, TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestHealthEndpoints(HttpCase):
    """HTTP-level checks for /healthz, /readyz and /metrics."""

    def test_healthz_liveness(self):
        resp = self.url_open("/healthz")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("ok", resp.text)

    def test_readyz_readiness(self):
        resp = self.url_open("/readyz")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("ready", resp.text)

    def test_metrics_prometheus_format(self):
        resp = self.url_open("/metrics")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/plain", resp.headers.get("Content-Type", ""))
        # Every declared SLI counter must appear in the body.
        for name in (
            "fayna_sms_sent_total",
            "fayna_sms_failed_total",
            "fayna_kamilka_escalated_total",
            "fayna_cron_runs_total",
            "fayna_cron_failed_total",
            "fayna_refund_processed_total",
            "fayna_refund_failed_total",
            "fayna_http_requests_total",
        ):
            self.assertIn(name, resp.text, f"missing SLI counter {name}")


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestMetricsCounters(TransactionCase):
    """Unit-level checks for the SLI counter helper."""

    def test_bump_counter_increments(self):
        params = self.env["ir.config_parameter"]
        params.set_param("fayna_sms_sent_total", "0")
        bump_counter(self.env, "fayna_sms_sent_total")
        bump_counter(self.env, "fayna_sms_sent_total")
        self.assertEqual(int(params.get_param("fayna_sms_sent_total", "0")), 2)

    def test_bump_counter_unknown_name_is_safe(self):
        # Unknown names must not raise and must not create a parameter.
        bump_counter(self.env, "fayna_does_not_exist_total")
        self.assertFalse(
            self.env["ir.config_parameter"].get_param("fayna_does_not_exist_total", False)
        )
