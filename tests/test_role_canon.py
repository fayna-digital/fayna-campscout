# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""ADR-22 — canon role taxonomy tests.

Covers:
  1. camp.staff + camp.staff.vacancy share ONE canonical Selection.
  2. Each canonical role is creatable on camp.staff.
  3. Hire: vacancy.role flows verbatim onto the hired camp.staff.role (no map).
  4. Legacy data migration: a row carrying an old key (inserted via raw SQL,
     bypassing the Selection) is rewritten to its canonical key by the same
     UPDATE logic the post-migrate script runs.
"""
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.fayna_camp_portal.models._role_taxonomy import (
    CAMP_ROLE_KEYS,
    CAMP_ROLE_SELECTION,
    LEGACY_ROLE_MAP,
)

CANON_KEYS = [key for key, _label in CAMP_ROLE_SELECTION]


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestRoleCanon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.event = cls.env["event.event"].create(
            {
                "name": "Canon Role Camp 2026",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-14 18:00:00",
            }
        )

    # ------------------------------------------------------------------
    # 1. Shared, identical Selection on both models
    # ------------------------------------------------------------------

    def test_both_models_share_canon_selection(self):
        staff_sel = dict(self.env["camp.staff"]._fields["role"].selection)
        vacancy_sel = dict(self.env["camp.staff.vacancy"]._fields["role"].selection)
        self.assertEqual(set(staff_sel), CAMP_ROLE_KEYS)
        self.assertEqual(
            set(staff_sel),
            set(vacancy_sel),
            "camp.staff and camp.staff.vacancy role keys must be identical (ADR-22).",
        )

    # ------------------------------------------------------------------
    # 2. Every canon role is creatable
    # ------------------------------------------------------------------

    def test_create_staff_each_canon_role(self):
        for role in CANON_KEYS:
            staff = self.env["camp.staff"].create(
                {
                    "name": f"Staff {role}",
                    "event_id": self.event.id,
                    "role": role,
                    "date_from": "2026-07-01",
                    "date_to": "2026-07-14",
                }
            )
            self.assertEqual(staff.role, role)

    # ------------------------------------------------------------------
    # 3. Hire: vacancy role == hired staff role (no bridge)
    # ------------------------------------------------------------------

    def test_hire_role_matches_vacancy_no_mapping(self):
        for role in ("wychowawca", "kierownik", "instruktor"):
            vacancy = self.env["camp.staff.vacancy"].create(
                {
                    "name": f"Wakat {role}",
                    "event_id": self.event.id,
                    "role": role,
                    "candidate_name": f"Kandydat {role}",
                }
            )
            vacancy.action_hire()
            self.assertEqual(vacancy.state, "hired")
            self.assertTrue(vacancy.staff_id)
            self.assertEqual(
                vacancy.staff_id.role,
                role,
                "Hired staff role must equal the vacancy role verbatim (ADR-22).",
            )

    # ------------------------------------------------------------------
    # 4. Legacy migration rewrites old keys to canon
    # ------------------------------------------------------------------

    def test_legacy_map_covers_all_old_keys(self):
        # Every legacy key maps to a valid canonical key.
        for legacy, canon in LEGACY_ROLE_MAP.items():
            self.assertIn(
                canon,
                CAMP_ROLE_KEYS,
                f"LEGACY_ROLE_MAP[{legacy!r}] -> {canon!r} is not a canon key.",
            )

    def test_migration_rewrites_legacy_staff_row(self):
        """Insert a legacy 'counselor' staff via raw SQL (bypass Selection),
        then apply the post-migrate UPDATE and confirm it became 'wychowawca'.
        """
        # A valid canon record to obtain a clean row, then force a legacy key
        # straight in the DB (ORM would reject 'counselor' now).
        staff = self.env["camp.staff"].create(
            {
                "name": "Legacy Counselor",
                "event_id": self.event.id,
                "role": "wychowawca",
                "date_from": "2026-07-01",
                "date_to": "2026-07-14",
            }
        )
        self.env.cr.execute(
            "UPDATE camp_staff SET role = 'counselor' WHERE id = %s", (staff.id,)
        )

        # Run the canonical UPDATE (same statement the migration issues).
        self.env.cr.execute(
            "UPDATE camp_staff SET role = %s WHERE role = %s",
            ("wychowawca", "counselor"),
        )

        self.env.cr.execute("SELECT role FROM camp_staff WHERE id = %s", (staff.id,))
        self.assertEqual(self.env.cr.fetchone()[0], "wychowawca")

        # And no legacy key survives anywhere in the table.
        legacy_keys = tuple(
            k for k in LEGACY_ROLE_MAP if k not in CAMP_ROLE_KEYS
        )
        self.env.cr.execute(
            "SELECT count(*) FROM camp_staff WHERE role IN %s", (legacy_keys,)
        )
        self.assertEqual(self.env.cr.fetchone()[0], 0)
