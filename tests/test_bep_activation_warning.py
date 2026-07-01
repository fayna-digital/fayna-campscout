# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""BEP activation warning — non-blocking (owner decision: WARN, not hard-block).

Corrected-TZ acceptance point (audit 2026-07-01): publishing a shift below its
break-even head-count must WARN the organizer (may knowingly run a below-BEP
camp) — it must NOT hard-block. Verifies the onchange returns a warning when
publishing below BEP, and is silent otherwise.

Perspective: independent QA engineer, not the code author.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestBepActivationWarning(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.event = cls.env["event.event"].create(
            {
                "name": "QA BEP Camp",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-08 18:00:00",
                "date_tz": "Europe/Warsaw",
                "seats_max": 40,
            }
        )
        cat_fixed = cls.env["camp.budget.category"].create(
            {"name": "BEP Ośrodek", "cost_kind": "stale", "vat_marza": True}
        )
        cat_var = cls.env["camp.budget.category"].create(
            {"name": "BEP Wyżywienie", "cost_kind": "zmienne_na_dziecko", "vat_marza": True}
        )
        cls.budget = cls.env["camp.budget"].create(
            {"event_id": cls.event.id, "price_per_child": 1500.0, "planned_children": 20}
        )
        # fixed 10000, price 1500, variable 500 → BEP = ceil(10) = 10; registered = 0.
        cls.env["camp.budget.line"].create(
            {
                "budget_id": cls.budget.id,
                "category_id": cat_fixed.id,
                "name": "Ośrodek",
                "per": "per_camp",
                "amount": 10000.0,
            }
        )
        cls.env["camp.budget.line"].create(
            {
                "budget_id": cls.budget.id,
                "category_id": cat_var.id,
                "name": "Wyżywienie",
                "per": "per_child",
                "amount": 500.0,
            }
        )

    def test_below_bep_publish_warns_but_does_not_block(self):
        """registered 0 < BEP 10 + website_published → warning dict returned."""
        self.assertEqual(self.budget.bep_children, 10)
        self.assertEqual(self.budget.registered_children, 0)
        self.event.website_published = True
        res = self.event._onchange_website_published_bep_warning()
        self.assertTrue(res and "warning" in res, "below-BEP publish must warn")
        # Non-blocking: the record is still published (no exception raised).
        self.assertTrue(self.event.website_published)

    def test_unpublished_no_warning(self):
        self.event.website_published = False
        res = self.event._onchange_website_published_bep_warning()
        self.assertFalse(res, "unpublished shift → no warning")

    def test_event_without_budget_no_warning(self):
        ev = self.env["event.event"].create(
            {
                "name": "QA No Budget",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-08 18:00:00",
                "date_tz": "Europe/Warsaw",
            }
        )
        ev.website_published = True
        res = ev._onchange_website_published_bep_warning()
        self.assertFalse(res, "no budget → no warning")
