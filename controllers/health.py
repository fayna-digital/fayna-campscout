# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""NFR 5a — N-6 health-check (liveness/readiness) + N-7 observability (SLO/SLI).

Implements:
- ``GET /healthz``  — liveness: the Odoo process is up and serving HTTP.
- ``GET /readyz``   — readiness: core dependencies (DB reachable, cron table
  present) are available so the instance can serve traffic.
- ``GET /metrics``  — Prometheus-text-format metrics for key SLO/SLI counters.

Both health endpoints are deliberately ``auth="none"`` and dependency-light so
an orchestrator (Hetzner load balancer / UptimeRobot / k8s probe) can poll them
without a session. They must never raise on a healthy instance.

Security note: ``/metrics`` exposes only aggregate counters (no PII, no
per-record data). It is read-only and safe to expose to the monitoring stack.
"""

import logging
import time

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Prometheus text-format content type.
_PROMETHEUS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

# SLI counters we track. Each is a monotonic counter exposed on /metrics.
# Keys are the prometheus metric names (no PII).
_SLI_COUNTERS = {
    "fayna_sms_sent_total": "Total SMS messages dispatched.",
    "fayna_sms_failed_total": "Total SMS dispatch failures.",
    "fayna_kamilka_escalated_total": "Total Kamilka incidents escalated to backup.",
    "fayna_cron_runs_total": "Total cron cycles executed.",
    "fayna_cron_failed_total": "Total cron cycles that raised.",
    "fayna_refund_processed_total": "Total refunds processed.",
    "fayna_refund_failed_total": "Total refund attempts that failed.",
    "fayna_http_requests_total": "Total HTTP requests served by the portal.",
}


class CampscoutHealth(http.Controller):
    """Liveness, readiness and Prometheus metrics endpoints (N-6, N-7)."""

    @http.route("/healthz", type="http", auth="none", website=False, csrf=False)
    def healthz(self, **kw):
        """Liveness probe — the process is up and can answer HTTP."""
        return http.Response(
            "ok\n",
            status=200,
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )

    @http.route("/readyz", type="http", auth="none", website=False, csrf=False)
    def readyz(self, **kw):
        """Readiness probe — DB is reachable and core tables exist.

        Returns 200 when ready, 503 when the database is not reachable or the
        cron table is missing (e.g. mid-migration). Never raises.
        """
        try:
            # A trivial DB round-trip proves the connection pool is healthy.
            request.env.cr.execute("SELECT 1")
            request.env.cr.fetchone()
            # Confirm the Odoo cron table exists (core infra dependency).
            request.env.cr.execute(
                "SELECT 1 FROM information_schema.tables " "WHERE table_name = 'ir_cron' LIMIT 1"
            )
            if not request.env.cr.fetchone():
                return http.Response(
                    "not ready: ir_cron table missing\n",
                    status=503,
                    headers={"Content-Type": "text/plain; charset=utf-8"},
                )
        except Exception as exc:  # noqa: BLE001
            _logger.warning("[READYZ] readiness probe failed: %s", exc)
            return http.Response(
                f"not ready: {exc}\n",
                status=503,
                headers={"Content-Type": "text/plain; charset=utf-8"},
            )
        return http.Response(
            "ready\n",
            status=200,
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )

    @http.route("/metrics", type="http", auth="none", website=False, csrf=False)
    def metrics(self, **kw):
        """Prometheus-text-format metrics for SLO/SLI counters (N-7).

        Exposes only aggregate counters from ``ir.config_parameter`` (no PII).
        Each counter is stored as an integer config parameter so it survives
        restarts and can be incremented from any model/controller.
        """
        lines = []
        params = request.env["ir.config_parameter"].sudo()
        for name, help_text in _SLI_COUNTERS.items():
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} counter")
            try:
                value = int(params.get_param(name, "0"))
            except (TypeError, ValueError):
                value = 0
            lines.append(f"{name} {value}")
        body = "\n".join(lines) + "\n"
        return http.Response(
            body,
            status=200,
            headers={"Content-Type": _PROMETHEUS_CONTENT_TYPE},
        )


def bump_counter(env, name, delta=1):
    """Increment one of the SLI counters stored in ``ir.config_parameter``.

    Safe to call from any model/controller; never raises (best-effort).
    Unknown names are ignored so a typo cannot crash a hot path.
    """
    if name not in _SLI_COUNTERS:
        _logger.warning("[METRICS] unknown counter ignored: %s", name)
        return
    try:
        params = env["ir.config_parameter"].sudo()
        current = int(params.get_param(name, "0"))
        params.set_param(name, str(current + delta))
    except Exception as exc:  # noqa: BLE001
        _logger.warning("[METRICS] failed to bump %s: %s", name, exc)


def _now_ms():
    """Monotonic millisecond timestamp for latency SLIs (not exposed yet)."""
    return int(time.monotonic() * 1000)
