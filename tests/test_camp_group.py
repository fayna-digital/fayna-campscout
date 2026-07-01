# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — tests for camp.group (grupa wychowawcza, §2 art. 92c)
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestCampGroup(TransactionCase):
    """§2 art. 92c: group size limits, age mix, auto-split, event scoping."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent = cls.env["res.partner"].create(
            {"name": "Group Test Parent", "email": "group-test@campscout.test"}
        )
        cls.event = cls.env["event.event"].create(
            {
                "name": "Group Test Camp 2026",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-14 18:00:00",
            }
        )
        cls.other_event = cls.env["event.event"].create(
            {
                "name": "Other Camp 2026",
                "date_begin": "2026-08-01 08:00:00",
                "date_end": "2026-08-14 18:00:00",
            }
        )
        cls.Group = cls.env["camp.group"]

    @classmethod
    def _make_child(cls, idx, birth_date, event=None, **extra):
        """Create a participant + open registration on *event* (default shift)."""
        event = event or cls.event
        child = cls.env["camp.participant"].create(
            {
                "first_name": f"Child{idx}",
                "last_name": "GroupTest",
                "birth_date": birth_date,
                **extra,
            }
        )
        cls.env["event.registration"].create(
            {
                "event_id": event.id,
                "partner_id": cls.parent.id,
                "participant_id": child.id,
                "state": "open",
            }
        )
        return child

    @classmethod
    def _make_children(cls, count, birth_date, offset=0, **extra):
        children = cls.env["camp.participant"]
        for i in range(count):
            children |= cls._make_child(offset + i, birth_date, **extra)
        return children

    # ------------------------------------------------------------------
    # Creation + capacity 20
    # ------------------------------------------------------------------

    def test_create_group(self):
        """A group is created with the default legal limit of 20 (no under-10)."""
        children = self._make_children(3, "2012-03-15")
        group = self.Group.create(
            {
                "name": "Grupa A",
                "event_id": self.event.id,
                "participant_ids": [(6, 0, children.ids)],
            }
        )
        self.assertEqual(group.participant_count, 3)
        self.assertFalse(group.has_under_10)
        self.assertEqual(group.capacity_limit, 20)

    def test_capacity_limit_20(self):
        """20 older children fit; the 21st raises ValidationError (art. 92c)."""
        children = self._make_children(20, "2012-01-01")
        group = self.Group.create(
            {
                "name": "Grupa B",
                "event_id": self.event.id,
                "participant_ids": [(6, 0, children.ids)],
            }
        )
        self.assertEqual(group.participant_count, 20)
        extra = self._make_child(99, "2012-01-01")
        with self.assertRaises(ValidationError):
            extra.group_id = group.id

    # ------------------------------------------------------------------
    # Mixed group with a child under 10 → limit 15
    # ------------------------------------------------------------------

    def test_mixed_group_limit_15(self):
        """One child under 10 lowers the limit to 15; the 16th child raises."""
        # 14 older + 1 young (age 7 on 2026-07-01) = 15 — exactly at the limit.
        older = self._make_children(14, "2012-01-01")
        young = self._make_child(50, "2018-09-01")
        group = self.Group.create(
            {
                "name": "Grupa C",
                "event_id": self.event.id,
                "participant_ids": [(6, 0, (older | young).ids)],
            }
        )
        self.assertTrue(group.has_under_10)
        self.assertEqual(group.capacity_limit, 15)
        self.assertEqual(group.participant_count, 15)
        sixteenth = self._make_child(51, "2012-01-01")
        with self.assertRaises(ValidationError):
            sixteenth.group_id = group.id

    # ------------------------------------------------------------------
    # Disability limit (sprint TZ §2: max 2 per group)
    # ------------------------------------------------------------------

    def test_disabled_limit_2(self):
        """At most 2 participants with special needs per group."""
        two = self._make_children(2, "2012-01-01", has_disability=True)
        third = self._make_child(60, "2012-01-01", has_disability=True)
        group = self.Group.create(
            {
                "name": "Grupa D",
                "event_id": self.event.id,
                "participant_ids": [(6, 0, two.ids)],
            }
        )
        self.assertEqual(group.disabled_count, 2)
        with self.assertRaises(ValidationError):
            third.group_id = group.id

    # ------------------------------------------------------------------
    # Auto-split
    # ------------------------------------------------------------------

    def test_auto_split_17_young(self):
        """17 under-10 children -> 2 groups of 9 + 8.

        Design choice (documented in camp.group.action_auto_split): children
        are spread EVENLY across the minimal number of groups instead of
        greedy 15 + 2 — balanced groups are pedagogically sound and leave
        headroom for manual moves by the kierownik.
        """
        self._make_children(17, "2018-09-01")
        groups = self.Group.action_auto_split(self.event)
        self.assertEqual(len(groups), 2)
        sizes = sorted(g.participant_count for g in groups)
        self.assertEqual(sizes, [8, 9])
        for group in groups:
            self.assertTrue(group.has_under_10)
            self.assertEqual(group.capacity_limit, 15)
            self.assertEqual(group.event_id, self.event)

    def test_auto_split_keeps_existing_assignments(self):
        """Children already in a group are not touched by auto-split."""
        assigned = self._make_child(70, "2012-01-01")
        existing = self.Group.create(
            {
                "name": "Grupa E",
                "event_id": self.event.id,
                "participant_ids": [(6, 0, assigned.ids)],
            }
        )
        loose = self._make_children(3, "2012-01-01", offset=71)
        # The registration hook (D2) may auto-assign newly registered children
        # into the existing group; explicitly leave them ungrouped so this test
        # exercises auto-split on loose children only.
        loose.write({"group_id": False})
        created = self.Group.action_auto_split(self.event)
        self.assertEqual(assigned.group_id, existing)
        self.assertEqual(len(created), 1)
        self.assertEqual(created.participant_ids, loose)

    def test_auto_split_separates_ages(self):
        """Under-10 and 10+ children land in separate groups."""
        self._make_children(5, "2018-09-01", offset=80)  # age 7
        self._make_children(5, "2012-01-01", offset=90)  # age 14
        groups = self.Group.action_auto_split(self.event)
        self.assertEqual(len(groups), 2)
        young_groups = groups.filtered("has_under_10")
        old_groups = groups - young_groups
        self.assertEqual(len(young_groups), 1)
        self.assertEqual(young_groups.participant_count, 5)
        self.assertEqual(old_groups.participant_count, 5)
        self.assertEqual(old_groups.capacity_limit, 20)

    # ------------------------------------------------------------------
    # Event scoping
    # ------------------------------------------------------------------

    def test_participant_other_event_rejected(self):
        """A child registered to another shift cannot join this group."""
        stranger = self._make_child(95, "2012-01-01", event=self.other_event)
        group = self.Group.create({"name": "Grupa F", "event_id": self.event.id})
        with self.assertRaises(ValidationError):
            stranger.group_id = group.id
