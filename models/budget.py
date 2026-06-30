# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
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
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Analytic plan that groups all per-camp analytic accounts.
ANALYTIC_PLAN_NAME = "Obozy (CampScout)"
ANALYTIC_PREFIX = "CAMP"

# fill_vs_bep: registered/bep ≥ 1 → ok; ≥ WARNING_FILL_RATIO → warning; else loss.
WARNING_FILL_RATIO = 0.8

# ir.config_parameter holding the external księgowa (accountant) e-mail —
# recipient of the per-camp financial evidence (§10/§4c). The accountant is
# OUTSIDE the system: invoices via KSeF + one evidence per shift by e-mail.
_PARAM_KSIEGOWA_EMAIL = "fayna_camp_portal.ksiegowa_email"


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

    # ── Ewidencja dla zewnętrznej księgowej (§10/§4c) ─────────────────────────
    # RODO art.9: agregaty finansowe TYLKO — żadnych danych dzieci. Odbiorcą
    # jest urzędowy adres księgowej (config-param), nie e-mail wpisany ad hoc.

    ksiegowa_email = fields.Char(
        compute="_compute_ksiegowa_email",
        store=True,
        readonly=False,
        string="E-mail księgowej",
        help=(
            "Adres zewnętrznej księgowej — odbiorca ewidencji finansowej tego "
            "turnusu. Domyślnie z parametru systemu; można nadpisać dla turnusu. "
            "RODO art.9: ewidencja zawiera tylko kwoty zbiorcze, bez danych dzieci."
        ),
    )

    evidence_revenue_net = fields.Monetary(
        compute="_compute_evidence_vat",
        currency_field="currency_id",
        string="Przychód netto (ewidencja)",
        help="Suma kwot netto z faktur sprzedaży powiązanych z kontem analitycznym obozu.",
    )
    evidence_revenue_vat = fields.Monetary(
        compute="_compute_evidence_vat",
        currency_field="currency_id",
        string="VAT należny (ewidencja)",
        help="Suma kwot VAT z faktur sprzedaży powiązanych z kontem analitycznym obozu.",
    )
    evidence_revenue_gross = fields.Monetary(
        compute="_compute_evidence_vat",
        currency_field="currency_id",
        string="Przychód brutto (ewidencja)",
        help="Przychód netto + VAT należny (faktury sprzedaży).",
    )
    evidence_costs_net = fields.Monetary(
        compute="_compute_evidence_vat",
        currency_field="currency_id",
        string="Koszty netto (ewidencja)",
        help="Suma kwot netto z faktur zakupu (vendor bills) powiązanych z kontem analitycznym obozu.",
    )
    evidence_costs_vat = fields.Monetary(
        compute="_compute_evidence_vat",
        currency_field="currency_id",
        string="VAT naliczony (ewidencja)",
        help="Suma kwot VAT z faktur zakupu powiązanych z kontem analitycznym obozu.",
    )
    evidence_costs_gross = fields.Monetary(
        compute="_compute_evidence_vat",
        currency_field="currency_id",
        string="Koszty brutto (ewidencja)",
        help="Koszty netto + VAT naliczony (faktury zakupu).",
    )
    evidence_balance = fields.Monetary(
        compute="_compute_evidence_vat",
        currency_field="currency_id",
        string="Saldo (ewidencja)",
        help="Przychód netto − koszty netto (wynik turnusu wg faktur).",
    )
    evidence_vat_lines = fields.Json(
        compute="_compute_evidence_vat",
        string="VAT — rozbicie wg stawek",
        help="Rozbicie kwot wg stawek VAT: [{rate, base, vat, kind}]. Tylko agregaty.",
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

    # ── Ewidencja księgowej: e-mail + rozbicie VAT ────────────────────────────

    @api.depends("event_id")
    def _compute_ksiegowa_email(self):
        """Default the accountant e-mail from the system parameter.

        Mirrors teczka_ko.delegatura_email: a per-shift override is kept if an
        organizator typed one by hand; otherwise the module-level default wins.
        """
        default_email = self.env["ir.config_parameter"].sudo().get_param(_PARAM_KSIEGOWA_EMAIL, "")
        for rec in self:
            if rec.ksiegowa_email:
                continue
            rec.ksiegowa_email = default_email or False

    def _compute_evidence_vat(self):
        """Aggregate net / VAT / gross per shift from POSTED account.move lines.

        Source: account.move.line whose ``analytic_distribution`` references the
        camp's analytic account, on posted customer invoices (revenue) and
        vendor bills (costs). Pure aggregates — NO child personal data (RODO
        art.9). Graceful: stays 0 when account models are unavailable or no
        analytic account is linked yet.
        """
        MoveLine = self.env.get("account.move.line")
        for rec in self:
            rev_net = rev_vat = cost_net = cost_vat = 0.0
            vat_map = {}  # (kind, rate) -> {"base": x, "vat": y}
            account = rec.analytic_account_id
            if MoveLine is not None and account:
                lines = MoveLine.sudo().search(
                    [
                        ("parent_state", "=", "posted"),
                        (
                            "move_id.move_type",
                            "in",
                            ("out_invoice", "out_refund", "in_invoice", "in_refund"),
                        ),
                        ("display_type", "=", False),
                    ]
                )
                for line in lines:
                    dist = line.analytic_distribution or {}
                    # analytic_distribution keys are str(account.id) → percent.
                    if str(account.id) not in {str(k) for k in dist}:
                        continue
                    move_type = line.move_id.move_type
                    is_revenue = move_type in ("out_invoice", "out_refund")
                    sign = -1.0 if move_type in ("out_refund", "in_refund") else 1.0
                    base = abs(line.price_subtotal) * sign
                    vat = (abs(line.price_total) - abs(line.price_subtotal)) * sign
                    rate = sum(line.tax_ids.mapped("amount")) if line.tax_ids else 0.0
                    kind = "revenue" if is_revenue else "cost"
                    if is_revenue:
                        rev_net += base
                        rev_vat += vat
                    else:
                        cost_net += base
                        cost_vat += vat
                    bucket = vat_map.setdefault((kind, rate), {"base": 0.0, "vat": 0.0})
                    bucket["base"] += base
                    bucket["vat"] += vat

            rec.evidence_revenue_net = rev_net
            rec.evidence_revenue_vat = rev_vat
            rec.evidence_revenue_gross = rev_net + rev_vat
            rec.evidence_costs_net = cost_net
            rec.evidence_costs_vat = cost_vat
            rec.evidence_costs_gross = cost_net + cost_vat
            rec.evidence_balance = rev_net - cost_net
            rec.evidence_vat_lines = [
                {
                    "kind": kind,
                    "rate": rate,
                    "base": round(vals["base"], 2),
                    "vat": round(vals["vat"], 2),
                }
                for (kind, rate), vals in sorted(vat_map.items())
            ]

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

    # ── Ewidencja dla księgowej (§10/§4c) — PDF + e-mail ──────────────────────

    def action_print_evidence(self):
        """Render the per-shift financial evidence as a QWeb-PDF (no child data)."""
        self.ensure_one()
        return self.env.ref("fayna_camp_portal.action_report_camp_budget_evidence").report_action(
            self
        )

    def action_send_evidence_to_ksiegowa(self):
        """Wyślij ewidencję finansową turnusu (PDF) na e-mail księgowej.

        Renders the per-shift financial evidence (revenue / costs / balance /
        VAT breakdown — pure aggregates, NO child data, RODO art.9) as a
        QWeb-PDF and e-mails it to ``ksiegowa_email``. Logs who / when / where
        to the chatter. Kierownik/organizator may run it; the render and mail
        go through sudo (kierownik has the budget read-only by record rule).
        """
        self.ensure_one()
        email_to = (self.ksiegowa_email or "").strip()
        if not email_to:
            raise UserError(
                _(
                    "Brak adresu e-mail księgowej. Uzupełnij pole „E-mail księgowej” "
                    "lub parametr systemu (Ustawienia → fayna_camp_portal.ksiegowa_email)."
                )
            )

        report = self.env.ref("fayna_camp_portal.action_report_camp_budget_evidence")
        pdf_content, _ext = report.sudo()._render_qweb_pdf(
            "fayna_camp_portal.report_camp_budget_evidence",
            res_ids=self.ids,
        )
        filename = "Ewidencja_{}.pdf".format((self.event_id.name or "").replace(" ", "_"))
        attachment = (
            self.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": filename,
                    "type": "binary",
                    "raw": pdf_content,
                    "mimetype": "application/pdf",
                    "res_model": self._name,
                    "res_id": self.id,
                }
            )
        )

        company = self.event_id.company_id or self.env.company
        email_from = company.email or self.env.user.email_formatted or "noreply@campscout.eu"
        body_html = _(
            "<p>Szanowni Państwo,</p>"
            "<p>w załączeniu przesyłamy ewidencję finansową turnusu "
            "<strong>%(event)s</strong> (organizator: %(org)s):<br/>"
            "przychody, koszty, saldo oraz rozbicie VAT.</p>"
            "<p>Ewidencja zawiera wyłącznie kwoty zbiorcze — bez danych uczestników "
            "(RODO art. 9). Faktury źródłowe otrzymują Państwo przez KSeF.</p>"
            "<p>Z poważaniem,<br/>%(sender)s</p>",
            event=self.event_id.name or "—",
            org=company.name or "—",
            sender=self.env.user.name or "CampScout",
        )

        mail = (
            self.env["mail.mail"]
            .sudo()
            .create(
                {
                    "subject": _("Ewidencja finansowa turnusu — %s", self.event_id.name or ""),
                    "body_html": body_html,
                    "email_from": email_from,
                    "email_to": email_to,
                    "attachment_ids": [(4, attachment.id)],
                }
            )
        )
        mail.send()

        log = _(
            "📊 Ewidencja finansowa wysłana do księgowej.<br/>"
            "Odbiorca: <strong>%(to)s</strong><br/>"
            "Przychód netto: %(rev)s · Koszty netto: %(cost)s · Saldo: %(bal)s<br/>"
            "Wysłał(a): %(user)s<br/>"
            "Data: %(when)s",
            to=email_to,
            rev=f"{self.evidence_revenue_net:.2f}",
            cost=f"{self.evidence_costs_net:.2f}",
            bal=f"{self.evidence_balance:.2f}",
            user=self.env.user.name,
            when=fields.Datetime.to_string(fields.Datetime.now()),
        )
        # sudo: kierownik has the budget read-only (record rule); the audit
        # note must still be written regardless of write rights.
        self.sudo().message_post(body=log)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Ewidencja wysłana"),
                "message": _("Ewidencja została wysłana na adres %s.") % email_to,
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def _cron_send_monthly_evidence(self):
        """Optional monthly auto-evidence: e-mail one evidence per active budget.

        Sends only when a księgowa e-mail is configured (per-budget or global)
        AND the shift has booked analytic figures, so empty drafts are skipped.
        Failures on one budget never block the rest.
        """
        default_email = self.env["ir.config_parameter"].sudo().get_param(_PARAM_KSIEGOWA_EMAIL, "")
        budgets = self.search([("active", "=", True), ("analytic_account_id", "!=", False)])
        sent = 0
        for budget in budgets:
            email_to = (budget.ksiegowa_email or default_email or "").strip()
            if not email_to:
                continue
            # Skip shifts with no booked figures yet (nothing to report).
            if not (budget.evidence_revenue_net or budget.evidence_costs_net):
                continue
            try:
                budget.action_send_evidence_to_ksiegowa()
                sent += 1
            except Exception as exc:  # noqa: BLE001 — one bad budget must not stop the cron
                _logger.warning("Monthly evidence cron: budget %s failed: %s", budget.id, exc)
        _logger.info("Monthly evidence cron: sent %s evidence e-mail(s).", sent)
        return sent


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
