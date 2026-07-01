# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Experiential role test — WYCHOWAWCA writes a dated note in fayna.camp.dziennik.note.

Perspective: independent QA engineer. Proves that a user holding ONLY
`group_camp_wychowawca` can:
  1. Create a fayna.camp.dziennik.note on an existing dziennik.
  2. Cannot edit or delete the note on a submitted dziennik (legal freeze).

Key facts pinned from the code:
  * ACL (ir.model.access.csv:118-119): ONLY base.group_system has perm_create=1
    on fayna.camp.dziennik.note. group_user (which wychowawca implies) has
    read-only (perm_read=1, perm_write=0, perm_create=0, perm_unlink=0).
  * Required fields (operations.py:3403-3452): dziennik_id, date, content,
    note_type (default 'info'), author_id (default current user).
  * Notes are immutable once the parent dziennik.state == 'submitted'
    (operations.py:3454-3458 write hook).

PRODUCT FINDING (confirmed against live CI run 28532258120, 2026-07-01):
  Wychowawca cannot create fayna.camp.dziennik.note — only Administration/Settings can.
  This is a missing ACL: group_camp_wychowawca needs perm_create=1 on
  model_fayna_camp_dziennik_note in security/ir.model.access.csv.
  test_wychowawca_creates_note is LEFT FAILING intentionally to document this gap.
"""

import datetime

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestWychowawcaDayNote(TransactionCase):
    """Wychowawca can write a dated note on an active dziennik.

    PRODUCT FINDING: test_wychowawca_creates_note currently FAILS because the
    ACL for fayna.camp.dziennik.note only grants perm_create=1 to base.group_system
    (ir.model.access.csv:118). group_camp_wychowawca is missing create rights.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Wychowawca user — only this role group
        cls.wychowawca_user = cls.env["res.users"].create(
            {
                "name": "QA Wychowawca",
                "login": "qa_wychowawca_note@campscout.test",
                "password": "QaWych-1234!",
                "groups_id": [(6, 0, [cls.env.ref("fayna_camp_portal.group_camp_wychowawca").id])],
            }
        )

        # Event and staff setup
        cls.event = cls.env["event.event"].create(
            {
                "name": "QA Shift — Wychowawca Note Test",
                "date_begin": datetime.datetime(2026, 7, 10, 9, 0),
                "date_end": datetime.datetime(2026, 7, 20, 18, 0),
                "date_tz": "Europe/Warsaw",
            }
        )
        cls.kierownik_staff = cls.env["camp.staff"].create(
            {
                "event_id": cls.event.id,
                "name": "QA Kierownik for Wychowawca Test",
                "role": "kierownik",
                "date_from": datetime.date(2026, 7, 10),
                "date_to": datetime.date(2026, 7, 20),
            }
        )
        cls.wychowawca_staff = cls.env["camp.staff"].create(
            {
                "event_id": cls.event.id,
                "name": "QA Wychowawca",
                "role": "wychowawca",
                "user_id": cls.wychowawca_user.id,
                "date_from": datetime.date(2026, 7, 10),
                "date_to": datetime.date(2026, 7, 20),
            }
        )

        # Active dziennik — created as admin (superuser) because kierownik also
        # lacks create rights (see test_role_kierownik_dziennik.py for that finding).
        cls.dziennik = cls.env["fayna.camp.dziennik"].create(
            {
                "event_id": cls.event.id,
                "group_name": "Grupa Wychowawca",
                "date_start": datetime.date(2026, 7, 10),
                "state": "active",
                "kierownik_id": cls.kierownik_staff.id,
                "wychowawca_ids": [(4, cls.wychowawca_staff.id)],
            }
        )

    # ── 1. Wychowawca can create a dated note ────────────────────────────────

    def test_wychowawca_creates_note(self):
        """group_camp_wychowawca can create a fayna.camp.dziennik.note — no AccessError.

        PRODUCT FINDING: This test FAILS with AccessError because
        ir.model.access.csv only grants perm_create to base.group_system on
        fayna.camp.dziennik.note (line 118). group_camp_wychowawca has read-only.
        FIX REQUIRED: add a row granting perm_create=1 (and perm_write=1) to
        group_camp_wychowawca in security/ir.model.access.csv.
        """
        try:
            note = (
                self.env["fayna.camp.dziennik.note"]
                .with_user(self.wychowawca_user)
                .create(
                    {
                        "dziennik_id": self.dziennik.id,
                        "date": datetime.date(2026, 7, 12),
                        "content": "Wieczorna gra terenowa — świetna frekwencja, brak incydentów.",
                        "note_type": "info",
                    }
                )
            )
            self.assertTrue(note.id, "Wychowawca must be able to create a dziennik note")
            self.assertEqual(
                note.date,
                datetime.date(2026, 7, 12),
                "Date field must be preserved exactly",
            )
            self.assertEqual(
                note.author_id.id,
                self.wychowawca_user.id,
                "author_id must auto-populate to the wychowawca's user",
            )
        except AccessError as exc:
            self.fail(
                "PRODUCT FINDING — Wychowawca got AccessError creating fayna.camp.dziennik.note: "
                f"{exc}\n\n"
                "FIX: add to security/ir.model.access.csv a row granting perm_create=1 and "
                "perm_write=1 to group_camp_wychowawca on model_fayna_camp_dziennik_note."
            )

    # ── 2. Note on a submitted dziennik is frozen ────────────────────────────

    def test_note_frozen_after_dziennik_submit(self):
        """Editing a note on a submitted dziennik raises UserError (legal freeze)."""
        note = self.env["fayna.camp.dziennik.note"].create(
            {
                "dziennik_id": self.dziennik.id,
                "date": datetime.date(2026, 7, 13),
                "content": "Note przed zamknięciem.",
                "note_type": "recommendation",
            }
        )

        # Force-submit the dziennik via admin (bypass the 'must have activities' gate)
        self.dziennik.sudo().write({"state": "submitted"})

        # Wychowawca tries to edit the note on the now-submitted dziennik
        with self.assertRaises(
            UserError,
            msg=(
                "PRODUCT FINDING: editing notes on a submitted dziennik must raise UserError "
                "(operations.py:3454-3458). If this passes, the legal freeze is broken."
            ),
        ):
            note.with_user(self.wychowawca_user).write({"content": "Próba edycji po zamknięciu."})
