# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — F-generator product card tests (TZ §8, _generate_product_card)
#
# Covers:
#   1. action_approve on event with camp_program_id + structured program →
#      product.camp_daily_routine is populated (non-empty).
#   2. camp_highlights contains <ul> / <li>.
#   3. product.list_price = budget.price_per_child.
#   4. Event WITHOUT structured_program_ids → action_approve does NOT raise
#      (graceful skip — generator wraps in try/except).
#   5. Idempotent: already-set fields are NOT overwritten on second approve.
#
# Fixtures follow the same pattern as test_phase_c_wychowawca.py:
#   camp.program.structured → camp.program.day → camp.program.activity.line
#
# NOTE: action_approve writes website_published=True.  The test verifies that
# the card was populated AND that the approval state transitions correctly.
# Organizator user is required for action_approve (same as test_native_approval).

from datetime import date

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal", "card_generator")
class TestCardGenerator(TransactionCase):
    """Tests for _generate_product_card (TZ §8 F-generator)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # --- Organizator user (required for action_approve) ----------------
        cls.group_organizator = cls.env.ref("fayna_camp_portal.group_camp_organizator")
        cls.organizator_user = cls.env["res.users"].create(
            {
                "name": "Test Organizator Card",
                "login": "test_organizator_card@campscout.test",
                "groups_id": [(6, 0, [cls.group_organizator.id])],
            }
        )

        # --- Camp activity records (pre-existing, matched by name) ---------
        cls.activity_kajak = cls.env["camp.activity"].sudo().create({"name": "Kajakarstwo"})
        cls.activity_archery = cls.env["camp.activity"].sudo().create({"name": "Łucznictwo"})

    # ------------------------------------------------------------------
    # Helper: make product.template (camp program card)
    # ------------------------------------------------------------------

    def _make_camp_product(self, name="Test Camp Program 2026"):
        """Create a bare camp program product (no card fields set yet)."""
        return (
            self.env["product.template"]
            .sudo()
            .create(
                {
                    "name": name,
                    "is_camp_program": True,
                    "list_price": 0.0,
                    "type": "service",
                }
            )
        )

    # ------------------------------------------------------------------
    # Helper: make event + full fixture (structured program + budget)
    # ------------------------------------------------------------------

    def _make_event_with_fixtures(self, product):
        """Build a complete event fixture: event → structured program →
        day → activity lines → budget with price_per_child=850.

        Returns the event record (camp_approval_state='pending_approval').
        """
        event = (
            self.env["event.event"]
            .sudo()
            .create(
                {
                    "name": "F-Generator Test Turnus 2026",
                    "date_begin": "2026-07-10 08:00:00",
                    "date_end": "2026-07-17 18:00:00",
                    "seats_limited": True,
                    "seats_max": 30,
                    "website_published": False,
                    "camp_approval_state": "pending_approval",
                    "camp_program_id": product.id,
                }
            )
        )

        # Structured program (Plan A, published — preferred by _get_plan_a_program)
        structured = (
            self.env["camp.program.structured"]
            .sudo()
            .create(
                {
                    "event_id": event.id,
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
        )

        # One program day with activity lines
        day = (
            self.env["camp.program.day"]
            .sudo()
            .create(
                {
                    "program_id": structured.id,
                    "date": date(2026, 7, 10),
                }
            )
        )
        # Meal line (category='meal') — should appear in daily_routine
        self.env["camp.program.activity.line"].sudo().create(
            {
                "day_id": day.id,
                "time_from": 8.0,
                "time_to": 8.75,
                "title": "Śniadanie",
                "category": "meal",
                "owner_role": "kierownik",
                "is_locked": True,
            }
        )
        # Activity line (category='activity') — used for highlights + activity_ids
        self.env["camp.program.activity.line"].sudo().create(
            {
                "day_id": day.id,
                "time_from": 10.0,
                "time_to": 11.0,
                "title": "Kajakarstwo",
                "category": "activity",
                "owner_role": "kierownik",
                "is_locked": False,
            }
        )
        self.env["camp.program.activity.line"].sudo().create(
            {
                "day_id": day.id,
                "time_from": 15.0,
                "time_to": 16.0,
                "title": "Łucznictwo",
                "category": "activity",
                "owner_role": "wychowawca",
                "is_locked": False,
            }
        )

        # Budget with price_per_child > 0 (required for list_price population)
        event.sudo().action_open_budget()
        budget = event.camp_budget_id
        if budget:
            budget.sudo().write({"price_per_child": 850.0})

        return event

    # ------------------------------------------------------------------
    # Test 1: action_approve populates camp_daily_routine (non-empty)
    # ------------------------------------------------------------------

    def test_approve_populates_camp_daily_routine(self):
        """After action_approve: product.camp_daily_routine must be non-empty HTML."""
        product = self._make_camp_product()
        event = self._make_event_with_fixtures(product)

        event.with_user(self.organizator_user).action_approve()

        self.assertEqual(event.camp_approval_state, "approved")
        self.assertTrue(
            product.camp_daily_routine,
            "camp_daily_routine must be populated after action_approve.",
        )
        # Must contain HTML list markup (ramowy plan or per-day detail)
        self.assertIn(
            "<li>",
            product.camp_daily_routine,
            "camp_daily_routine must contain <li> elements.",
        )

    # ------------------------------------------------------------------
    # Test 2: camp_highlights contains <ul>/<li>
    # ------------------------------------------------------------------

    def test_approve_populates_camp_highlights(self):
        """After action_approve: product.camp_highlights must be a <ul> list."""
        product = self._make_camp_product(name="Test Camp Highlights 2026")
        event = self._make_event_with_fixtures(product)

        event.with_user(self.organizator_user).action_approve()

        highlights = product.camp_highlights
        self.assertTrue(
            highlights,
            "camp_highlights must be non-empty after action_approve.",
        )
        self.assertIn("<ul>", highlights, "camp_highlights must open with <ul>.")
        self.assertIn("<li>", highlights, "camp_highlights must contain <li> items.")

    # ------------------------------------------------------------------
    # Test 3: list_price = budget.price_per_child
    # ------------------------------------------------------------------

    def test_approve_sets_list_price_from_budget(self):
        """After action_approve: product.list_price must equal budget.price_per_child (850)."""
        product = self._make_camp_product(name="Test Camp Price 2026")
        event = self._make_event_with_fixtures(product)

        event.with_user(self.organizator_user).action_approve()

        self.assertAlmostEqual(
            product.list_price,
            850.0,
            places=2,
            msg=f"Expected list_price=850.0, got {product.list_price}",
        )

    # ------------------------------------------------------------------
    # Test 4: event WITHOUT structured_program_ids — approve must NOT raise
    # ------------------------------------------------------------------

    def test_approve_without_structured_program_is_graceful(self):
        """action_approve on event with camp_program_id but NO structured program
        must not raise — generator wraps errors in try/except (TZ §0b reliability).
        """
        product = self._make_camp_product(name="No-Program Camp 2026")
        event = (
            self.env["event.event"]
            .sudo()
            .create(
                {
                    "name": "No Structured Program Event 2026",
                    "date_begin": "2026-08-01 08:00:00",
                    "date_end": "2026-08-08 18:00:00",
                    "seats_limited": True,
                    "seats_max": 20,
                    "website_published": False,
                    "camp_approval_state": "pending_approval",
                    "camp_program_id": product.id,
                    # intentionally no structured_program_ids
                }
            )
        )

        # Must not raise any exception
        try:
            event.with_user(self.organizator_user).action_approve()
        except Exception as exc:
            self.fail(f"action_approve raised unexpectedly when no structured program: {exc}")

        self.assertEqual(
            event.camp_approval_state,
            "approved",
            "camp_approval_state must be 'approved' even when no structured program.",
        )

    # ------------------------------------------------------------------
    # Test 5: idempotent — already-set card fields are NOT overwritten
    # ------------------------------------------------------------------

    def test_card_generator_is_idempotent(self):
        """_generate_product_card must not overwrite fields that are already set.

        Scenario:
          1. Set camp_daily_routine and camp_highlights manually on the product.
          2. Approve the event (triggers _generate_product_card).
          3. Verify manual values are preserved (not replaced by auto-generated ones).
        """
        product = self._make_camp_product(name="Idempotent Camp 2026")

        # Pre-populate the card fields manually
        manual_routine = "<p>Manually set daily routine — do not overwrite.</p>"
        manual_highlights = "<ul><li>Manually set highlight</li></ul>"
        manual_price = 999.0

        product.sudo().write(
            {
                "camp_daily_routine": manual_routine,
                "camp_highlights": manual_highlights,
                "list_price": manual_price,
            }
        )

        event = self._make_event_with_fixtures(product)

        # Re-link product to this event (already set, but ensure)
        event.sudo().write({"camp_program_id": product.id})

        event.with_user(self.organizator_user).action_approve()

        # All three fields must retain the manually set values
        self.assertEqual(
            product.camp_daily_routine,
            manual_routine,
            "camp_daily_routine must NOT be overwritten if already set.",
        )
        self.assertEqual(
            product.camp_highlights,
            manual_highlights,
            "camp_highlights must NOT be overwritten if already set.",
        )
        self.assertAlmostEqual(
            product.list_price,
            manual_price,
            places=2,
            msg=f"list_price must NOT be overwritten if already set (expected {manual_price}).",
        )

    # ------------------------------------------------------------------
    # Test 6: event with NO camp_program_id — approve does NOT raise
    # ------------------------------------------------------------------

    def test_approve_without_camp_program_id_is_graceful(self):
        """action_approve when event.camp_program_id is not set must not raise.

        _generate_product_card returns early with an info log in this case.
        """
        event = (
            self.env["event.event"]
            .sudo()
            .create(
                {
                    "name": "No Program ID Event 2026",
                    "date_begin": "2026-09-01 08:00:00",
                    "date_end": "2026-09-08 18:00:00",
                    "seats_limited": True,
                    "seats_max": 15,
                    "website_published": False,
                    "camp_approval_state": "pending_approval",
                    # camp_program_id intentionally omitted
                }
            )
        )

        try:
            event.with_user(self.organizator_user).action_approve()
        except Exception as exc:
            self.fail(f"action_approve raised unexpectedly when camp_program_id is unset: {exc}")

        self.assertEqual(
            event.camp_approval_state,
            "approved",
            "Approval state must be 'approved' even when camp_program_id is missing.",
        )
