"""Post-install hooks for fayna_campscout.

Strangler Fig migration: transfer ownership of ir.model.data records
from old module names to fayna_campscout so that existing data
(campscout_management, fayna_camp_qualification, etc.) is preserved.

This is a one-time migration — safe to run multiple times (idempotent).
"""

import logging

_logger = logging.getLogger(__name__)

# Modules whose ir.model.data records should be migrated to fayna_campscout.
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


def post_init_hook(env):
    """Transfer ir.model.data ownership from absorbed modules to fayna_campscout.

    Uses direct SQL for performance — avoids loading 10k+ records into ORM.
    Skips modules that are still installed (safety guard against accidental migration).
    """
    cr = env.cr

    # Find which of the absorbed modules are actually installed
    cr.execute(
        "SELECT name FROM ir_module_module WHERE name = ANY(%s) AND state = 'installed'",
        (_ABSORBED_MODULES,),
    )
    still_installed = {row[0] for row in cr.fetchall()}

    modules_to_migrate = [m for m in _ABSORBED_MODULES if m not in still_installed]

    if not modules_to_migrate:
        _logger.info("fayna_campscout post_init_hook: no modules to migrate")
        return

    _logger.info(
        "fayna_campscout post_init_hook: migrating ir.model.data from %d modules: %s",
        len(modules_to_migrate),
        ", ".join(modules_to_migrate),
    )

    for module_name in modules_to_migrate:
        cr.execute(
            """
            UPDATE ir_model_data
            SET module = 'fayna_campscout'
            WHERE module = %s
              AND module != 'fayna_campscout'
            """,
            (module_name,),
        )
        count = cr.rowcount
        if count:
            _logger.info(
                "fayna_campscout post_init_hook: migrated %d records from %s",
                count,
                module_name,
            )
