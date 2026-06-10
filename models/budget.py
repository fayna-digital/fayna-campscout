# Fayna CampScout — camp budget (TZ_SPRINT_2026-06-10 §5 «Фінанси», decision R8).
#
# Two margins — НЕ одна (R8):
#   * marza_vat_planned      — hipotetyczna marża VAT (art. 119 ustawy o VAT):
#                              przychód − ТІЛЬКИ koszty «dla bezpośredniej korzyści
#                              turysty» (category.vat_marza=True). База заліцок KSeF.
#   * marza_business_planned — бізнес-маржа: przychód − ВСІ koszty, включно з
#                              reklamą / kadrą / overhead (vat_marza=False).
#
# Models:
#   camp.budget.category — довідник категорій витрат (stałe/zmienne + vat_marza
#                          + is_salary для record-rule «kierownik без зарплат»).
#   camp.budget          — один бюджет на event.event (турнус), BEP + обидві маржі
#                          + analytic-рахунок CAMP/{event} для план-vs-факт.
#   camp.budget.line     — рядок витрат (per_camp / per_child / per_child_day).
#
# event.event ← _inherit у цьому ж файлі: budget_id + action_open_budget.
#
# TODO (окремий крок, потребує account-інтеграції):
#   * Rejestr faktur за місяць (numer, kontrahent, obóz, data zapłaty,
#     kwota marża / kwota gadżety) — стик із l10n_pl_ksef_margin P_PMarzy.
#   * Cash-flow по датах (потрібні дати платежів з account.move).

import logging
import math

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

# Analytic plan that groups all per-camp analytic accounts.
ANALYTIC_PLAN_NAME = "Obozy (CampScout)"
ANALYTIC_PREFIX = "CAMP"

# fill_vs_bep: registered/bep ≥ 1 → ok; ≥ WARNING_FILL_RATIO → warning; else loss.
WARNING_FILL_RATIO = 0.8


# ──────────────────────────────────────────────────────────────────────────────
# camp.budget.category  (довідник категорій витрат)
# ──────────────────────────────────────────────────────────────────────────────


class CampBudgetCategory(models.Model):
    _name = "camp.budget.category"
    _description = "Camp Budget Cost Category"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    cost_kind = fields.Selection(
        [
            ("stale", "Koszt stały (na turnus)"),
            ("zmienne_na_dziecko", "Koszt zmienny (na dziecko)"),
        ],
        string="Cost Kind",
        required=True,
        default="stale",
        help="Stały — fixed amount per shift; zmienny — scales with children count.",
    )
    vat_marza = fields.Boolean(
        string="Do VAT-marży (art. 119)",
        default=False,
        help=(
            "True = koszt «dla bezpośredniej korzyści turysty» (art. 119 ustawy "
            "o VAT) — входить у базу VAT-маржі. Reklama / kadra / overhead = False "
            "(decision R8): вони зменшують лише бізнес-маржу, НЕ VAT-маржу."
        ),
    )
    is_salary = fields.Boolean(
        string="Wynagrodzenia (kadra)",
        default=False,
        help=(
            "True = salary category. Kierownik's record rule hides budget LINES "
            "of salary categories (kierownik sees the budget read-only WITHOUT "
            "wynagrodzenia — TZ §5)."
        ),
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


# ──────────────────────────────────────────────────────────────────────────────
# camp.budget  (один бюджет на турнус)
# ──────────────────────────────────────────────────────────────────────────────


class CampBudget(models.Model):
    _name = "camp.budget"
    _description = "Camp Shift Budget (BEP + VAT/business margins)"
    _order = "event_id"

    event_id = fields.Many2one(
        "event.event",
        string="Camp Shift",
        required=True,
        index=True,
        ondelete="cascade",
    )
    camp_season_id = fields.Many2one(
        related="event_id.camp_season_id",
        store=True,
        string="Season",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    active = fields.Boolean(default=True)

    # ── Capacity / pricing inputs ─────────────────────────────────────────────

    capacity = fields.Integer(
        related="event_id.seats_max",
        store=True,
        string="Capacity (seats_max)",
        help="Maximum seats of the shift (event.event.seats_max).",
    )
    price_per_child = fields.Monetary(
        string="Cena za dziecko (realna)",
        currency_field="currency_id",
        help="Real average price per child AFTER discounts (not the list price).",
    )
    planned_children = fields.Integer(
        string="Planowana liczba dzieci",
        help="Expected number of paying children used for planned figures.",
    )
    days = fields.Integer(
        compute="_compute_days",
        store=True,
        string="Days (doby)",
        help="Shift duration in days — multiplier for per_child_day lines.",
    )

    line_ids = fields.One2many("camp.budget.line", "budget_id", string="Cost Lines")

    # ── Planned figures ───────────────────────────────────────────────────────

    revenue_planned = fields.Monetary(
        compute="_compute_financials",
        currency_field="currency_id",
        string="Przychód (plan)",
    )
    total_fixed = fields.Monetary(
        compute="_compute_financials",
        currency_field="currency_id",
        string="Koszty stałe",
    )
    variable_per_child = fields.Monetary(
        compute="_compute_financials",
        currency_field="currency_id",
        string="Koszt zmienny / dziecko",
    )
    total_variable_planned = fields.Monetary(
        compute="_compute_financials",
        currency_field="currency_id",
        string="Koszty zmienne (plan)",
    )
    contribution_margin = fields.Monetary(
        compute="_compute_financials",
        currency_field="currency_id",
        string="Contribution margin / dziecko",
        help="price_per_child − variable_per_child.",
    )
    bep_children = fields.Integer(
        compute="_compute_financials",
        string="BEP (min. dzieci)",
        help="ceil(koszty stałe / (cena − koszt zmienny na dziecko)). 0 + warning gdy cena ≤ koszt zmienny.",
    )
    bep_warning = fields.Boolean(
        compute="_compute_financials",
        string="BEP nieosiągalny",
        help="True gdy price_per_child ≤ variable_per_child — every child adds loss.",
    )
    marza_vat_planned = fields.Monetary(
        compute="_compute_financials",
        currency_field="currency_id",
        string="Marża VAT (art. 119)",
        help=(
            "Hipotetyczna marża VAT: przychód − TYLKO koszty «dla bezpośredniej "
            "korzyści turysty» (vat_marza=True). База заліцок (l10n_pl_ksef_margin)."
        ),
    )
    marza_business_planned = fields.Monetary(
        compute="_compute_financials",
        currency_field="currency_id",
        string="Marża biznesowa (z reklamą)",
        help="Бізнес-маржа: przychód − WSZYSTKIE koszty (включно з reklamą/kadrą) — R8.",
    )
    profit_at_planned = fields.Monetary(
        compute="_compute_financials",
        currency_field="currency_id",
        string="Zysk przy planowanej liczbie",
        help="Przychód − koszty stałe − koszty zmienne przy planned_children.",
    )

    # ── Fill vs BEP ───────────────────────────────────────────────────────────

    registered_children = fields.Integer(
        compute="_compute_registered_children",
        string="Zapisane dzieci",
        help="Open + done event.registration count on the shift.",
    )
    fill_vs_bep = fields.Selection(
        [
            ("ok", "OK — powyżej BEP"),
            ("warning", "Uwaga — blisko BEP"),
            ("loss", "Strata — poniżej BEP"),
        ],
        compute="_compute_fill_vs_bep",
        string="Status vs BEP",
    )
    fill_vs_bep_pct = fields.Float(
        compute="_compute_fill_vs_bep",
        string="Wypełnienie vs BEP (%)",
        help="registered / BEP × 100 (capped at 100 for the progressbar).",
    )

    # ── Actuals (analytic) ────────────────────────────────────────────────────

    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
        copy=False,
        help="Auto-created CAMP/{event} account — all invoices of the shift tag it.",
    )
    actual_revenue = fields.Monetary(
        compute="_compute_actuals",
        currency_field="currency_id",
        string="Przychód (fakt)",
        help="Sum of positive account.analytic.line amounts on the camp account.",
    )
    actual_costs = fields.Monetary(
        compute="_compute_actuals",
        currency_field="currency_id",
        string="Koszty (fakt)",
        help="Sum of negative account.analytic.line amounts (as a positive number).",
    )
    actual_profit = fields.Monetary(
        compute="_compute_actuals",
        currency_field="currency_id",
        string="Wynik (fakt)",
    )

    _sql_constraints = [
        (
            "unique_event_budget",
            "UNIQUE(event_id)",
            "Each camp shift can only have one budget.",
        )
    ]

    # ── Computes ──────────────────────────────────────────────────────────────

    @api.depends("event_id.name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _("Budżet: %s") % (rec.event_id.name or "—")

    @api.depends("event_id.date_begin", "event_id.date_end")
    def _compute_days(self):
        for rec in self:
            begin = rec.event_id.date_begin
            end = rec.event_id.date_end
            rec.days = max((end - begin).days, 1) if begin and end else 1

    @api.depends(
        "price_per_child",
        "planned_children",
        "days",
        "line_ids.amount",
        "line_ids.per",
        "line_ids.category_id.vat_marza",
    )
    def _compute_financials(self):
        for rec in self:
            children = rec.planned_children
            fixed = vat_fixed = var = vat_var = 0.0
            for line in rec.line_ids:
                if line.per == "per_camp":
                    fixed += line.amount
                    if line.category_id.vat_marza:
                        vat_fixed += line.amount
                else:
                    per_child = line.amount * (rec.days if line.per == "per_child_day" else 1)
                    var += per_child
                    if line.category_id.vat_marza:
                        vat_var += per_child

            rec.total_fixed = fixed
            rec.variable_per_child = var
            rec.total_variable_planned = var * children
            rec.revenue_planned = rec.price_per_child * children
            rec.contribution_margin = rec.price_per_child - var

            denominator = rec.price_per_child - var
            if denominator <= 0:
                # Guard: every child adds loss (or price unset) — BEP undefined.
                rec.bep_children = 0
                rec.bep_warning = True
            else:
                rec.bep_children = math.ceil(round(fixed / denominator, 6))
                rec.bep_warning = False

            rec.marza_vat_planned = rec.revenue_planned - (vat_fixed + vat_var * children)
            total_costs_planned = fixed + var * children
            rec.marza_business_planned = rec.revenue_planned - total_costs_planned
            rec.profit_at_planned = rec.marza_business_planned

    @api.depends("event_id.registration_ids.state")
    def _compute_registered_children(self):
        for rec in self:
            rec.registered_children = len(
                rec.event_id.registration_ids.filtered(lambda r: r.state in ("open", "done"))
            )

    @api.depends("registered_children", "bep_children", "bep_warning")
    def _compute_fill_vs_bep(self):
        for rec in self:
            if rec.bep_warning:
                rec.fill_vs_bep = "loss"
                rec.fill_vs_bep_pct = 0.0
                continue
            bep = rec.bep_children
            if not bep:
                # No fixed costs (or no lines yet): break-even from child #1.
                rec.fill_vs_bep = "ok"
                rec.fill_vs_bep_pct = 100.0
                continue
            ratio = rec.registered_children / bep
            rec.fill_vs_bep_pct = min(ratio * 100.0, 100.0)
            if ratio >= 1:
                rec.fill_vs_bep = "ok"
            elif ratio >= WARNING_FILL_RATIO:
                rec.fill_vs_bep = "warning"
            else:
                rec.fill_vs_bep = "loss"

    def _compute_actuals(self):
        """Plan-vs-fact from account.analytic.line on the camp's analytic account.

        Graceful degradation: when the analytic model is unavailable or no
        account is linked yet, actuals stay 0 (the planned dashboard still works).
        TODO: per-category actual split (needs invoice-line → budget-category
        mapping; part of the Rejestr faktur step).
        """
        line_model = self.env.get("account.analytic.line")
        for rec in self:
            revenue = costs = 0.0
            if line_model is not None and rec.analytic_account_id:
                # +/- split needs raw amounts (a single read_group sum would
                # net revenue against costs).
                amounts = (
                    line_model.sudo()
                    .search([("account_id", "=", rec.analytic_account_id.id)])
                    .mapped("amount")
                )
                revenue = sum(a for a in amounts if a > 0)
                costs = -sum(a for a in amounts if a < 0)
            rec.actual_revenue = revenue
            rec.actual_costs = costs
            rec.actual_profit = revenue - costs

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains("price_per_child", "planned_children")
    def _check_non_negative(self):
        for rec in self:
            if rec.price_per_child < 0:
                raise ValidationError(_("Price per child cannot be negative."))
            if rec.planned_children < 0:
                raise ValidationError(_("Planned children count cannot be negative."))

    # ── Analytic account ──────────────────────────────────────────────────────

    @api.model
    def _get_camp_analytic_plan(self):
        """Return (and lazily create) the shared 'Obozy' analytic plan.

        Odoo 17: account.analytic.account.plan_id is required, so every camp
        account hangs off one dedicated plan.
        """
        plan_model = self.env.get("account.analytic.plan")
        if plan_model is None:
            return None
        plan = plan_model.sudo().search([("name", "=", ANALYTIC_PLAN_NAME)], limit=1)
        if not plan:
            plan = plan_model.sudo().create({"name": ANALYTIC_PLAN_NAME})
        return plan

    def _ensure_analytic(self):
        """Create the CAMP/{event.name} analytic account once. Idempotent.

        Graceful: if the analytic models are unavailable, logs and returns
        an empty value — budget planning keeps working without actuals.
        """
        account_model = self.env.get("account.analytic.account")
        for rec in self:
            if rec.analytic_account_id:
                continue
            if account_model is None:
                _logger.warning(
                    "camp.budget %s: account.analytic.account unavailable — "
                    "skipping analytic creation (actuals stay 0).",
                    rec.id,
                )
                continue
            plan = rec._get_camp_analytic_plan()
            if plan is None:
                continue
            name = f"{ANALYTIC_PREFIX}/{rec.event_id.name}"
            existing = account_model.sudo().search(
                [("name", "=", name), ("plan_id", "=", plan.id)], limit=1
            )
            rec.analytic_account_id = existing or account_model.sudo().create(
                {
                    "name": name,
                    "plan_id": plan.id,
                    "company_id": rec.company_id.id,
                }
            )
        return self.mapped("analytic_account_id")

    def action_ensure_analytic(self):
        self._ensure_analytic()
        return True


# ──────────────────────────────────────────────────────────────────────────────
# camp.budget.line  (рядок витрат)
# ──────────────────────────────────────────────────────────────────────────────


class CampBudgetLine(models.Model):
    _name = "camp.budget.line"
    _description = "Camp Budget Cost Line"
    _order = "category_id, id"

    budget_id = fields.Many2one(
        "camp.budget",
        required=True,
        index=True,
        ondelete="cascade",
    )
    category_id = fields.Many2one(
        "camp.budget.category",
        string="Category",
        required=True,
        index=True,
        ondelete="restrict",
    )
    name = fields.Char(
        string="Description",
        help="Optional detail (e.g. supplier / contract). Defaults to category name.",
    )
    currency_id = fields.Many2one(related="budget_id.currency_id")
    per = fields.Selection(
        [
            ("per_camp", "Na turnus (stały)"),
            ("per_child", "Na dziecko"),
            ("per_child_day", "Na dziecko / dobę"),
        ],
        string="Per",
        required=True,
        default="per_camp",
        help=(
            "How 'amount' scales: per_camp — total for the shift (fixed); "
            "per_child — × planned children; per_child_day — × children × days."
        ),
    )
    amount = fields.Monetary(
        currency_field="currency_id",
        required=True,
        help="Per the selected unit: total / per child / per child per day.",
    )
    days = fields.Integer(related="budget_id.days")
    qty = fields.Float(
        compute="_compute_qty",
        string="Qty (plan)",
        help="per_camp → 1; per_child → planned children; per_child_day → children × days.",
    )
    subtotal_planned = fields.Monetary(
        compute="_compute_qty",
        currency_field="currency_id",
        string="Razem (plan)",
    )
    vat_marza = fields.Boolean(related="category_id.vat_marza")
    is_salary = fields.Boolean(related="category_id.is_salary")

    @api.depends("per", "amount", "budget_id.planned_children", "budget_id.days")
    def _compute_qty(self):
        for line in self:
            children = line.budget_id.planned_children
            if line.per == "per_camp":
                line.qty = 1.0
            elif line.per == "per_child":
                line.qty = float(children)
            else:  # per_child_day
                line.qty = float(children * line.budget_id.days)
            line.subtotal_planned = line.amount * line.qty

    @api.onchange("category_id")
    def _onchange_category_id(self):
        for line in self:
            if not line.category_id:
                continue
            if not line.name:
                line.name = line.category_id.name
            line.per = "per_camp" if line.category_id.cost_kind == "stale" else "per_child"


# ──────────────────────────────────────────────────────────────────────────────
# event.event  ← _inherit  (budget link + open/create action)
# ──────────────────────────────────────────────────────────────────────────────


class EventEventBudget(models.Model):
    _inherit = "event.event"

    camp_budget_ids = fields.One2many(
        "camp.budget",
        "event_id",
        string="Budgets",
        help="Technical O2M — UNIQUE(event_id) guarantees at most one record.",
    )
    camp_budget_id = fields.Many2one(
        "camp.budget",
        compute="_compute_camp_budget_id",
        string="Budget",
    )

    @api.depends("camp_budget_ids")
    def _compute_camp_budget_id(self):
        for event in self:
            event.camp_budget_id = event.camp_budget_ids[:1]

    def action_open_budget(self):
        """Open the shift budget; create it (+ analytic account) on first use."""
        self.ensure_one()
        budget = self.camp_budget_ids[:1]
        if not budget:
            budget = self.env["camp.budget"].create(
                {
                    "event_id": self.id,
                    "planned_children": self.seats_max or 0,
                }
            )
        budget._ensure_analytic()
        return {
            "type": "ir.actions.act_window",
            "name": _("Budżet: %s") % self.name,
            "res_model": "camp.budget",
            "res_id": budget.id,
            "view_mode": "form",
            "target": "current",
        }
