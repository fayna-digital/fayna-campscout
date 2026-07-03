# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Experiential role test — ORGANIZATOR creates a camp end-to-end.

Perspective: an independent QA engineer. This test does NOT trust the fact
that the wizard code exists; it drives the wizard AS a user who only holds the
`group_camp_organizator` role and asserts that the organizator can actually
perform their headline job: spin up a new camp through `camp.create.wizard`
(backend action `action_camp_create_wizard`) and get back a real, usable
event + budget, with the §7 price calculator producing the arithmetic the
owner will quote to parents.

Key facts pinned from the code under test (wizards/camp_create_wizard.py):
  * ACL (security/ir.model.access.csv:163) grants create on camp.create.wizard
    ONLY to group_camp_organizator and group_camp_kierownik.
  * action_create_camp() creates event.event (+ ticket), a camp.budget with
    seeded lines, a teczka, one camp.group and a structured program, and
    RETURNS an ir.actions.act_window pointing at the new event.event.
  * computed_price_per_child = §7 cost-buildup:
        cost_sum = lodging*days + food*days + insurance*days
                   + salaries/children + advertising/children
                   + merch + stationery + operational
        base = cost_sum * (1 + markup/100)
        vat 'zw'  -> price = base  (children's camps are VAT-exempt art.43)
    With a deliberately simple cost set the expected number is exact.

The test runs the wizard with the organizator's own environment
(`with_user`), so every ORM access check / record rule is exercised as that
role — not as admin.
"""

import datetime
import uuid

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestOrganizatorCreatesCamp(TransactionCase):
    """Organizator role can create a camp via the wizard and gets a real event+budget."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.organizator = cls.env["res.users"].create(
            {
                "name": "QA Organizator",
                "login": "qa_organizator@campscout.test",
                "password": "QaOrg-1234!",
                "groups_id": [(6, 0, [cls.env.ref("fayna_camp_portal.group_camp_organizator").id])],
            }
        )

    def _wizard_vals(self, suffix=None):
        """A minimal but complete cost set with an EXACT expected price.

        seats=10, exactly 10 calendar days (08:00→08:00 so math.ceil gives 10),
        lodging 50/day, food 30/day, all salary/other fields zeroed explicitly,
        no markup, VAT-exempt ('zw'):

            days     = math.ceil(10.0) = 10
            cost_sum = (50 + 30) * 10  = 800.00
            base     = 800.00 * 1.0    = 800.00
            price    = 800.00           (zw → no VAT added)

        salary_instructor_per_turnus is explicitly set to 0.0 to override the
        wizard field default of 300.0 (which would otherwise add 300/10=30.00
        per child and push the result to 910.00).

        suffix — optional string appended to the camp name.  Pass a unique token
        (e.g. a short uuid4 hex) when test isolation requires each invocation to
        produce a distinct event.event name, so that teczka/budget unique
        constraints cannot collide with leftovers from a prior run in the same
        test database.
        """
        name = "QA Obóz 2026 — Turnus I"
        if suffix:
            name = f"{name} [{suffix}]"
        return {
            "name": name,
            # Exactly 10.0 days: math.ceil(864000s / 86400) = 10, not 11.
            "date_begin": datetime.datetime(2026, 7, 1, 8, 0, 0),
            "date_end": datetime.datetime(2026, 7, 11, 8, 0, 0),
            "seats": 10,
            "cost_lodging_per_day": 50.0,
            "cost_food_per_child_day": 30.0,
            # Salary fields: field default is 300.0 — zero them explicitly so
            # the only cost inputs are lodging+food and the pinned number stays 800.
            "salary_instructor_per_turnus": 0.0,
            "salary_wychowawca_per_turnus": 0.0,
            "salary_kierownik_per_turnus": 0.0,
            "vat_mode": "zw",
            "markup_percent": 0.0,
        }

    # ── 1. The §7 price calculator computes the number the owner will quote ──

    def test_price_calculator_is_exact(self):
        """The wizard's computed price matches the §7 formula to the cent."""
        wizard = (
            self.env["camp.create.wizard"].with_user(self.organizator).create(self._wizard_vals())
        )
        self.assertEqual(
            wizard.computed_price_per_child,
            800.00,
            "§7 calculator must produce (50+30)*10 = 800.00 for the pinned cost set; "
            f"got {wizard.computed_price_per_child}. A wrong number here means the "
            "organizator would quote parents an incorrect camp price.",
        )
        # apply-computed-price is the button the organizator clicks to lock it in
        wizard.action_apply_computed_price()
        self.assertEqual(
            wizard.price_per_child,
            800.00,
            "action_apply_computed_price must copy the computed number into "
            "price_per_child (the field the event ticket is priced from)",
        )

    # ── 2. The organizator actually creates a camp (event + budget) ──────────

    def test_organizator_creates_camp_event_and_budget(self):
        """Running the wizard as the organizator yields a real event + budget."""
        # Use a unique suffix so this test never collides with a teczka/budget
        # that may remain in the shared test DB from a previous run (the wizard
        # creates camp.teczka.ko with a UNIQUE(event_id) constraint; if the
        # very same event.event record somehow survived from a prior session,
        # the INSERT would fail with a duplicate-key error).
        run_id = uuid.uuid4().hex[:8]
        vals = self._wizard_vals(suffix=run_id)
        expected_name = vals["name"]

        wizard = self.env["camp.create.wizard"].with_user(self.organizator).create(vals)
        wizard.action_apply_computed_price()

        action = wizard.action_create_camp()

        # (a) The wizard returns an action opening the created event.event.
        self.assertIsInstance(
            action, dict, "action_create_camp must return an ir.actions.act_window dict"
        )
        self.assertEqual(
            action.get("res_model"),
            "event.event",
            "wizard must land the organizator on the newly created event.event",
        )
        event_id = action.get("res_id")
        self.assertTrue(event_id, "wizard action must carry the new event id (res_id)")

        # (b) The event genuinely exists with the wizard's data.
        event = self.env["event.event"].browse(event_id)
        self.assertTrue(event.exists(), "the camp event.event record must exist")
        self.assertEqual(event.name, expected_name)
        self.assertEqual(event.seats_max, 10, "event seat cap must carry the wizard's seats value")

        # (c) A budget was seeded for the camp (the organizator's money view).
        budget = self.env["camp.budget"].search([("event_id", "=", event.id)], limit=1)
        self.assertTrue(
            budget,
            "action_create_camp must seed a camp.budget for the new event — "
            "without it the organizator has no cost/BEP view for the camp",
        )
        self.assertTrue(
            budget.line_ids,
            "the seeded budget must carry at least the lodging/food/salary lines",
        )

        # (d) An event ticket priced from the calculator exists (what parents buy).
        ticket = self.env["event.event.ticket"].search([("event_id", "=", event.id)], limit=1)
        self.assertTrue(
            ticket,
            "the wizard must create the 'Udział w obozie' ticket parents register on",
        )
        self.assertEqual(
            ticket.price,
            800.00,
            "the ticket price must equal the applied §7 price (800.00) — this is the "
            "exact figure a parent is charged",
        )
