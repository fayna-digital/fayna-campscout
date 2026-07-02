# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Post-install hooks for fayna_camp_portal.

Strangler Fig migration: transfer ownership of ir.model.data records
from old module names to fayna_camp_portal so that existing data
(campscout_management, fayna_camp_qualification, etc.) is preserved.

This is a one-time migration — safe to run multiple times (idempotent).
"""

import logging

_logger = logging.getLogger(__name__)

# Modules whose ir.model.data records should be migrated to fayna_camp_portal.
# Only includes modules that have been FULLY absorbed into this module
# and no longer exist as separate installable modules.
_ABSORBED_MODULES = [
    "campscout_management",
    "fayna_camp_template",
    "fayna_camp_qualification",
    "fayna_camp_operations",
    "fayna_camp_nutrition",
    "fayna_camp_emergency",
    "fayna_camp_loyalty",
    "fayna_camp_sales",
    "fayna_camp_reviews",
    "fayna_camp_stories",
    "fayna_camp_program",
    "fayna_camp_dziennik_zajec",
    "fayna_camp_kuratorium",
    "fayna_camp_reports",
    "fayna_camp_transport",
    "fayna_camp_schedule",
    "fayna_instructor_school",
    "fayna_camp_vozhatyi_school",
    "fayna_sms_turbosms",
    "fayna_sms_base",
    "fayna_camp_sms_routing",
]

# ──────────────────────────────────────────────────────────────────────────────
# Bilingual UI (R2): the portal + kiosk are used by Ukrainian children in Poland.
# PL is the market/default language, UA is the second parent-facing language.
# ──────────────────────────────────────────────────────────────────────────────
_BILINGUAL_LANGS = ["pl_PL", "uk_UA"]
_DEFAULT_LANG = "pl_PL"


def _setup_bilingual_languages(env):
    """Activate PL + UA and make PL the default language (R2). Idempotent.

    Odoo-native, verified against odoo/17.0 source:

    * ``res.lang._activate_lang(code)`` only flips ``active = True`` (no-op if
      already active) and returns the record — it does NOT load .po terms.
      So for every language we *newly* activate we replay exactly what
      ``res.lang.toggle_active()`` / the ``base.language.install`` wizard do:
      ``ir.module.module._update_translations(codes)`` to pull each installed
      module's .po for the new languages. Without this, a fresh single install
      would leave the languages active but untranslated.

    * ``ir.default.set('res.partner', 'lang', 'pl_PL')`` makes every NEW partner
      (portal parents, staff users) default to Polish, overriding the field
      default without patching core. Guarded by ``_get`` so a re-run / ``-u``
      never clobbers a value an admin set afterwards.

    * The company's own partner language drives company-context rendering
      (server-generated documents); aligned to PL only when still on the Odoo
      install default (``en_US``/unset), never overriding a deliberate choice.
    """
    Lang = env["res.lang"]

    newly_activated = []
    for code in _BILINGUAL_LANGS:
        existing = Lang.with_context(active_test=False).search([("code", "=", code)])
        was_active = bool(existing.active)
        lang = Lang._activate_lang(code)  # native activation, idempotent
        if lang and not was_active:
            newly_activated.append(code)

    if newly_activated:
        _logger.info(
            "fayna_camp_portal: activated languages %s — loading module translations",
            ", ".join(newly_activated),
        )
        installed_mods = env["ir.module.module"].search([("state", "=", "installed")])
        # filter_lang accepts a list of codes (odoo/17.0 ir_module.py); overwrite
        # defaults to False so existing custom translations are preserved.
        installed_mods._update_translations(newly_activated)

    # Default language PL for NEW partners/users. Set when there is no default yet
    # OR the default is still Odoo's install-default en_US — but never override a
    # deliberate admin choice of another language (mirrors the company-partner guard
    # below). Odoo ships an en_US default for res.partner.lang, so an `is None` guard
    # would leave new partners on English.
    current_default = env["ir.default"]._get("res.partner", "lang")
    if current_default in (None, False, "en_US"):
        env["ir.default"].set("res.partner", "lang", _DEFAULT_LANG)
        _logger.info("fayna_camp_portal: default res.partner.lang set to %s", _DEFAULT_LANG)

    company_partner = env.company.partner_id
    if company_partner.lang in (False, "en_US"):
        company_partner.lang = _DEFAULT_LANG
        _logger.info("fayna_camp_portal: company partner language aligned to %s", _DEFAULT_LANG)


def post_init_hook(env):
    """Transfer ir.model.data ownership from absorbed modules to fayna_camp_portal.

    Uses direct SQL for performance — avoids loading 10k+ records into ORM.
    Skips modules that are still installed (safety guard against accidental migration).

    Also activates the bilingual PL/UA UI and sets PL as the default language
    (R2) — see ``_setup_bilingual_languages``.
    """
    # R2 — bilingual PL/UA UI + default PL (idempotent, own try/except so a
    # translation hiccup never aborts the ir.model.data migration below).
    try:
        _setup_bilingual_languages(env)
    except Exception:
        _logger.exception("fayna_camp_portal: bilingual language setup failed (non-fatal)")

    cr = env.cr

    # Find which of the absorbed modules are actually installed
    cr.execute(
        "SELECT name FROM ir_module_module WHERE name = ANY(%s) AND state = 'installed'",
        (_ABSORBED_MODULES,),
    )
    still_installed = {row[0] for row in cr.fetchall()}

    modules_to_migrate = [m for m in _ABSORBED_MODULES if m not in still_installed]

    if not modules_to_migrate:
        _logger.info("fayna_camp_portal post_init_hook: no modules to migrate")
        return

    _logger.info(
        "fayna_camp_portal post_init_hook: migrating ir.model.data from %d modules: %s",
        len(modules_to_migrate),
        ", ".join(modules_to_migrate),
    )

    for module_name in modules_to_migrate:
        # Delete source records that would collide with existing fayna_camp_portal entries
        cr.execute(
            """
            DELETE FROM ir_model_data
            WHERE module = %s
              AND name IN (
                  SELECT name FROM ir_model_data WHERE module = 'fayna_camp_portal'
              )
            """,
            (module_name,),
        )
        deleted = cr.rowcount
        if deleted:
            _logger.info(
                "fayna_camp_portal post_init_hook: skipped %d duplicate records from %s",
                deleted,
                module_name,
            )

        cr.execute(
            """
            UPDATE ir_model_data
            SET module = 'fayna_camp_portal'
            WHERE module = %s
            """,
            (module_name,),
        )
        count = cr.rowcount
        if count:
            _logger.info(
                "fayna_camp_portal post_init_hook: migrated %d records from %s",
                count,
                module_name,
            )
