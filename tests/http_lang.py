# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Language-prefix-agnostic HTTP helpers for portal HttpCase tests.

With two active website languages (R2 bilingual PL/UA) every /my/* request
made in a non-default language gets an EXTRA 3xx hop that merely rewrites the
URL to its language-prefixed form (`/my/x` → `/pl/my/x`) before the actual
controller — and its ownership gate — runs. Tests that assert on the FIRST
redirect Location would mistake that rewrite for the functional redirect.

These helpers follow ONLY such language rewrites (same path modulo a leading
language segment) and hand back the first *functional* response, so isolation
asserts keep testing the ownership gate — not the router's i18n plumbing.
"""

from urllib.parse import urlparse

REDIRECT_CODES = (301, 302, 303, 307, 308)

# Portal pages render lazily (first hit triggers asset-bundle generation and
# heavy KPI/qualification queries), so a single request can take well over the
# 12s default `url_open` read timeout — which made HttpCase tests flaky with
# `requests.exceptions.ReadTimeout`. Use a generous timeout for all HTTP calls.
HTTP_TIMEOUT = 60

# url_code segments Odoo emits for the languages this module activates
# (see hooks._setup_bilingual_languages). Deliberately explicit — a generic
# 2-letter regex would swallow real path segments like '/my'.
_LANG_SEGMENTS = {"pl", "uk", "en", "pl_PL", "uk_UA", "en_US"}


def strip_lang_prefix(path):
    """Drop one leading language segment: '/pl/my/x' → '/my/x'."""
    parts = path.split("/", 2)
    if len(parts) >= 2 and parts[1] in _LANG_SEGMENTS:
        return "/" + parts[2] if len(parts) == 3 else "/"
    return path


def lang_prefix_of(path):
    """Return the language prefix of *path* ('/pl'; '' when unprefixed)."""
    parts = path.split("/", 2)
    if len(parts) >= 2 and parts[1] in _LANG_SEGMENTS:
        return "/" + parts[1]
    return ""


def location_path(response):
    """Path component of a redirect response's Location header."""
    return urlparse(response.headers.get("Location", "")).path


def open_functional(case, url, max_hops=3, timeout=HTTP_TIMEOUT, **kw):
    """`url_open(allow_redirects=False)` that skips language rewrites.

    Follows a redirect ONLY while its Location is the same path modulo the
    language prefix (a pure i18n rewrite). Returns the first response that is
    either not a redirect or redirects to a genuinely different path — i.e.
    the controller's own verdict.

    `timeout` defaults to :data:`HTTP_TIMEOUT` (60s) because portal pages
    render lazily and can exceed Odoo's 12s default read timeout.
    """
    current = url
    response = case.url_open(current, allow_redirects=False, timeout=timeout, **kw)
    for _ in range(max_hops):
        if response.status_code not in REDIRECT_CODES:
            return response
        target = location_path(response)
        if strip_lang_prefix(target) != strip_lang_prefix(urlparse(current).path):
            return response
        current = response.headers.get("Location", "")
        response = case.url_open(current, allow_redirects=False, timeout=timeout, **kw)
    return response
