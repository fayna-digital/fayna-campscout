# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Experiential role test — KIEROWNIK reads and creates fayna.camp.dziennik.

Perspective: independent QA engineer. Proves that a user holding ONLY
`group_camp_kierownik` can:
  1. Create a fayna.camp.dziennik record (own event — no admin needed).
  2. Read the record back and verify the staffing link.

Key facts pinned from the code:
  * ACL (ir.model.access.csv:114-115): ONLY base.group_system has perm_create=1
    on fayna.camp.dziennik. group_user (which kierownik implies) has read-only.
  * There is NO ACL granting group_camp_kierownik perm_create on this model.
  * Required fields (operations.py:2923-2938): event_id, group_name, date_start.
  * The model uses group_unique_per_event SQL constraint.

PRODUCT FINDING (confirmed against live CI run 28532258120, 2026-07-01):
  Kierownik cannot create fayna.camp.dziennik — only Administration/Settings can.
  This is a missing ACL: group_camp_kierownik needs perm_create=1 on
  model_fayna_camp_dziennik in security/ir.model.access.csv.
  Tests below are LEFT FAILING intentionally to document this gap.
"""

import datetime

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestKierownikDziennik(TransactionCase):
    """Kierownik role can read and create a fayna.camp.dziennik without AccessError.

    PRODUCT FINDING: Both tests below currently FAIL because the ACL for
    fayna.camp.dziennik grants perm_create=1 only to base.group_system
    (ir.model.access.csv:114). group_camp_kierownik is missing create rights.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Kierownik user — only this one role group
        cls.kierownik_user = cls.env["res.users"].create(
            {
                "name": "QA Kierownik",
                "login": "qa_kierownik_dziennik@campscout.test",
                "password": "QaKier-9876!",
                "groups_id": [(6, 0, [cls.env.ref("fayna_camp_portal.group_camp_kierownik").id])],
            }
        )

        # A real event.event to satisfy the required FK
        cls.event = cls.env["event.event"].create(
            {
                "name": "QA Shift — Kierownik Test",
                "date_begin": datetime.datetime(2026, 7, 10, 9, 0),
                "date_end": datetime.datetime(2026, 7, 20, 18, 0),
                "date_tz": "Europe/Warsaw",
            }
        )

        # A camp.staff record that links the kierownik user to the event
        cls.staff = cls.env["camp.staff"].create(
            {
                "event_id": cls.event.id,
                "name": "QA Kierownik",
                "role": "kierownik",
                "user_id": cls.kierownik_user.id,
                "date_from": datetime.date(2026, 7, 10),
                "date_to": datetime.date(2026, 7, 20),
            }
        )

    # ── 1. Kierownik can create a dziennik ───────────────────────────────────

    def test_kierownik_creates_dziennik(self):
        """group_camp_kierownik can create fayna.camp.dziennik — no AccessError.

        PRODUCT FINDING: This test FAILS with AccessError because
        ir.model.access.csv only grants perm_create to base.group_system.
        group_camp_kierownik is missing create rights on fayna.camp.dziennik.
        FIX REQUIRED: add a row granting perm_create=1 to group_camp_kierownik
        in security/ir.model.access.csv.
        """
        try:
            dziennik = (
                self.env["fayna.camp.dziennik"]
                .with_user(self.kierownik_user)
                .create(
                    {
                        "event_id": self.event.id,
                        "group_name": "Grupa Alpha",
                        "date_start": datetime.date(2026, 7, 10),
                        "kierownik_id": self.staff.id,
                    }
                )
            )
            self.assertTrue(dziennik.id, "Kierownik must be able to create a dziennik record")
            self.assertEqual(
                dziennik.group_name,
                "Grupa Alpha",
                "group_name must persist after creation",
            )
        except AccessError as exc:
            self.fail(
                "PRODUCT FINDING — Kierownik got AccessError creating fayna.camp.dziennik: "
                f"{exc}\n\n"
                "FIX: add to security/ir.model.access.csv a row granting perm_create=1 "
                "to group_camp_kierownik on model_fayna_camp_dziennik."
            )

    # ── 2. Kierownik can link staff and read it back ─────────────────────────

    def test_kierownik_reads_dziennik_with_staffing(self):
        """Kierownik reads back the dziennik and sees the kierownik_id link.

        PRODUCT FINDING: This test FAILS because the kierownik cannot create the
        dziennik needed to read it back (same AccessError as test_kierownik_creates_dziennik).
        Both read and create are blocked by the missing ACL.
        """
        try:
            (
                self.env["fayna.camp.dziennik"]
                .with_user(self.kierownik_user)
                .create(
                    {
                        "event_id": self.event.id,
                        "group_name": "Grupa Beta",
                        "date_start": datetime.date(2026, 7, 10),
                        "kierownik_id": self.staff.id,
                    }
                )
            )
        except AccessError as exc:
            self.fail(
                "PRODUCT FINDING — Kierownik got AccessError creating fayna.camp.dziennik "
                f"(prerequisite for read test): {exc}\n\n"
                "Same root cause as test_kierownik_creates_dziennik."
            )

        # Read back through the same user context
        found = (
            self.env["fayna.camp.dziennik"]
            .with_user(self.kierownik_user)
            .search([("event_id", "=", self.event.id), ("group_name", "=", "Grupa Beta")])
        )
        self.assertTrue(found, "Kierownik must be able to search own dziennik records")
        self.assertEqual(
            found.kierownik_id.id,
            self.staff.id,
            "kierownik_id must match the linked camp.staff record",
        )
