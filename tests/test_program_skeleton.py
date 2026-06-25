# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — tests for ADR Фаза A: skeleton generator + constraints
# Covers ADR §1 (поля + constrains), §2 (генератор), §3 (ACL — model-level),
# §4 (wizard rain plan).
from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestProgramSkeleton(TransactionCase):
    """ADR Фаза A: генератор скелету, ≥9h сон, free-hours, rain plan."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # 7-day camp: 2026-07-01 → 2026-07-07
        cls.event = cls.env["event.event"].create(
            {
                "name": "Skeleton Test Camp 2026",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-07 18:00:00",
                "seats_max": 30,
            }
        )

    def _make_structured(self, **kw):
        """Create a minimal camp.program.structured with frame-day defaults."""
        vals = {
            "event_id": self.event.id,
            "is_rain_plan": False,
            "wake_time": 7.0,
            "breakfast": 8.0,
            "lunch": 13.0,
            "afternoon_rest": 14.0,
            "snack": 16.0,
            "dinner": 18.0,
            "lights_out": 22.0,
            "meal_duration": 0.75,
            "rest_duration": 1.0,
        }
        vals.update(kw)
        return self.env["camp.program.structured"].create(vals)

    # ── §1 constraint: ≥9h sleep ─────────────────────────────────────────

    def test_sleep_ok_22_to_07(self):
        """lights_out=22, wake=7 → sleep=9h → valid."""
        structured = self._make_structured(lights_out=22.0, wake_time=7.0)
        # No error raised — record created
        self.assertTrue(structured.id)

    def test_sleep_fail_23_to_07(self):
        """lights_out=23, wake=7 → sleep=8h → ValidationError."""
        with self.assertRaises(ValidationError):
            self._make_structured(lights_out=23.0, wake_time=7.0)

    def test_sleep_fail_lights_out_lte_wake(self):
        """lights_out <= wake_time → ValidationError."""
        with self.assertRaises(ValidationError):
            self._make_structured(lights_out=6.0, wake_time=7.0)

    def test_sleep_fail_22_5_to_07(self):
        """lights_out=22.5, wake=7 → sleep=8.5h < 9 → ValidationError."""
        with self.assertRaises(ValidationError):
            self._make_structured(lights_out=22.5, wake_time=7.0)

    # ── §2 генератор: 7 днів → 7 day records ────────────────────────────

    def test_generate_skeleton_7_days(self):
        """7-day event → _generate_skeleton creates 7 camp.program.day records."""
        structured = self._make_structured()
        self.env["camp.program.structured"]._generate_skeleton(self.event, structured)
        self.assertEqual(len(structured.day_ids), 7, "Expected 7 program days for a 7-day camp")

    def test_generate_skeleton_fixed_lines(self):
        """Each day must contain Śniadanie, Obiad, Cisza poobiednia, Kolacja, Cisza nocna."""
        structured = self._make_structured()
        self.env["camp.program.structured"]._generate_skeleton(self.event, structured)

        expected_titles = {"Śniadanie", "Obiad", "Cisza poobiednia", "Podwieczorek",
                           "Kolacja", "Cisza nocna", "Sen (noc)"}
        for day in structured.day_ids:
            skeleton_titles = set(
                day.activity_line_ids.filtered("is_skeleton").mapped("title")
            )
            for title in expected_titles:
                self.assertIn(
                    title, skeleton_titles,
                    f"Day {day.date}: missing skeleton line '{title}'"
                )

    def test_generate_skeleton_meal_categories(self):
        """Śniadanie, Obiad, Kolacja, Podwieczorek → category='meal'."""
        structured = self._make_structured()
        self.env["camp.program.structured"]._generate_skeleton(self.event, structured)
        day = structured.day_ids[0]
        meal_titles = {"Śniadanie", "Obiad", "Kolacja", "Podwieczorek"}
        for line in day.activity_line_ids.filtered("is_skeleton"):
            if line.title in meal_titles:
                self.assertEqual(line.category, "meal",
                                 f"'{line.title}' should have category='meal'")

    # ── §2 free-hours ───────────────────────────────────────────────────

    def test_free_hours_gaps_filled(self):
        """After skeleton generation each day must have at least one 'free' line."""
        structured = self._make_structured()
        self.env["camp.program.structured"]._generate_skeleton(self.event, structured)
        for day in structured.day_ids:
            free_lines = day.activity_line_ids.filtered(lambda l: l.category == "free")
            self.assertTrue(
                len(free_lines) > 0,
                f"Day {day.date}: no free-time lines generated"
            )

    def test_free_hours_no_overlap_with_skeleton(self):
        """Free lines must not overlap with skeleton fixed lines within [wake, lights_out]."""
        structured = self._make_structured()
        self.env["camp.program.structured"]._generate_skeleton(self.event, structured)
        day = structured.day_ids[0]
        wake = structured.wake_time
        lights = structured.lights_out

        skeleton_slots = [
            (l.time_from, l.time_to)
            for l in day.activity_line_ids.filtered("is_skeleton")
            if l.category != "free" and l.time_to <= lights and l.time_from >= wake
        ]
        free_slots = [
            (l.time_from, l.time_to)
            for l in day.activity_line_ids.filtered(lambda l: l.category == "free")
        ]
        for fs, fe in free_slots:
            for ss, se in skeleton_slots:
                overlap = min(fe, se) - max(fs, ss)
                self.assertLessEqual(
                    overlap, 0,
                    f"Free slot [{fs},{fe}] overlaps with skeleton slot [{ss},{se}]"
                )

    # ── §4 rain plan ────────────────────────────────────────────────────

    def test_rain_plan_creates_two_structured(self):
        """_create_structured_skeleton with also_generate_rain_plan=True → 2 records."""
        wizard = self.env["camp.create.wizard"].create(
            {
                "name": "Rain Test Camp",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-07 18:00:00",
                "seats": 20,
                "also_generate_rain_plan": True,
                "fd_wake_time": 7.0,
                "fd_breakfast": 8.0,
                "fd_lunch": 13.0,
                "fd_afternoon_rest": 14.0,
                "fd_snack": 16.0,
                "fd_dinner": 18.0,
                "fd_lights_out": 22.0,
                "fd_meal_duration": 0.75,
                "fd_rest_duration": 1.0,
            }
        )
        wizard._create_structured_skeleton(self.event)
        structured_records = self.env["camp.program.structured"].search(
            [("event_id", "=", self.event.id)]
        )
        self.assertEqual(
            len(structured_records), 2,
            "Expected 2 structured programs: normal + rain plan"
        )
        rain_records = structured_records.filtered("is_rain_plan")
        self.assertEqual(len(rain_records), 1, "Expected exactly one rain plan")

    # ── §3 ACL model-level (quick smoke — no login-as, just field presence) ──

    def test_new_fields_on_activity_line(self):
        """camp.program.activity.line must have category/is_skeleton/is_locked/owner_role."""
        line_model = self.env["camp.program.activity.line"]
        for field_name in ("category", "is_skeleton", "is_locked", "owner_role"):
            self.assertIn(
                field_name, line_model._fields,
                f"Field '{field_name}' missing on camp.program.activity.line"
            )

    def test_new_fields_on_structured(self):
        """camp.program.structured must have all rамовий день Float fields."""
        model = self.env["camp.program.structured"]
        for field_name in (
            "wake_time", "breakfast", "lunch", "afternoon_rest",
            "snack", "dinner", "lights_out", "meal_duration", "rest_duration"
        ):
            self.assertIn(
                field_name, model._fields,
                f"Field '{field_name}' missing on camp.program.structured"
            )

    def test_structured_program_ids_on_event(self):
        """event.event must have structured_program_ids o2m field."""
        self.assertIn(
            "structured_program_ids",
            self.env["event.event"]._fields,
            "Field 'structured_program_ids' missing on event.event"
        )
