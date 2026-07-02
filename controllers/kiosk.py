# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Kiosk shell controller for CampScout (TZ §4).

Two JSON-RPC endpoints:
  /camp/kiosk/layout        → per-role tile grid (called by CampKiosk OWL)
  /camp/kiosk/toggle_visible → bool: should the "↔ Odoo" systray show?

Layout is computed server-side from env.user groups — no role logic in JS.
Each tile: {label, icon, action, color, description?}
  action = xmlid string that doAction() resolves (string xmlid or tag).

Actions referenced must exist in the module; missing xmlids are silently
skipped so a partial install never crashes the kiosk (Reliability §0b).
"""

import logging

from odoo import _, http

# Single source of truth for the accepted UI languages (defined in hooks.py).
# Importing keeps the kiosk switcher and the language-setup hook in lockstep —
# no risk of the endpoint accepting a locale the module never activates. Safe
# from circular import: controllers is imported before hooks in __init__.py and
# hooks.py imports nothing from this package.
from odoo.addons.fayna_camp_portal.hooks import _BILINGUAL_LANGS
from odoo.http import request
from odoo.tools.translate import _lt

_logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Tile definitions per role (server-side).
# Each entry: (xmlid_or_tag, label, icon, color, description_or_None)
#
# xmlid_or_tag is passed verbatim to Odoo doAction().  Use the full external
# id string (module.action_name) so Odoo resolves it to the action dict.
# color: Bootstrap suffix — primary / success / warning / danger / info.
#
# label / description are wrapped in _lt (LAZY translation), not _().  These
# lists are built at MODULE IMPORT time, where there is no user/request lang
# context — a plain _() would freeze the term to whatever language is active at
# import (the server default).  _lt returns a lazy proxy whose translation is
# resolved at str() time (verified: odoo/tools/translate.py::_lt.__str__ reads
# the CURRENT context lang).  _resolve_tiles() therefore calls str() on them
# inside the JSON request — where request.env carries the caller's lang — so
# each tile is serialised in the user's own language.  _lt is also recognised
# by Odoo's PO extractor, so the strings land in the .pot for translation.
# ──────────────────────────────────────────────────────────────────────────────

_KIEROWNIK_TILES = [
    (
        "fayna_camp_portal.action_camp_create_wizard",
        _lt("Nowy obóz"),
        "plus-circle",
        "warning",
        _lt("Stwórz nowy obóz (kreator)"),
    ),
    (
        "fayna_camp_portal.action_camp_moje_obozy",
        _lt("Moje obozy"),
        "suitcase",
        "primary",
        _lt("Moje zmiany — wybierz obóz"),
    ),
    (
        "fayna_camp_portal.action_camp_staff",
        _lt("Kadra"),
        "users",
        "primary",
        _lt("Mój obóz — pracownicy"),
    ),
    (
        "fayna_camp_portal.action_camp_group",
        _lt("Grupy"),
        "sitemap",
        "primary",
        _lt("Grupy wychowawcze"),
    ),
    (
        "fayna_camp_portal.action_camp_program_wypoczynku",
        _lt("Program"),
        "calendar",
        "success",
        _lt("Program wypoczynku"),
    ),
    (
        "fayna_camp_portal.camp_teczka_ko_action",
        _lt("Dokumenty"),
        "folder-open",
        "success",
        _lt("Teczka kontroli KO"),
    ),
    (
        "fayna_camp_portal.action_camp_budget",
        _lt("Budżet"),
        "money",
        "warning",
        _lt("BEP / marże"),
    ),
    (
        "fayna_camp_portal.action_camp_incident_report",
        _lt("Sytuacje"),
        "exclamation-triangle",
        "danger",
        _lt("Zdarzenia nadzwyczajne"),
    ),
    (
        "fayna_camp_portal.action_camp_daily_report",
        _lt("Raport dnia"),
        "file-text-o",
        "info",
        _lt("Raport dzienny §2.11"),
    ),
]

_WYCHOWAWCA_TILES = [
    (
        "fayna_camp_portal.action_camp_group",
        _lt("Moja grupa"),
        "users",
        "primary",
        _lt("Grupy wychowawcze"),
    ),
    (
        "fayna_camp_portal.action_camp_participant",
        _lt("Karty"),
        "id-card",
        "primary",
        _lt("Karty kwalifikacyjne"),
    ),
    (
        "fayna_camp_portal.action_fayna_camp_dziennik",
        _lt("Dziennik"),
        "book",
        "success",
        _lt("Dziennik zajęć (Zał. 5)"),
    ),
    (
        "fayna_camp_portal.action_camp_program_structured_wychowawca",
        _lt("Mój program"),
        "calendar-check-o",
        "success",
        _lt("Program dnia"),
    ),
    (
        "fayna_camp_portal.action_camp_incident_report",
        _lt("Zdarzenie"),
        "exclamation-triangle",
        "danger",
        _lt("Zgłoś zdarzenie"),
    ),
]

_INSTRUCTOR_TILES = [
    (
        "fayna_camp_portal.action_camp_activity",
        _lt("Zajęcia"),
        "flag",
        "primary",
        _lt("Moje aktywności"),
    ),
    (
        "fayna_camp_portal.action_camp_incident_report",
        _lt("Bezpieczeństwo"),
        "shield",
        "danger",
        _lt("Zgłoś zdarzenie"),
    ),
    (
        "fayna_camp_portal.action_camp_participant",
        _lt("Uczestnicy"),
        "child",
        "info",
        _lt("Lista uczestników zajęć"),
    ),
]

_TILES_BY_GROUP = [
    # Checked in priority order; first match wins.
    ("fayna_camp_portal.group_camp_kierownik", _KIEROWNIK_TILES),
    ("fayna_camp_portal.group_camp_wychowawca", _WYCHOWAWCA_TILES),
    ("fayna_camp_portal.group_camp_instructor", _INSTRUCTOR_TILES),
]

_TOGGLE_GROUPS = [
    "base.group_system",
    "fayna_camp_portal.group_camp_organizator",
]


def _resolve_tiles(env, raw_tiles):
    """Filter tile list to only include actions that exist in the DB.

    Uses env.ref() with raise_if_not_found=False; silently drops unknown
    xmlids so a partial install never crashes the kiosk (Reliability §0b).
    Returns list of tile dicts.
    """
    result = []
    for xmlid, label, icon, color, description in raw_tiles:
        # Verify the action record exists before sending to the client.
        try:
            record = env.ref(xmlid, raise_if_not_found=False)
            if not record:
                _logger.debug("camp kiosk: action xmlid not found, skipping tile: %s", xmlid)
                continue
        except Exception:
            _logger.warning("camp kiosk: error resolving xmlid %s, skipping", xmlid, exc_info=True)
            continue

        # Resolve the lazy _lt proxies to concrete strings HERE, inside the
        # request, so translation happens in the caller's language before the
        # dict is JSON-serialised (a raw _lt proxy is not JSON-serialisable).
        result.append(
            {
                "action": xmlid,
                "label": str(label),
                "icon": icon,
                "color": color,
                "description": str(description) if description else description,
            }
        )
    return result


class CampKioskController(http.Controller):
    """Kiosk layout and toggle visibility endpoints."""

    @http.route(
        "/camp/kiosk/layout",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def kiosk_layout(self, **kw):
        """Return tile grid for the current user's kiosk role.

        Returns:
            {"tiles": [{label, icon, action, color, description?}, ...]}
            {"tiles": [], "error": "..."} if no matching role found.
        """
        env = request.env
        user = env.user

        for group_xmlid, raw_tiles in _TILES_BY_GROUP:
            if user.has_group(group_xmlid):
                tiles = _resolve_tiles(env, raw_tiles)
                return {"tiles": tiles}

        # User has none of the kiosk roles — return empty with a message.
        _logger.warning(
            "camp kiosk: user %s (%d) accessed /camp/kiosk/layout without a kiosk role",
            user.login,
            user.id,
        )
        return {
            "tiles": [],
            "error": _("Brak uprawnień do kiosku. Skontaktuj się z organizatorem."),
        }

    @http.route(
        "/camp/kiosk/toggle_visible",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def kiosk_toggle_visible(self, **kw):
        """Return whether the "↔ Odoo" toggle should be shown in systray.

        Visible only to base.group_system or group_camp_organizator.
        Returns:
            {"visible": True/False}
        """
        user = request.env.user
        visible = any(user.has_group(g) for g in _TOGGLE_GROUPS)
        return {"visible": visible}

    @http.route(
        "/camp/kiosk/back_visible",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def kiosk_back_visible(self, **kw):
        """Return whether the "← Powrót" (back to fullscreen kiosk) systray
        button should be shown.

        Mirror image of toggle_visible: the back button is for the kiosk roles
        (kierownik / wychowawca / instructor) who land in the standard backend
        after tapping a tile, NOT for admin/organizator (they have the toggle).
        Returns:
            {"visible": True/False}
        """
        user = request.env.user
        visible = any(user.has_group(group_xmlid) for group_xmlid, _tiles in _TILES_BY_GROUP)
        return {"visible": visible}

    @http.route(
        "/camp/kiosk/set_lang",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def kiosk_set_lang(self, lang=None, **kw):
        """Persist the current user's UI language (kiosk PL/UA switcher, R2).

        The kiosk is an OWL client-action, so the native portal language
        selector does not apply — this endpoint backs the in-header toggle.
        Writes res.users.lang with sudo() (a user may not have write access to
        their own res.users record) after validating the code against the set
        of ACTIVE res.lang, so the client can never park a user on an
        uninstalled / inactive locale.

        Input:  {"lang": "pl_PL" | "uk_UA"}
        Output: {"ok": True} on success, else {"ok": False, "error": "..."}.
        """
        if not lang:
            return {"ok": False, "error": _("No language specified.")}

        # Only the module's own bilingual set (pl_PL / uk_UA) is switchable from
        # the kiosk — never an arbitrary active locale the deployment happens to
        # have enabled (R2). This gate runs first, before the DB round-trip.
        if lang not in _BILINGUAL_LANGS:
            _logger.warning("camp kiosk: rejected set_lang to non-bilingual lang %r", lang)
            return {"ok": False, "error": _("Unsupported language: %s") % lang}

        # Belt-and-braces: the language must also be active in this DB (it is
        # activated by _setup_bilingual_languages on install/upgrade), so the
        # client can never park a user on an inactive/uninstalled locale.
        is_active = request.env["res.lang"].sudo().search_count(
            [("code", "=", lang), ("active", "=", True)]
        )
        if not is_active:
            _logger.warning("camp kiosk: rejected set_lang to inactive/unknown lang %r", lang)
            return {"ok": False, "error": _("Unsupported language: %s") % lang}

        request.env.user.sudo().write({"lang": lang})
        return {"ok": True}
