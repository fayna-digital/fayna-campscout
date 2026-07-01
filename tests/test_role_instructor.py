# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Experiential role test — INSTRUCTOR manages camp.activity records.

Perspective: independent QA engineer. Proves that a user holding ONLY
`group_camp_instructor` can:
  1. Read existing camp.activity records.
  2. Write (update) a camp.activity record.
  3. Cannot create new camp.activity records (ACL: perm_create=0).

Key facts pinned from the code under test:
  * ACL (ir.model.access.csv:144):
    access_camp_activity_instructor → group_camp_instructor
    perm_read=1, perm_write=1, perm_create=0, perm_unlink=0
  * camp.activity required fields (models/camp.py:57-60): name only.
  * Instructor record rule (security/record_rules.xml:85-93): instructor
    sees only camp.participant where registration_ids.event_id.staff_ids.user_id == user.id
    — does NOT restrict camp.activity itself.
"""

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestInstructor(TransactionCase):
    """Instructor role can read and write camp.activity — but cannot create."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Instructor user — only this role group
        cls.instructor_user = cls.env["res.users"].create(
            {
                "name": "QA Instructor",
                "login": "qa_instructor@campscout.test",
                "password": "QaInstr-5678!",
                "groups_id": [(6, 0, [cls.env.ref("fayna_camp_portal.group_camp_instructor").id])],
            }
        )

        # Seed a camp.activity as admin (instructor cannot create one)
        cls.activity = cls.env["camp.activity"].create(
            {
                "name": "QA Archery Session",
            }
        )

    # ── 1. Instructor can read camp.activity ────────────────────────────────

    def test_instructor_reads_camp_activity(self):
        """group_camp_instructor can search and read camp.activity — no AccessError."""
        activities = (
            self.env["camp.activity"]
            .with_user(self.instructor_user)
            .search([("name", "=", "QA Archery Session")])
        )
        self.assertTrue(activities, "Instructor must be able to search camp.activity records")
        self.assertEqual(
            activities[0].name,
            "QA Archery Session",
            "Instructor must read the activity name field",
        )

    # ── 2. Instructor can write (update) camp.activity ──────────────────────

    def test_instructor_writes_camp_activity(self):
        """group_camp_instructor can update (write) a camp.activity record."""
        self.activity.with_user(self.instructor_user).write(
            {"name": "QA Archery Session — Updated by Instructor"}
        )
        # Verify the write took effect (read as admin to avoid rule filtering)
        self.assertEqual(
            self.activity.name,
            "QA Archery Session — Updated by Instructor",
            "Instructor write on camp.activity must persist",
        )

    # ── 3. Instructor CANNOT create camp.activity (perm_create=0) ───────────

    def test_instructor_cannot_create_camp_activity(self):
        """PRODUCT FINDING candidate: perm_create=0 for instructor on camp.activity.

        ACL row 144: access_camp_activity_instructor has perm_create=0.
        If create succeeds, either the ACL is wrong or group_user baseline
        overrides it — that would be a security gap.
        """
        with self.assertRaises(
            AccessError,
            msg=(
                "PRODUCT FINDING: instructor must not be able to create camp.activity "
                "(ir.model.access.csv line 144: perm_create=0). "
                "If this test fails, the ACL allows creation — check for group_user override."
            ),
        ):
            self.env["camp.activity"].with_user(self.instructor_user).create(
                {"name": "Unauthorized new activity by instructor"}
            )
