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

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Tile definitions per role (server-side).
# Each entry: (xmlid_or_tag, label, icon, color, description_or_None)
#
# xmlid_or_tag is passed verbatim to Odoo doAction().  Use the full external
# id string (module.action_name) so Odoo resolves it to the action dict.
# color: Bootstrap suffix — primary / success / warning / danger / info.
# ──────────────────────────────────────────────────────────────────────────────

_KIEROWNIK_TILES = [
    (
        "fayna_camp_portal.action_camp_create_wizard",
        "Nowy obóz",
        "plus-circle",
        "warning",
        "Stwórz nowy obóz (kreator)",
    ),
    (
        "fayna_camp_portal.action_camp_staff",
        "Kadra",
        "users",
        "primary",
        "Mój obóz — pracownicy",
    ),
    (
        "fayna_camp_portal.action_camp_group",
        "Grupy",
        "sitemap",
        "primary",
        "Grupy wychowawcze",
    ),
    (
        "fayna_camp_portal.action_camp_program_wypoczynku",
        "Program",
        "calendar",
        "success",
        "Program wypoczynku",
    ),
    (
        "fayna_camp_portal.camp_teczka_ko_action",
        "Dokumenty",
        "folder-open",
        "success",
        "Teczka kontroli KO",
    ),
    (
        "fayna_camp_portal.action_camp_budget",
        "Budżet",
        "money",
        "warning",
        "BEP / marże",
    ),
    (
        "fayna_camp_portal.action_camp_incident_report",
        "Sytuacje",
        "exclamation-triangle",
        "danger",
        "Zdarzenia nadzwyczajne",
    ),
    (
        "fayna_camp_portal.action_camp_daily_report",
        "Raport dnia",
        "file-text-o",
        "info",
        "Raport dzienny §2.11",
    ),
]

_WYCHOWAWCA_TILES = [
    (
        "fayna_camp_portal.action_camp_group",
        "Moja grupa",
        "users",
        "primary",
        "Grupy wychowawcze",
    ),
    (
        "fayna_camp_portal.action_camp_participant",
        "Karty",
        "id-card",
        "primary",
        "Karty kwalifikacyjne",
    ),
    (
        "fayna_camp_portal.action_fayna_camp_dziennik",
        "Dziennik",
        "book",
        "success",
        "Dziennik zajęć (Zał. 5)",
    ),
    (
        "fayna_camp_portal.action_camp_program_structured_wychowawca",
        "Mój program",
        "calendar-check-o",
        "success",
        "Program dnia",
    ),
    (
        "fayna_camp_portal.action_camp_incident_report",
        "Zdarzenie",
        "exclamation-triangle",
        "danger",
        "Zgłoś zdarzenie",
    ),
]

_INSTRUCTOR_TILES = [
    (
        "fayna_camp_portal.action_camp_activity",
        "Zajęcia",
        "flag",
        "primary",
        "Moje aktywności",
    ),
    (
        "fayna_camp_portal.action_camp_incident_report",
        "Bezpieczeństwo",
        "shield",
        "danger",
        "Zgłoś zdarzenie",
    ),
    (
        "fayna_camp_portal.action_camp_participant",
        "Uczestnicy",
        "child",
        "info",
        "Lista uczestników zajęć",
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
                _logger.debug(
                    "camp kiosk: action xmlid not found, skipping tile: %s", xmlid
                )
                continue
        except Exception:
            _logger.warning(
                "camp kiosk: error resolving xmlid %s, skipping", xmlid, exc_info=True
            )
            continue

        result.append(
            {
                "action": xmlid,
                "label": label,
                "icon": icon,
                "color": color,
                "description": description,
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
            "camp kiosk: user %s (%d) accessed /camp/kiosk/layout "
            "without a kiosk role",
            user.login,
            user.id,
        )
        return {
            "tiles": [],
            "error": "Brak uprawnień do kiosku. Skontaktuj się z organizatorem.",
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
