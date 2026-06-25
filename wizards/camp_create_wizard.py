# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — майстер «Новий табір» (TZ_SPRINT_2026-06-10 §6, R11/R12)
#
# One wizard run generates the full shift skeleton in NATIVE tables
# (§8a rule: БІЗНЕС-записів у XML НЕМАЄ — табори/події/квитки створює
# лише майстер):
#   1. event.event (seats_max, dates, venue partner) — R11: продаж лишається
#      через sale.order + event_sale; квиток = шар місткості.
#   2. event.event.ticket «Udział w obozie» + service/event product.
#   3. camp.budget через існуючий event.action_open_budget() (він же робить
#      _ensure_analytic) + стартові лінії: nocleg, wyżywienie, kierownik.
#      Зарплатні лінії wychowawców НЕ тут — їх додає двигун автоштату
#      (models/staffing.py) у міру реєстрацій.
#   4. camp.teczka.ko — порожній чеклист готовності KO.
#   5. Каркас груп: одна порожня camp.group «Grupa 1» (далі —
#      camp.group.action_auto_split у міру заповнення).
#
# R12: дефолтні ставки кадри — ir.config_parameter
#   fayna_camp_portal.salary_wychowawca_default / salary_kierownik_default
#   (ті самі ключі читає двигун автоштату).
import logging
import math

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

_TICKET_NAME = "Udział w obozie"

_SALARY_WYCHOWAWCA_PARAM = "fayna_camp_portal.salary_wychowawca_default"
_SALARY_KIEROWNIK_PARAM = "fayna_camp_portal.salary_kierownik_default"


class CampCreateWizard(models.TransientModel):
    _name = "camp.create.wizard"
    _description = "Майстер «Новий табір» (event + квиток + бюджет + teczka + групи)"

    # ── ADR Фаза A §4 — multi-step ────────────────────────────────────────
    step = fields.Selection(
        [
            ("type", "1. Typ obozu"),
            ("basics", "2. Podstawowe dane"),
            ("logo", "3. Logo"),
            ("dates", "4. Daty i miejscowość"),
            ("accommodation", "5. Obiekt"),
            ("frame_day", "6. Plan dnia"),
            ("program", "7. Program"),
            ("capacity", "8. Miejsca i finanse"),
        ],
        default="type",
        required=True,
        string=_("Krok"),
        help=_("Current step in the multi-step wizard."),
    )

    # Step 1 — typ obozu (mirrors camp.program.wypoczynku)
    vacation_form = fields.Selection(
        [
            ("kolonia", "Kolonia"),
            ("oboz", "Obóz"),
            ("biwak", "Biwak"),
            ("zimowisko", "Zimowisko"),
            ("inne", "Inne"),
        ],
        default="oboz",
        string=_("Forma wypoczynku"),
        help=_("Formal form of leisure as classified by MEN regulation."),
    )
    camp_type = fields.Selection(
        [
            ("kolonijny", "Kolonijny"),
            ("obozowy", "Obozowy"),
            ("inne", "Inne"),
        ],
        string=_("Typ obozu"),
        help=_("Camp type classification for Kuratorium filing."),
    )
    accommodation_type = fields.Selection(
        [
            ("hotel", "Hotel / pensjonat"),
            ("occasional", "Obiekt okazjonalny"),
            ("tent", "Pole namiotowe"),
            ("school", "Szkoła / placówka"),
            ("other", "Inne"),
        ],
        default="hotel",
        string=_("Rodzaj obiektu"),
        help=_("Type of accommodation used."),
    )

    # Step 3 — logo
    logo_image = fields.Image(
        string=_("Logo obozu"),
        max_width=512,
        max_height=512,
        help=_("Camp logo — will be set on the camp product template (image_1920)."),
    )

    # Step 6 — рамковий день (mirrors CampProgramStructured)
    fd_wake_time = fields.Float(default=7.0, string=_("Pobudka"))
    fd_breakfast = fields.Float(default=8.0, string=_("Śniadanie"))
    fd_lunch = fields.Float(default=13.0, string=_("Obiad"))
    fd_afternoon_rest = fields.Float(default=14.0, string=_("Cisza poobiednia"))
    fd_snack = fields.Float(default=16.0, string=_("Podwieczorek"))
    fd_dinner = fields.Float(default=18.0, string=_("Kolacja"))
    fd_lights_out = fields.Float(default=22.0, string=_("Cisza nocna"))
    fd_meal_duration = fields.Float(default=0.75, string=_("Czas posiłku (h)"))
    fd_rest_duration = fields.Float(default=1.0, string=_("Czas ciszy poobiedniej (h)"))

    # Step 7 — program options
    also_generate_rain_plan = fields.Boolean(
        default=False,
        string=_("Generuj też plan B (deszczowy)"),
        help=_("If True, a second CampProgramStructured (is_rain_plan=True) is generated."),
    )

    name = fields.Char(
        required=True,
        string=_("Camp shift name"),
        help=_("e.g. 'Obóz NWŚ — turnus 2 (2026)'."),
    )
    date_begin = fields.Datetime(
        required=True,
        string=_("Start"),
        help=_("Shift start — also the age anchor for art. 92c group limits."),
    )
    date_end = fields.Datetime(
        required=True,
        string=_("End"),
        help=_("Shift end — per_child_day budget lines multiply by the day count."),
    )
    location = fields.Char(
        string=_("Address / location"),
        help=_(
            "Venue address. A res.partner with this name is found or created "
            "and linked as the event venue (address_id)."
        ),
    )
    seats = fields.Integer(
        required=True,
        default=40,
        string=_("Seats (місткість)"),
        help=_("Capacity of the shift: event.seats_max AND the ticket seats_max (R11)."),
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self._default_currency(),
        string=_("Currency"),
    )
    price_per_child = fields.Monetary(
        currency_field="currency_id",
        string=_("Cena za dziecko"),
        help=_("Ticket price AND the budget's real price per child (BEP input)."),
    )
    cost_lodging_per_day = fields.Monetary(
        currency_field="currency_id",
        string=_("Nocleg / dziecko / dobę"),
        help=_("Lodging cost per child per day → budget line 'Nocleg' (per_child_day)."),
    )
    cost_food_per_child_day = fields.Monetary(
        currency_field="currency_id",
        string=_("Wyżywienie / dziecko / dobę"),
        help=_("Food cost per child per day → budget line 'Wyżywienie' (per_child_day)."),
    )
    salary_wychowawca_per_turnus = fields.Monetary(
        currency_field="currency_id",
        default=lambda self: self._default_salary(_SALARY_WYCHOWAWCA_PARAM),
        string=_("Stawka wychowawcy / turnus"),
        help=_(
            "R12: per-shift wychowawca salary. Default from ir.config_parameter "
            "fayna_camp_portal.salary_wychowawca_default. Used by the auto-staffing "
            "engine when it opens vacancies (no budget line is added upfront)."
        ),
    )
    salary_kierownik_per_turnus = fields.Monetary(
        currency_field="currency_id",
        default=lambda self: self._default_salary(_SALARY_KIEROWNIK_PARAM),
        string=_("Stawka kierownika / turnus"),
        help=_(
            "R12: per-shift kierownik salary. Default from ir.config_parameter "
            "fayna_camp_portal.salary_kierownik_default. Added as a per_camp "
            "budget line (kadra / is_salary)."
        ),
    )

    # ── §7 КАЛЬКУЛЯТОР ЦІНИ ───────────────────────────────────────────────
    # Cost-buildup поля (на дитину або на весь табір — позначено в help)
    # ------- кадра -------
    salary_instructor_per_turnus = fields.Monetary(
        currency_field="currency_id",
        default=300.0,
        string=_("Stawka instruktora / turnus"),
        help=_("Per-shift instructor salary (300 zł default per TZ §7). Divided by seats in calc."),
    )
    # ------- інші витрати на дитину/день -------
    cost_insurance_per_child_day = fields.Float(
        string=_("Ubezpieczenie / dziecko / dobę [zł]"),
        digits=(10, 2),
        default=0.0,
        help=_("NNW insurance cost per child per day (e.g. 1.50 zł)."),
    )
    # ------- одноразові на дитину -------
    cost_merch_per_child = fields.Float(
        string=_("Gadżety / dziecko [zł]"),
        digits=(10, 2),
        default=0.0,
        help=_(
            "Merch cost per child. Note: merch is a physical good (VAT 23%)"
            " and should be invoiced as a separate line item."
        ),
    )
    cost_stationery_per_child = fields.Float(
        string=_("Materiały / dziecko [zł]"),
        digits=(10, 2),
        default=0.0,
        help=_("Stationery / consumables per child for the whole shift."),
    )
    cost_operational_per_child = fields.Float(
        string=_("Operacyjne / dziecko [zł]"),
        digits=(10, 2),
        default=0.0,
        help=_("Venue rent, activities, other per-child operational costs for the whole shift."),
    )
    # ------- реклама (загальний бюджет, constrain ≤20% суми витрат) -------
    cost_advertising_total = fields.Float(
        string=_("Reklama (ogółem) [zł]"),
        digits=(10, 2),
        default=0.0,
        help=_(
            "Total advertising/marketing budget for the shift."
            " Constrained to ≤ 20% of total cost budget (§7). Spread per child."
        ),
    )
    # ------- VAT та націнка -------
    vat_mode = fields.Selection(
        [
            ("zw", "Zwolniona art.43 ust.1 pkt 24 (opieka nad dziećmi)"),
            ("marza", "VAT-marża 23% (art.119, firma turystyczna)"),
            ("standard", "Standard 23%"),
        ],
        default="zw",
        required=True,
        string=_("Tryb VAT"),
        help=_(
            "VAT regime for the camp service.\n"
            "• zw — default, safe; applies when organizer = fundacja/NGO (art.43).\n"
            "• marza — organizer is a registered tourism firm (rejestr turystyki); VAT"
            " only on the margin component.\n"
            "• standard — full 23% on the whole price.\n"
            "[UWAGA] Consult a księgowa before switching from 'zw' — grey-zone per TZ §7."
        ),
    )
    markup_percent = fields.Float(
        string=_("Marża [%]"),
        digits=(5, 2),
        default=5.0,
        help=_("Markup percentage added on top of total cost. Must be ≥ 0."),
    )
    # ------- результат калькулятора -------
    computed_price_per_child = fields.Monetary(
        currency_field="currency_id",
        string=_("Obliczona cena / dziecko"),
        compute="_compute_price_per_child",
        store=True,
        readonly=True,
        help=_(
            "Calculated price per child (cost-buildup + markup + VAT).\n"
            "Use 'Zastosuj jako cenę' to copy this value to the actual ticket price."
        ),
    )
    vat_note = fields.Char(
        string=_("Uwaga VAT"),
        compute="_compute_price_per_child",
        store=True,
        readonly=True,
        help=_("Human-readable note on VAT treatment for the chosen vat_mode."),
    )

    # ── compute ───────────────────────────────────────────────────────────

    @api.depends(
        "cost_lodging_per_day",
        "cost_food_per_child_day",
        "salary_wychowawca_per_turnus",
        "salary_kierownik_per_turnus",
        "salary_instructor_per_turnus",
        "cost_insurance_per_child_day",
        "cost_merch_per_child",
        "cost_stationery_per_child",
        "cost_operational_per_child",
        "cost_advertising_total",
        "markup_percent",
        "vat_mode",
        "seats",
        "date_begin",
        "date_end",
    )
    def _compute_price_per_child(self):
        """§7 cost-buildup formula (per child):

        days = date_end - date_begin (full calendar days, min 1)
        children = seats (min 1 to avoid ZeroDivisionError)

        per_child_day costs → × days:
            lodging   = cost_lodging_per_day × days
            food      = cost_food_per_child_day × days
            insurance = cost_insurance_per_child_day × days

        per_child lump-sum costs:
            merch, stationery, operational

        per_camp costs → ÷ children:
            wychowawca salary  (total for all wychowawcy is assumed to be
                               salary_wychowawca_per_turnus; staffing engine
                               multiplies this later — here we take it as-is)
            kierownik salary
            instructor salary
            advertising_total

        cost_sum = sum of all above
        base = cost_sum × (1 + markup_percent / 100)
        price:
            zw       → base  (no VAT added; 0% effective rate)
            marza    → base  (VAT only on the margin portion = not in price calc;
                              vat_note explains; gross = base)
            standard → base × 1.23

        Rounded to 2 decimal places.
        """
        for rec in self:
            # ── guard ──────────────────────────────────────────────────
            children = max(rec.seats or 1, 1)
            if rec.date_begin and rec.date_end and rec.date_end > rec.date_begin:
                delta = rec.date_end - rec.date_begin
                days = max(math.ceil(delta.total_seconds() / 86400), 1)
            else:
                days = 1

            # ── per-child-day costs ────────────────────────────────────
            lodging = (rec.cost_lodging_per_day or 0.0) * days
            food = (rec.cost_food_per_child_day or 0.0) * days
            insurance = (rec.cost_insurance_per_child_day or 0.0) * days

            # ── per-camp costs spread per child ────────────────────────
            salary_wych = (rec.salary_wychowawca_per_turnus or 0.0) / children
            salary_kier = (rec.salary_kierownik_per_turnus or 0.0) / children
            salary_instr = (rec.salary_instructor_per_turnus or 0.0) / children
            advertising = (rec.cost_advertising_total or 0.0) / children

            # ── per-child lump-sum ─────────────────────────────────────
            merch = rec.cost_merch_per_child or 0.0
            stationery = rec.cost_stationery_per_child or 0.0
            operational = rec.cost_operational_per_child or 0.0

            cost_sum = (
                lodging
                + food
                + insurance
                + salary_wych
                + salary_kier
                + salary_instr
                + advertising
                + merch
                + stationery
                + operational
            )

            markup = max(rec.markup_percent or 0.0, 0.0)
            base = cost_sum * (1.0 + markup / 100.0)

            vat_mode = rec.vat_mode or "zw"
            if vat_mode == "standard":
                price = base * 1.23
                note = _("Cena brutto ze stawką VAT 23% (standard).")
            elif vat_mode == "marza":
                price = base
                note = _(
                    "VAT-marża (art.119): VAT 23% naliczany TYLKO od marży"
                    " (marża = cena – koszt usług nabytych). Kwota powyżej"
                    " = podstawa kalkulacji; rzeczywisty VAT do marży liczy księgowa."
                )
            else:  # zw
                price = base
                note = _(
                    "Zwolniona z VAT (art.43 ust.1 pkt 24 lit.a)"
                    " — opieka nad dziećmi i młodzieżą."
                )

            rec.computed_price_per_child = round(price, 2)
            rec.vat_note = note

    def action_apply_computed_price(self):
        """Copy computed_price_per_child → price_per_child."""
        self.ensure_one()
        self.write({"price_per_child": self.computed_price_per_child})
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    # ── constrains ────────────────────────────────────────────────────────

    @api.constrains("markup_percent")
    def _check_markup(self):
        for rec in self:
            if (rec.markup_percent or 0.0) < 0:
                raise ValidationError(_("Marża musi być ≥ 0%."))

    @api.constrains("cost_advertising_total", "cost_lodging_per_day",
                    "cost_food_per_child_day", "salary_wychowawca_per_turnus",
                    "salary_kierownik_per_turnus", "salary_instructor_per_turnus",
                    "cost_insurance_per_child_day", "cost_merch_per_child",
                    "cost_stationery_per_child", "cost_operational_per_child",
                    "seats", "date_begin", "date_end")
    def _check_advertising_cap(self):
        """Advertising ≤ 20% of total cost budget (excl. advertising itself)."""
        for rec in self:
            adv = rec.cost_advertising_total or 0.0
            if adv <= 0:
                continue
            children = max(rec.seats or 1, 1)
            if rec.date_begin and rec.date_end and rec.date_end > rec.date_begin:
                delta = rec.date_end - rec.date_begin
                days = max(math.ceil(delta.total_seconds() / 86400), 1)
            else:
                days = 1
            cost_excl_adv = (
                (rec.cost_lodging_per_day or 0.0) * days * children
                + (rec.cost_food_per_child_day or 0.0) * days * children
                + (rec.cost_insurance_per_child_day or 0.0) * days * children
                + (rec.salary_wychowawca_per_turnus or 0.0)
                + (rec.salary_kierownik_per_turnus or 0.0)
                + (rec.salary_instructor_per_turnus or 0.0)
                + (rec.cost_merch_per_child or 0.0) * children
                + (rec.cost_stationery_per_child or 0.0) * children
                + (rec.cost_operational_per_child or 0.0) * children
            )
            cap = cost_excl_adv * 0.20
            if adv > cap:
                raise ValidationError(
                    _(
                        "Budżet reklamowy (%(adv).2f zł) przekracza 20%% sumy"
                        " pozostałych kosztów (max %(cap).2f zł). Zmniejsz kwotę"
                        " reklamy lub zwiększ inne koszty.",
                        adv=adv,
                        cap=cap,
                    )
                )

    @api.model
    def _default_currency(self):
        """Robust currency default: never return False (MonetaryField would crash
        in OWL). Fall back to PLN, then any active currency."""
        company = self.env.company
        if company.currency_id:
            return company.currency_id
        pln = self.env["res.currency"].search([("name", "=", "PLN")], limit=1)
        if pln:
            return pln
        return self.env["res.currency"].search([("active", "=", True)], limit=1)

    @api.model
    def _default_salary(self, param):
        raw = self.env["ir.config_parameter"].sudo().get_param(param, "0")
        try:
            return float(raw or 0)
        except ValueError:
            _logger.warning("[camp_create_wizard] Bad value %r for config param %s", raw, param)
            return 0.0

    @api.constrains("date_begin", "date_end")
    def _check_dates(self):
        for wizard in self:
            if wizard.date_begin and wizard.date_end and wizard.date_end <= wizard.date_begin:
                raise ValidationError(_("Shift end must be after the start."))

    @api.constrains("seats")
    def _check_seats(self):
        for wizard in self:
            if wizard.seats <= 0:
                raise ValidationError(_("Seats must be a positive number."))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_create_venue(self):
        """Find/create the venue res.partner for `location` (native table)."""
        self.ensure_one()
        if not self.location:
            return self.env["res.partner"]
        partner_model = self.env["res.partner"]
        venue = partner_model.search([("name", "=", self.location)], limit=1)
        return venue or partner_model.create(
            {
                "name": self.location,
                "is_company": True,
                "comment": _("Auto-created camp venue (camp.create.wizard)."),
            }
        )

    def _get_or_create_event_product(self):
        """Default event-type product for the ticket — NATIVE tables only.

        Order: (1) the stock event_sale demo/default product if present,
        (2) any existing event-type product, (3) create a fresh service
        product flagged as event (Odoo 17: detailed_type='event'; the
        legacy `event_ok=True` boolean became this selection value).
        """
        product = self.env.ref("event_sale.product_product_event", raise_if_not_found=False)
        if product and product.exists():
            return product
        product_model = self.env["product.product"]
        type_field = "detailed_type" if "detailed_type" in product_model._fields else "type"
        event_supported = type_field == "detailed_type" and any(
            key == "event" for key, _label in product_model._fields[type_field].selection
        )
        product_type = "event" if event_supported else "service"
        product = product_model.search([(type_field, "=", product_type)], limit=1)
        if product:
            return product
        return product_model.create(
            {
                "name": _TICKET_NAME,
                type_field: product_type,
                "list_price": 0.0,
            }
        )

    def _get_budget_category(self, xmlid, fallback_domain):
        """Category by data/budget_categories.xml XML id, fallback search."""
        category = self.env.ref(f"fayna_camp_portal.{xmlid}", raise_if_not_found=False)
        if category:
            return category
        return self.env["camp.budget.category"].search(fallback_domain, limit=1)

    # ------------------------------------------------------------------
    # Main action
    # ------------------------------------------------------------------

    def action_create_camp(self):
        self.ensure_one()

        # 1. event.event — the camp shift itself (R11: tickets = capacity layer).
        #    §6 ADR-13: created immediately as unpublished + pending_approval.
        #    website_published=False → not on website until organizator approves.
        event_vals = {
            "name": self.name,
            "date_begin": self.date_begin,
            "date_end": self.date_end,
            "seats_limited": True,
            "seats_max": self.seats,
            "website_published": False,
            "camp_approval_state": "pending_approval",
        }
        venue = self._get_or_create_venue()
        if venue:
            event_vals["address_id"] = venue.id
        event = self.env["event.event"].create(event_vals)

        # 2. Ticket «Udział w obozie» (event_sale layer, native table).
        #    Event is website_published=False → ticket not visible/buyable on site
        #    until organizator approves (action_approve sets website_published=True).
        product = self._get_or_create_event_product()
        self.env["event.event.ticket"].create(
            {
                "event_id": event.id,
                "name": _TICKET_NAME,
                "product_id": product.id,
                "price": self.price_per_child,
                "seats_max": self.seats,
            }
        )

        # 3. Budget via the EXISTING flow: action_open_budget() creates the
        #    camp.budget + calls _ensure_analytic() (analytic CAMP/{event}).
        event.action_open_budget()
        budget = event.camp_budget_ids[:1]
        budget.write(
            {
                "price_per_child": self.price_per_child,
                "planned_children": self.seats,
            }
        )
        self._create_budget_lines(budget)

        # 4. Teczka KO — readiness checklist (computes do the rest).
        self.env["camp.teczka.ko"].create({"event_id": event.id})

        # 5. Regulaminy: published organizer-wide templates (event_id empty)
        #    APPLY to this event by design — camp.regulamin.check_acks_for_event
        #    already matches ('event_id', '=', False) templates, so NOTHING is
        #    copied here.
        #    TODO(§6): acknowledgments are generated later, once kadra exists —
        #    call regulamin.action_generate_acks(event=event) after hiring
        #    (there is no staff at wizard time, so generating now is a no-op).

        # 6. Group skeleton — one empty group; auto-split takes over later
        #    (camp.group.action_auto_split distributes children by age).
        self.env["camp.group"].create({"name": _("Grupa 1"), "event_id": event.id})

        # 7. Structured program skeleton (ADR Фаза A §4)
        self._create_structured_skeleton(event)

        # 8. Logo → product.template.image_1920 if camp_program_id is set
        if self.logo_image and event.camp_program_id:
            event.camp_program_id.sudo().write({"image_1920": self.logo_image})

        _logger.info(
            "[camp_create_wizard] Camp shift created: event=%s seats=%s budget=%s",
            event.id,
            self.seats,
            budget.id,
        )
        return {
            "type": "ir.actions.act_window",
            "name": event.name,
            "res_model": "event.event",
            "res_id": event.id,
            "view_mode": "form",
            "target": "current",
        }

    def _create_budget_lines(self, budget):
        """Initial cost lines: nocleg + wyżywienie (per_child_day, VAT-marża
        categories) and the kierownik salary (per_camp, kadra/is_salary).

        Wychowawca salary lines are NOT created here — the auto-staffing
        engine adds one 'Wakat wychowawca #N' line per opened vacancy.
        """
        self.ensure_one()
        line_model = self.env["camp.budget.line"]
        specs = [
            (
                "budget_categ_osrodek",
                [("name", "ilike", "nocleg")],
                _("Nocleg"),
                "per_child_day",
                self.cost_lodging_per_day,
            ),
            (
                "budget_categ_wyzywienie",
                [("name", "ilike", "wyżywienie")],
                _("Wyżywienie"),
                "per_child_day",
                self.cost_food_per_child_day,
            ),
            (
                "budget_categ_kadra",
                ["|", ("is_salary", "=", True), ("name", "ilike", "kadra")],
                _("Kierownik wypoczynku (wynagrodzenie)"),
                "per_camp",
                self.salary_kierownik_per_turnus,
            ),
        ]
        for xmlid, fallback_domain, line_name, per, amount in specs:
            if not amount:
                continue  # zero inputs → no noise lines
            category = self._get_budget_category(xmlid, fallback_domain)
            if not category:
                raise UserError(
                    _(
                        "Budget category for '%(line)s' not found (XML id "
                        "%(xmlid)s missing and no name match) — check "
                        "data/budget_categories.xml.",
                        line=line_name,
                        xmlid=xmlid,
                    )
                )
            line_model.create(
                {
                    "budget_id": budget.id,
                    "category_id": category.id,
                    "name": line_name,
                    "per": per,
                    "amount": amount,
                }
            )
        return True

    # ── ADR Фаза A §4 — step navigation ───────────────────────────────────

    _STEP_ORDER = [
        "type",
        "basics",
        "logo",
        "dates",
        "accommodation",
        "frame_day",
        "program",
        "capacity",
    ]

    def action_next(self):
        self.ensure_one()
        idx = self._STEP_ORDER.index(self.step)
        if idx < len(self._STEP_ORDER) - 1:
            self.write({"step": self._STEP_ORDER[idx + 1]})
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_back(self):
        self.ensure_one()
        idx = self._STEP_ORDER.index(self.step)
        if idx > 0:
            self.write({"step": self._STEP_ORDER[idx - 1]})
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    # ── ADR Фаза A §4 — skeleton generator call ────────────────────────────

    def _create_structured_skeleton(self, event):
        """Create structured program(s) and generate skeleton days.

        Always creates the normal plan. If also_generate_rain_plan=True,
        creates a second structured record with is_rain_plan=True.
        """
        self.ensure_one()
        structured_model = self.env["camp.program.structured"]
        frame_day_vals = {
            "wake_time": self.fd_wake_time,
            "breakfast": self.fd_breakfast,
            "lunch": self.fd_lunch,
            "afternoon_rest": self.fd_afternoon_rest,
            "snack": self.fd_snack,
            "dinner": self.fd_dinner,
            "lights_out": self.fd_lights_out,
            "meal_duration": self.fd_meal_duration,
            "rest_duration": self.fd_rest_duration,
        }

        # Normal plan
        structured_normal = structured_model.create(
            dict(
                event_id=event.id,
                is_rain_plan=False,
                **frame_day_vals,
            )
        )
        structured_model._generate_skeleton(event, structured_normal)

        # Rain plan
        if self.also_generate_rain_plan:
            structured_rain = structured_model.create(
                dict(
                    event_id=event.id,
                    is_rain_plan=True,
                    **frame_day_vals,
                )
            )
            structured_model._generate_skeleton(event, structured_rain)

        return True
