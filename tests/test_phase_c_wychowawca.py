# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — tests for ADR Фаза C: wychowawca fills free slots
# Covers:
#   _check_locked_write constrain (locked → ValidationError; free → OK; sudo regres)
#   record rule: write locked → AccessError; write free → OK; create → AccessError
#   100%-гейт action_wychowawca_submit (unfilled → UserError; all filled → wychowawca_done)
#   rain plan — окремий гейт (rain structured not affected by normal submit)
#   fill_progress compute: 0 → 100
from datetime import date, timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestPhaseCWychowawca(TransactionCase):
    """ADR Фаза C — wychowawca fills free slots, respects locks, 100%-gate."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── base event ──────────────────────────────────────────────────
        cls.event = cls.env["event.event"].create(
            {
                "name": "Phase C Test Camp 2026",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-07 18:00:00",
                "seats_max": 30,
            }
        )

        # ── users: wychowawca, kierownik ────────────────────────────────
        group_wychowawca = cls.env.ref("fayna_camp_portal.group_camp_wychowawca")
        group_kierownik = cls.env.ref("fayna_camp_portal.group_camp_kierownik")
        group_employee = cls.env.ref("base.group_user")

        cls.user_wychowawca = cls.env["res.users"].create(
            {
                "name": "Test Wychowawca",
                "login": "test_wychowawca_c@campscout.test",
                "email": "test_wychowawca_c@campscout.test",
                "groups_id": [(6, 0, [group_wychowawca.id, group_employee.id])],
            }
        )
        cls.user_kierownik = cls.env["res.users"].create(
            {
                "name": "Test Kierownik",
                "login": "test_kierownik_c@campscout.test",
                "email": "test_kierownik_c@campscout.test",
                "groups_id": [(6, 0, [group_kierownik.id, group_employee.id])],
            }
        )

        # ── assign ownership so record-rules grant access ───────────────
        # kierownik owns the camp (kierownik rule: event_id.user_id == user)
        cls.event.user_id = cls.user_kierownik.id
        # wychowawca assigned to the camp via staff (wychowawca rules:
        # event_id.staff_ids.user_id == user)
        cls.env["camp.staff"].sudo().create(
            {
                "name": "WC Phase C",
                "event_id": cls.event.id,
                "user_id": cls.user_wychowawca.id,
                "role": "counselor",
                "date_from": "2026-07-01",
                "date_to": "2026-07-07",
            }
        )

        # ── structured program (normal, published) ──────────────────────
        cls.structured = cls.env["camp.program.structured"].create(
            {
                "event_id": cls.event.id,
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
                "state": "published",
            }
        )

        # ── day with two lines: locked (kierownik), free (wychowawca) ───
        cls.day = cls.env["camp.program.day"].create(
            {
                "program_id": cls.structured.id,
                "date": date(2026, 7, 1),
            }
        )
        # locked kierownik line (Obiad)
        cls.line_locked = cls.env["camp.program.activity.line"].sudo().create(
            {
                "day_id": cls.day.id,
                "time_from": 13.0,
                "time_to": 13.75,
                "title": "Obiad",
                "category": "meal",
                "owner_role": "kierownik",
                "is_locked": True,
                "skeleton_label": "Obiad",
            }
        )
        # free wychowawca line
        cls.line_free = cls.env["camp.program.activity.line"].sudo().create(
            {
                "day_id": cls.day.id,
                "time_from": 15.0,
                "time_to": 16.0,
                "title": "Czas wolny — do wypełnienia",
                "category": "free",
                "owner_role": "wychowawca",
                "is_locked": False,
                "skeleton_label": "Czas wolny",
            }
        )

        # ── rain plan structured (published) ────────────────────────────
        cls.structured_rain = cls.env["camp.program.structured"].create(
            {
                "event_id": cls.event.id,
                "is_rain_plan": True,
                "wake_time": 7.0,
                "breakfast": 8.0,
                "lunch": 13.0,
                "afternoon_rest": 14.0,
                "snack": 16.0,
                "dinner": 18.0,
                "lights_out": 22.0,
                "meal_duration": 0.75,
                "rest_duration": 1.0,
                "state": "published",
            }
        )
        cls.day_rain = cls.env["camp.program.day"].create(
            {
                "program_id": cls.structured_rain.id,
                "date": date(2026, 7, 1),
            }
        )
        cls.line_rain_free = cls.env["camp.program.activity.line"].sudo().create(
            {
                "day_id": cls.day_rain.id,
                "time_from": 10.0,
                "time_to": 11.0,
                "title": "Czas wolny — do wypełnienia",
                "category": "free",
                "owner_role": "wychowawca",
                "is_locked": False,
                "skeleton_label": "Czas wolny (deszcz)",
            }
        )

    # ── C1: constrain _check_locked_write ────────────────────────────────

    def test_constrain_locked_blocks_wychowawca(self):
        """Wychowawca writing is_locked=True line → blocked (rule AccessError or constrain ValidationError)."""
        with self.assertRaises((AccessError, ValidationError)):
            self.line_locked.with_user(self.user_wychowawca).write(
                {"title": "Własny obiad"}
            )

    def test_constrain_free_allows_wychowawca(self):
        """Wychowawca writing free (unlocked, owner=wychowawca) line → OK."""
        # Use sudo to bypass record rule for constrain-only test
        self.line_free.with_user(self.user_wychowawca).sudo().write(
            {"title": "Badminton drużynowy", "category": "activity"}
        )
        self.assertEqual(self.line_free.title, "Badminton drużynowy")
        # restore
        self.line_free.sudo().write(
            {"title": "Czas wolny — do wypełnienia", "category": "free"}
        )

    def test_constrain_sudo_regres_generator(self):
        """Generator in sudo creates locked lines without ValidationError (Phase A regress)."""
        new_line = self.env["camp.program.activity.line"].sudo().create(
            {
                "day_id": self.day.id,
                "time_from": 20.0,
                "time_to": 21.0,
                "title": "Zajęcia wieczorne",
                "category": "activity",
                "owner_role": "kierownik",
                "is_locked": True,
                "skeleton_label": "Wieczór",
            }
        )
        self.assertTrue(new_line.id, "Sudo create should not raise for locked lines")
        new_line.sudo().unlink()

    def test_constrain_kierownik_can_edit_locked(self):
        """Kierownik writing locked line → OK (no ValidationError)."""
        self.line_locked.with_user(self.user_kierownik).write(
            {"notes": "Uwaga: bezmięsne"}
        )
        self.assertEqual(self.line_locked.notes, "Uwaga: bezmięsne")
        self.line_locked.sudo().write({"notes": False})

    # ── C2: record rules ─────────────────────────────────────────────────

    def test_rule_wychowawca_cannot_write_locked_via_rule(self):
        """Record rule blocks wychowawca from writing a locked (kierownik-owned) line."""
        with self.assertRaises((AccessError, ValidationError)):
            self.line_locked.with_user(self.user_wychowawca).write(
                {"notes": "Próba edycji"}
            )

    def test_rule_wychowawca_cannot_create_line(self):
        """Record rule blocks wychowawca from creating new activity lines."""
        with self.assertRaises(AccessError):
            self.env["camp.program.activity.line"].with_user(
                self.user_wychowawca
            ).create(
                {
                    "day_id": self.day.id,
                    "time_from": 9.0,
                    "time_to": 10.0,
                    "title": "Nowa aktywność",
                    "category": "activity",
                    "owner_role": "wychowawca",
                    "is_locked": False,
                }
            )

    # ── C1+C3: fill_progress compute ─────────────────────────────────────

    def test_fill_progress_zero_when_unfilled(self):
        """fill_progress = 0 when wychowawca slot is still 'free'."""
        self.structured.invalidate_recordset()
        self.assertAlmostEqual(self.structured.fill_progress, 0.0, delta=1.0)

    def test_fill_progress_hundred_when_filled(self):
        """fill_progress = 100 after free slot is concretely filled."""
        self.line_free.sudo().write(
            {"title": "Badminton drużynowy", "category": "activity"}
        )
        self.structured.invalidate_recordset()
        self.assertAlmostEqual(self.structured.fill_progress, 100.0, delta=0.1)
        # restore
        self.line_free.sudo().write(
            {"title": "Czas wolny — do wypełnienia", "category": "free"}
        )

    # ── C1: action_wychowawca_submit (100%-gate) ──────────────────────────

    def test_submit_gate_blocks_when_unfilled(self):
        """action_wychowawca_submit raises UserError when free slots remain."""
        with self.assertRaises(UserError):
            self.structured.action_wychowawca_submit()

    def test_submit_gate_passes_when_all_filled(self):
        """action_wychowawca_submit sets wychowawca_done=True when all slots filled."""
        self.line_free.sudo().write(
            {"title": "Badminton drużynowy", "category": "activity"}
        )
        self.structured.action_wychowawca_submit()
        self.assertTrue(self.structured.wychowawca_done)
        # restore
        self.structured.sudo().write({"wychowawca_done": False})
        self.line_free.sudo().write(
            {"title": "Czas wolny — do wypełnienia", "category": "free"}
        )

    # ── Rain plan — separate gate ─────────────────────────────────────────

    def test_rain_submit_gate_blocks_when_unfilled(self):
        """Rain plan submit gate works independently from normal plan."""
        with self.assertRaises(UserError):
            self.structured_rain.action_wychowawca_submit()

    def test_rain_submit_passes_when_filled(self):
        """Rain plan: after filling its free slot, submit succeeds independently."""
        self.line_rain_free.sudo().write(
            {"title": "Gry planszowe", "category": "activity"}
        )
        self.structured_rain.action_wychowawca_submit()
        self.assertTrue(self.structured_rain.wychowawca_done)
        # normal plan still unaffected
        self.assertFalse(self.structured.wychowawca_done)
        # restore
        self.structured_rain.sudo().write({"wychowawca_done": False})
        self.line_rain_free.sudo().write(
            {"title": "Czas wolny — do wypełnienia", "category": "free"}
        )

    def test_normal_submit_does_not_affect_rain(self):
        """Filling normal plan does not mark rain plan as done."""
        self.line_free.sudo().write(
            {"title": "Badminton", "category": "activity"}
        )
        self.structured.action_wychowawca_submit()
        self.assertTrue(self.structured.wychowawca_done)
        self.assertFalse(self.structured_rain.wychowawca_done)
        # restore
        self.structured.sudo().write({"wychowawca_done": False})
        self.line_free.sudo().write(
            {"title": "Czas wolny — do wypełnienia", "category": "free"}
        )
