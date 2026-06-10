# Fayna CampScout — tests for camp.budget (TZ_SPRINT_2026-06-10 §5, decision R8)
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestCampBudget(TransactionCase):
    """§5 Finanse: BEP, dwie marże (R8), guard cena≤koszt, analytic idempotency."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.event = cls.env["event.event"].create(
            {
                "name": "Budget Test Camp 2026",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-08 18:00:00",  # 7 dób
                "seats_max": 40,
            }
        )
        # Self-contained categories — do not rely on data/budget_categories.xml
        # being loaded (fragments may not be merged yet on a partial install).
        cls.cat_osrodek = cls.env["camp.budget.category"].create(
            {"name": "Test Ośrodek", "cost_kind": "stale", "vat_marza": True}
        )
        cls.cat_wyzywienie = cls.env["camp.budget.category"].create(
            {
                "name": "Test Wyżywienie",
                "cost_kind": "zmienne_na_dziecko",
                "vat_marza": True,
            }
        )
        cls.cat_reklama = cls.env["camp.budget.category"].create(
            {"name": "Test Reklama", "cost_kind": "stale", "vat_marza": False}
        )
        cls.cat_kadra = cls.env["camp.budget.category"].create(
            {
                "name": "Test Kadra",
                "cost_kind": "stale",
                "vat_marza": False,
                "is_salary": True,
            }
        )
        cls.budget = cls.env["camp.budget"].create(
            {
                "event_id": cls.event.id,
                "price_per_child": 1500.0,
                "planned_children": 20,
            }
        )

    def _add_line(self, category, amount, per="per_camp", name=False):
        return self.env["camp.budget.line"].create(
            {
                "budget_id": self.budget.id,
                "category_id": category.id,
                "name": name or category.name,
                "per": per,
                "amount": amount,
            }
        )

    # ------------------------------------------------------------------
    # BEP
    # ------------------------------------------------------------------

    def test_bep_basic(self):
        """fixed 10000, price 1500, variable 500/child → BEP = ceil(10) = 10."""
        self._add_line(self.cat_osrodek, 10000.0, per="per_camp")
        self._add_line(self.cat_wyzywienie, 500.0, per="per_child")
        self.assertEqual(self.budget.total_fixed, 10000.0)
        self.assertEqual(self.budget.variable_per_child, 500.0)
        self.assertEqual(self.budget.contribution_margin, 1000.0)
        self.assertEqual(self.budget.bep_children, 10)
        self.assertFalse(self.budget.bep_warning)

    def test_bep_ceil_rounds_up(self):
        """Non-integer break-even rounds UP (10001/1000 → 11 children)."""
        self._add_line(self.cat_osrodek, 10001.0, per="per_camp")
        self._add_line(self.cat_wyzywienie, 500.0, per="per_child")
        self.assertEqual(self.budget.bep_children, 11)

    def test_bep_guard_price_below_variable(self):
        """price ≤ variable_per_child → bep=0 + warning flag + loss badge."""
        self._add_line(self.cat_osrodek, 10000.0, per="per_camp")
        self._add_line(self.cat_wyzywienie, 500.0, per="per_child")
        self.budget.price_per_child = 400.0  # < 500 variable
        self.assertEqual(self.budget.bep_children, 0)
        self.assertTrue(self.budget.bep_warning)
        self.assertEqual(self.budget.fill_vs_bep, "loss")

    def test_per_child_day_scales_with_days(self):
        """per_child_day line: 50/day × 7 dób = 350 variable per child."""
        self._add_line(self.cat_wyzywienie, 50.0, per="per_child_day")
        self.assertEqual(self.budget.days, 7)
        self.assertEqual(self.budget.variable_per_child, 350.0)
        line = self.budget.line_ids[0]
        self.assertEqual(line.qty, 20 * 7)  # planned_children × days
        self.assertEqual(line.subtotal_planned, 50.0 * 20 * 7)

    # ------------------------------------------------------------------
    # Dwie marże (R8)
    # ------------------------------------------------------------------

    def test_two_margins_differ_with_reklama(self):
        """R8: reklama зменшує бізнес-маржу, але НЕ VAT-маржу (art. 119)."""
        self._add_line(self.cat_osrodek, 10000.0, per="per_camp")
        self._add_line(self.cat_wyzywienie, 500.0, per="per_child")
        self._add_line(self.cat_reklama, 2000.0, per="per_camp")
        # revenue = 1500 × 20 = 30000
        # VAT-marża costs: 10000 + 500×20 = 20000 → marża VAT = 10000
        # business costs: 20000 + 2000 = 22000 → marża biznesowa = 8000
        self.assertEqual(self.budget.revenue_planned, 30000.0)
        self.assertEqual(self.budget.marza_vat_planned, 10000.0)
        self.assertEqual(self.budget.marza_business_planned, 8000.0)
        self.assertEqual(
            self.budget.marza_vat_planned - self.budget.marza_business_planned,
            2000.0,
            "Різниця між маржами = сума reklama-лінії (vat_marza=False)",
        )
        # kadra (salary, vat_marza=False) теж лише в бізнес-маржі
        self._add_line(self.cat_kadra, 3000.0, per="per_camp")
        self.assertEqual(self.budget.marza_vat_planned, 10000.0)
        self.assertEqual(self.budget.marza_business_planned, 5000.0)
        self.assertEqual(self.budget.profit_at_planned, 5000.0)

    # ------------------------------------------------------------------
    # Analytic account
    # ------------------------------------------------------------------

    def test_ensure_analytic_idempotent(self):
        """_ensure_analytic() створює рахунок CAMP/{event} рівно один раз."""
        self.budget._ensure_analytic()
        account = self.budget.analytic_account_id
        self.assertTrue(account, "Analytic account must be created on first call")
        self.assertEqual(account.name, f"CAMP/{self.event.name}")
        # Second call: same account, no duplicate.
        self.budget._ensure_analytic()
        self.assertEqual(self.budget.analytic_account_id, account)
        count = self.env["account.analytic.account"].search_count(
            [("name", "=", f"CAMP/{self.event.name}")]
        )
        self.assertEqual(count, 1)

    def test_action_open_budget_creates_once(self):
        """event.action_open_budget: створює бюджет якщо нема, далі відкриває той самий."""
        event2 = self.env["event.event"].create(
            {
                "name": "Budget Test Camp 2026 — II",
                "date_begin": "2026-08-01 08:00:00",
                "date_end": "2026-08-08 18:00:00",
                "seats_max": 30,
            }
        )
        action = event2.action_open_budget()
        budget = self.env["camp.budget"].browse(action["res_id"])
        self.assertTrue(budget.exists())
        self.assertEqual(budget.event_id, event2)
        self.assertEqual(budget.planned_children, 30)  # defaulted from seats_max
        self.assertTrue(budget.analytic_account_id)
        action2 = event2.action_open_budget()
        self.assertEqual(action2["res_id"], budget.id, "Same budget reused, not duplicated")
