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

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

_TICKET_NAME = "Udział w obozie"

_SALARY_WYCHOWAWCA_PARAM = "fayna_camp_portal.salary_wychowawca_default"
_SALARY_KIEROWNIK_PARAM = "fayna_camp_portal.salary_kierownik_default"


class CampCreateWizard(models.TransientModel):
    _name = "camp.create.wizard"
    _description = "Майстер «Новий табір» (event + квиток + бюджет + teczka + групи)"

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
        default=lambda self: self.env.company.currency_id,
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
        event_vals = {
            "name": self.name,
            "date_begin": self.date_begin,
            "date_end": self.date_end,
            "seats_limited": True,
            "seats_max": self.seats,
        }
        venue = self._get_or_create_venue()
        if venue:
            event_vals["address_id"] = venue.id
        event = self.env["event.event"].create(event_vals)

        # 2. Ticket «Udział w obozie» (event_sale layer, native table).
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
