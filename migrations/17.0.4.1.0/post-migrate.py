# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""R2 — bilingual PL/UA activation on UPGRADE (fix-forward).

``post_init_hook`` fires ONLY on a fresh install (uninstalled → installed).
Existing databases (staging / prod are already on 17.0.4.0.0) upgraded via ``-u``
would otherwise never activate PL/UA, leaving the whole bilingual feature — the
kiosk language switcher, the /my portal selector, the ``_lt`` tiles — dead.

This migration lives in a NEW version folder (17.0.4.1.0 > the installed
17.0.4.0.0) precisely so Odoo re-runs it on the next ``-u``. It replays the same
idempotent setup as the install hook.

Idempotent: ``_setup_bilingual_languages`` is a no-op once the languages are
active, the default is set and each website already carries the languages, so
re-running on a later ``-u`` writes nothing. Own try/except so a translation
hiccup never aborts the upgrade.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        # Fresh install — post_init_hook already ran _setup_bilingual_languages.
        return
    try:
        from odoo import SUPERUSER_ID, api

        env = api.Environment(cr, SUPERUSER_ID, {})
        from odoo.addons.fayna_camp_portal.hooks import _setup_bilingual_languages

        _setup_bilingual_languages(env)
        _logger.info("[R2] bilingual PL/UA activated on upgrade (17.0.4.1.0).")
    except Exception:
        _logger.exception("[R2] bilingual language setup on upgrade failed (non-fatal)")
