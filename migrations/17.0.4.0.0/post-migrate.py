# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""ADR-22 — Role canon consolidation, data migration.

Both camp.staff.role and camp.staff.vacancy.role moved to ONE canonical
Selection (_role_taxonomy.CAMP_ROLE_SELECTION). Existing rows still hold the
legacy keys; the new Selection would reject them on the next ORM read/write
(ValueError / invalid selection). This script rewrites every legacy key to its
canonical value via RAW SQL — it MUST run in the same `-u` as the model change,
BEFORE any ORM validation touches those rows.

Legacy → canon (mirror of _role_taxonomy.LEGACY_ROLE_MAP, kept inline so the
migration is self-contained and does not import module python at upgrade time):

  camp_staff.role:
    director, leader        -> kierownik
    counselor               -> wychowawca
    activity_lead           -> instruktor
    medic                   -> ratownik
    kitchen_staff           -> kuchnia
    logistics               -> logistyka
  camp_staff_vacancy.role:
    instructor              -> instruktor
    (wychowawca, kierownik already canonical)

Idempotent: re-running maps nothing (no legacy keys remain); canonical keys are
never touched because they are not in the WHERE IN list.
"""
import logging

_logger = logging.getLogger(__name__)

# old DB value -> canonical value. Same map for both tables; a table simply has
# no rows for keys it never used, so the extra entries are harmless no-ops.
_LEGACY_TO_CANON = {
    "director": "kierownik",
    "leader": "kierownik",
    "counselor": "wychowawca",
    "activity_lead": "instruktor",
    "medic": "ratownik",
    "kitchen_staff": "kuchnia",
    "logistics": "logistyka",
    "instructor": "instruktor",
}

# (table, role column) pairs to migrate.
_TARGETS = [
    ("camp_staff", "role"),
    ("camp_staff_vacancy", "role"),
]


def _table_exists(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
        (table,),
    )
    return bool(cr.fetchone())


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        # Fresh install — models already define the canonical Selection,
        # there are no legacy rows to migrate.
        return

    total = 0
    for table, column in _TARGETS:
        if not _table_exists(cr, table) or not _column_exists(cr, table, column):
            _logger.info("[ADR-22] %s.%s absent — skipped.", table, column)
            continue

        for legacy, canon in _LEGACY_TO_CANON.items():
            cr.execute(
                f'UPDATE "{table}" SET "{column}" = %s '
                f'WHERE "{column}" = %s',  # noqa: S608 — table/col are static constants above
                (canon, legacy),
            )
            if cr.rowcount:
                _logger.info(
                    "[ADR-22] %s.%s: %d row(s) '%s' -> '%s'.",
                    table,
                    column,
                    cr.rowcount,
                    legacy,
                    canon,
                )
                total += cr.rowcount

    # Verify: no legacy key may survive in either table (would break Selection).
    legacy_keys = tuple(_LEGACY_TO_CANON.keys())
    for table, column in _TARGETS:
        if not _table_exists(cr, table) or not _column_exists(cr, table, column):
            continue
        cr.execute(
            f'SELECT "{column}", count(*) FROM "{table}" '
            f'WHERE "{column}" IN %s GROUP BY "{column}"',  # noqa: S608 — static identifiers
            (legacy_keys,),
        )
        leftovers = cr.fetchall()
        if leftovers:
            # Loud signal — should be impossible after the UPDATEs above.
            _logger.error(
                "[ADR-22] %s.%s still holds legacy keys after migration: %s",
                table,
                column,
                leftovers,
            )

    _logger.info("[ADR-22] Role canon migration complete — %d row(s) rewritten.", total)
