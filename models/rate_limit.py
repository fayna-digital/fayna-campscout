# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""N-9 — general rate-limit for public forms + retry with exponential backoff.

Two concerns (docs/TZ.md [N-9]):

1. **Public-form rate limiting** — every public form (kadry-forms, /camp/vacancies)
   must apply a honeypot + IP-frequency limit, so bots cannot spam submissions.
   The limit is stored in ``ir.config_parameter`` (survives restart, no schema
   change) and keyed by IP + form name.

2. **Retry with exponential backoff** — outbound integrations (KSeF, SMS,
   Zadarma, SendPulse) must retry transient failures with exponential delay up
   to a cap, then log and continue gracefully (never block the sale).

Both are pure helpers — no model is required, so they are trivially unit-testable
and reusable from any controller or model.
"""

import logging
import random
import time

_logger = logging.getLogger(__name__)

#: Default window (seconds) within which submissions are counted.
DEFAULT_WINDOW_SECONDS = 300  # 5 minutes
#: Default max submissions per IP per window.
DEFAULT_MAX_PER_WINDOW = 5
#: Default honeypot field name (bots fill it; humans leave it empty).
DEFAULT_HONEYPOT_FIELD = "website"

#: Default backoff base delay (seconds) and multiplier.
DEFAULT_BACKOFF_BASE = 1.0
DEFAULT_BACKOFF_MULTIPLIER = 2.0
#: Default max retries before giving up gracefully.
DEFAULT_MAX_RETRIES = 3


def _param(env, key, default):
    """Read an ``ir.config_parameter`` with a default, tolerating missing rows."""
    try:
        value = env["ir.config_parameter"].sudo().get_param(key)
    except Exception:  # noqa: BLE001
        return default
    if not value:
        return default
    try:
        return type(default)(value)
    except (TypeError, ValueError):
        return default


def check_public_form_rate_limit(
    env,
    form_name,
    ip_address,
    honeypot_value=None,
    honeypot_field=DEFAULT_HONEYPOT_FIELD,
    max_per_window=None,
    window_seconds=None,
):
    """Enforce honeypot + IP-frequency limit on a public form submission.

    :param env: Odoo environment (``request.env`` or test env).
    :param form_name: Stable identifier of the form (e.g. ``"vacancy_apply"``).
    :param ip_address: Client IP (``request.httprequest.remote_addr``).
    :param honeypot_value: Value of the honeypot field from the POST. If truthy,
        the submission is a bot — returns ``False`` (reject) immediately.
    :param honeypot_field: Name of the honeypot field (for the config key).
    :param max_per_window: Override max submissions per window.
    :param window_seconds: Override window length.
    :returns: ``True`` if the submission is allowed, ``False`` if it must be
        rejected (bot or over the frequency limit).
    """
    # Honeypot: a filled hidden field means a bot.
    if honeypot_value:
        _logger.info(
            "fayna_camp_portal.rate_limit: honeypot triggered form=%s ip=%s",
            form_name,
            ip_address,
        )
        return False

    max_per_window = max_per_window or _param(
        env, f"fayna_camp_portal.rate_limit.{form_name}.max", DEFAULT_MAX_PER_WINDOW
    )
    window_seconds = window_seconds or _param(
        env,
        f"fayna_camp_portal.rate_limit.{form_name}.window",
        DEFAULT_WINDOW_SECONDS,
    )

    key = f"fayna_camp_portal.rate_limit.{form_name}.{ip_address}"
    now = time.time()
    try:
        raw = env["ir.config_parameter"].sudo().get_param(key)
    except Exception:  # noqa: BLE001
        raw = None

    timestamps = []
    if raw:
        try:
            timestamps = [float(t) for t in raw.split(",") if t]
        except ValueError:
            timestamps = []

    # Drop entries outside the window.
    cutoff = now - window_seconds
    timestamps = [t for t in timestamps if t > cutoff]

    if len(timestamps) >= max_per_window:
        _logger.warning(
            "fayna_camp_portal.rate_limit: over limit form=%s ip=%s count=%d",
            form_name,
            ip_address,
            len(timestamps),
        )
        return False

    # Record this submission and persist.
    timestamps.append(now)
    try:
        env["ir.config_parameter"].sudo().set_param(key, ",".join(f"{t:.3f}" for t in timestamps))
    except Exception:  # noqa: BLE001
        _logger.exception(
            "fayna_camp_portal.rate_limit: failed to persist counter form=%s ip=%s",
            form_name,
            ip_address,
        )
    return True


def retry_with_backoff(
    fn,
    *args,
    max_retries=DEFAULT_MAX_RETRIES,
    base_delay=DEFAULT_BACKOFF_BASE,
    multiplier=DEFAULT_BACKOFF_MULTIPLIER,
    jitter=True,
    logger=None,
    **kwargs,
):
    """Call ``fn`` retrying transient failures with exponential backoff.

    Retries only on the exceptions raised by ``fn`` itself (the caller decides
    which exceptions are transient by wrapping the call). After ``max_retries``
    attempts it logs the final error and returns ``None`` — graceful degradation,
    never blocking the surrounding business flow (N-9).

    :param fn: Callable to invoke.
    :param max_retries: Number of retries AFTER the first attempt.
    :param base_delay: Initial delay in seconds.
    :param multiplier: Exponential factor between attempts.
    :param jitter: Add random jitter to avoid thundering-herd retries.
    :param logger: Logger to use (defaults to module logger).
    :returns: ``fn``'s return value, or ``None`` if all attempts failed.
    """
    log = logger or _logger
    attempt = 0
    while True:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            attempt += 1
            if attempt > max_retries:
                log.error(
                    "fayna_camp_portal.backoff: giving up after %d attempts err=%s",
                    attempt,
                    exc,
                )
                return None
            delay = base_delay * (multiplier ** (attempt - 1))
            if jitter:
                # jitter for retry-backoff, not cryptographic
                delay *= random.uniform(0.5, 1.5)  # noqa: S311
            log.warning(
                "fayna_camp_portal.backoff: attempt %d/%d failed err=%s retrying in %.2fs",
                attempt,
                max_retries,
                exc,
                delay,
            )
            time.sleep(delay)


def client_ip(request):
    """Best-effort client IP from an Odoo ``http.request``."""
    try:
        return request.httprequest.remote_addr or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"
