# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Experiential role test — WYCHOWAWCA writes a dated note about a child.

Perspective: independent QA.  This test drives the system AS a user who holds
ONLY `group_camp_wychowawca` and asserts that the role can perform its
headline job: write a dated note (fayna.camp.dziennik.note) in a dziennik
they are assigned to.

Key facts pinned from code (models/operations.py):
  * fayna.camp.dziennik.note required fields (line 3418–3451):
      - dziennik_id  (Many2one fayna.camp.dziennik, required)
      - date         (Date, required, default today)
      - content      (Text, required)
      - note_type    (Selection, required, default 'info')
      - author_id    (Many2one res.users, required, readonly, default env.user)

  * The note model ACL (ir.model.access.csv line 118–119):
      fayna.camp.dziennik.note access is via base.group_user (read only, no
      create/write from role-specific lines). This means wychowawca can READ
      but CREATE goes through base.group_system.
    → FINDING: if this test fails with AccessError on create, it reveals a
      real ACL gap — wychowawca cannot write notes without group_system/sudo.

  * (історичний контраст із camp.journal вилучено — журнал злито в daily.report, reuse S1 пара 2.)

The test seeds the dziennik as admin (owner-env), assigns the wychowawca to
it, then attempts create as the wychowawca user.  A failure = FINDING.
"""

import datetime

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestWychowawcaNote(TransactionCase):
    """Wychowawca role writes a dated note (fayna.camp.dziennik.note) about a child."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.event = cls.env["event.event"].create(
            {
                "name": "QA Obóz Wychowawca Test 2026",
                "date_begin": datetime.datetime(2026, 7, 5, 9, 0, 0),
                "date_end": datetime.datetime(2026, 7, 15, 17, 0, 0),
            }
        )

        cls.wychowawca_user = cls.env["res.users"].create(
            {
                "name": "QA Wychowawca",
                "login": "qa_wychowawca@campscout.test",
                "password": "QaWych-1234!",
                "groups_id": [(6, 0, [cls.env.ref("fayna_camp_portal.group_camp_wychowawca").id])],
            }
        )

        # Seed a kierownik staff (required for dziennik.action_activate if called)
        cls.kierownik_staff = cls.env["camp.staff"].create(
            {
                "name": "QA Kierownik for Wychowawca Test",
                "role": "kierownik",
                "event_id": cls.event.id,
                "date_from": datetime.date(2026, 7, 5),
                "date_to": datetime.date(2026, 7, 15),
            }
        )

        # Seed a wychowawca staff linked to the wychowawca user
        cls.wychowawca_staff = cls.env["camp.staff"].create(
            {
                "name": "QA Wychowawca Staff",
                "role": "wychowawca",
                "event_id": cls.event.id,
                "user_id": cls.wychowawca_user.id,
                "date_from": datetime.date(2026, 7, 5),
                "date_to": datetime.date(2026, 7, 15),
            }
        )

        # Seed dziennik and assign both kierownik and wychowawca
        cls.dziennik = cls.env["fayna.camp.dziennik"].create(
            {
                "event_id": cls.event.id,
                "group_name": "Wychowawca QA Group",
                "date_start": datetime.date(2026, 7, 5),
                "kierownik_id": cls.kierownik_staff.id,
                "wychowawca_ids": [(4, cls.wychowawca_staff.id)],
            }
        )

    # ── 1. Wychowawca writes a dated note (the headline task) ────────────────

    def test_wychowawca_writes_note(self):
        """Wychowawca can create a fayna.camp.dziennik.note without AccessError.

        FINDING if fails: fayna.camp.dziennik.note has no wychowawca-specific
        CREATE ACL row — only base.group_system has write access (ir.model.access.csv
        lines 118-119). This is an ACL gap: wychowawca's core job is writing notes
        but the ORM blocks it.
        """
        try:
            note = (
                self.env["fayna.camp.dziennik.note"]
                .with_user(self.wychowawca_user)
                .create(
                    {
                        "dziennik_id": self.dziennik.id,
                        "date": datetime.date(2026, 7, 8),
                        "content": "QA: Anna K. — zachowała się wzorowo, brała udział w zajęciach.",
                        "note_type": "info",
                    }
                )
            )
        except AccessError as exc:
            # FINDING — document the gap; do not mask it
            self.fail(
                f"FINDING — Wychowawca got AccessError creating fayna.camp.dziennik.note: {exc}\n"
                "ACL gap: fayna.camp.dziennik.note has no wychowawca-specific CREATE row "
                "(ir.model.access.csv lines 118-119 grant only base.group_system write). "
                "Wychowawca cannot write dziennik notes without sudo — core role job is broken."
            )

        self.assertTrue(
            note.exists(),
            "The dated note created by wychowawca must persist in DB.",
        )
        self.assertEqual(
            note.dziennik_id.id,
            self.dziennik.id,
            "The note must be linked to the correct dziennik.",
        )
        self.assertEqual(
            note.date,
            datetime.date(2026, 7, 8),
            "The note date must match exactly what the wychowawca entered.",
        )
        self.assertEqual(
            note.author_id.id,
            self.wychowawca_user.id,
            "author_id must be auto-set to the wychowawca user (default=env.user).",
        )

    # ── 2. Wychowawca can read the dziennik (own assigned group) ─────────────

    def test_wychowawca_reads_own_dziennik(self):
        """Wychowawca reads a fayna.camp.dziennik they are assigned to."""
        try:
            dziennik_as_wy = (
                self.env["fayna.camp.dziennik"]
                .with_user(self.wychowawca_user)
                .browse(self.dziennik.id)
            )
            group_name = dziennik_as_wy.group_name
        except AccessError as exc:
            self.fail(f"Wychowawca got AccessError reading fayna.camp.dziennik.group_name: {exc}")
        self.assertEqual(
            group_name,
            "Wychowawca QA Group",
            "Wychowawca must be able to read the dziennik they are assigned to.",
        )

    # ── 3. Wychowawca can read camp.participant (own group) ──────────────────

    def test_wychowawca_can_search_participants(self):
        """Wychowawca can search camp.participant without AccessError.

        ACL access_camp_participant_wychowawca (line 136): read=1, write=1.
        """
        try:
            # Use a simple searchable domain — registration_ids.event_id traverses
            # a non-stored compute field which Odoo 17 cannot search (only stored
            # computed fields are searchable). Use active=True instead.
            _ = (
                self.env["camp.participant"]
                .with_user(self.wychowawca_user)
                .search([("active", "=", True)], limit=10)
            )
        except AccessError as exc:
            self.fail(
                f"Wychowawca got AccessError searching camp.participant: {exc}\n"
                "ACL access_camp_participant_wychowawca should grant read=1."
            )
        # We don't assert count because no participants are seeded here;
        # the goal is to verify NO AccessError is raised.
