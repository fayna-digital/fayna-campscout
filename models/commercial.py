# Fayna CampScout — Commercial models (loyalty, reviews, sales, installments)
# Native Odoo extensions where a native model exists; custom models only where
# there is no Community equivalent.
#
# Architecture decisions (see fayna-digital-docs ADR):
#
# - loyalty.program / loyalty.card / res.partner  ← _inherit (native loyalty module)
#   camp.loyalty.participant remains CUSTOM — it is a per-partner tier+points
#   tracker, not a coupon card. loyalty.card = individual coupon instance; there
#   is no native "tier tracker" in Odoo Community.
#
# - camp.review  ← CUSTOM — website_rating provides rating.rating which is a
#   single integer score attached to a mail.message thread. camp.review needs
#   a full content model (title / improvement / moderation / is_anonymous /
#   state machine). No native equivalent in Community.
#
# - fayna.payment.installment  ← CUSTOM — account.payment.term is a billing
#   template (how to split invoice due dates); fayna.payment.installment is a
#   per-order schedule instance with its own state machine (pending/paid/overdue).
#   These are complementary, not duplicates.
#
# - fayna.camp.season ← CUSTOM — there is no native "camp season" concept.

import logging
import secrets
import string
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

BANDA_PREFIX = "BANDA-"
BANDA_RANDOM_LEN = 6  # 36^6 ≈ 2.18 B combos — collision probability negligible
BANDA_MAX_TRIES = 8

TIER_THRESHOLDS = [
    ("banda", 2000),
    ("platinum", 1000),
    ("gold", 500),
    ("silver", 200),
    ("bronze", 0),
]

REFERRAL_POINTS = 100  # points awarded to referrer per successful BANDA redemption

REPEAT_CUSTOMER_LOOKBACK_YEARS = 2
PAID_STATES = ("sale", "done")

# ir.config_parameter keys
_PARAM_LOYALTY_ACTIVE = "fayna_campscout.loyalty_active"
_PARAM_SALES_ACTIVE = "fayna_campscout.sales_active"
_PARAM_SUPPORT_ADMIN_EMAIL = "fayna_campscout.support_admin_email"

# loyalty.program XML IDs (loaded by data/commercial_data.xml)
BANDA_PROGRAM_XMLID = "fayna_campscout.program_banda"
BANDA_REFERRER_PROGRAM_XMLID = "fayna_campscout.program_banda_referrer"


# ──────────────────────────────────────────────────────────────────────────────
# fayna.camp.season  (CUSTOM — no native equivalent)
# ──────────────────────────────────────────────────────────────────────────────

class FaynaCampSeason(models.Model):
    """Logical grouping of camp shifts for cross-camp business rules.

    A season (Літо 2026, Зима 2026, …) is a named bucket that several
    event.event records point to via camp_season_id. Drives the
    «Подвійна порція» loyalty rule (second paid booking in the same season).
    """

    _name = "fayna.camp.season"
    _description = "Camp Season (Літо 2026, Зима 2026, …)"
    _order = "year desc, season_type"

    name = fields.Char(required=True, index=True, translate=False)
    year = fields.Integer(required=True, index=True)
    season_type = fields.Selection(
        [
            ("summer", "Summer / Літо"),
            ("winter", "Winter / Зима"),
            ("spring", "Spring / Весна"),
            ("autumn", "Autumn / Осінь"),
        ],
        required=True,
        index=True,
    )
    date_from = fields.Date()
    date_to = fields.Date()
    color = fields.Integer(default=0)
    active = fields.Boolean(default=True)

    event_ids = fields.One2many("event.event", "camp_season_id", string="Camp Shifts")
    event_count = fields.Integer(compute="_compute_event_count")

    _sql_constraints = [
        (
            "unique_year_type",
            "UNIQUE(year, season_type)",
            "A season is uniquely identified by (year, season_type).",
        )
    ]

    @api.depends("event_ids")
    def _compute_event_count(self):
        for rec in self:
            rec.event_count = len(rec.event_ids)

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(_("Season date_from must be ≤ date_to."))


# ──────────────────────────────────────────────────────────────────────────────
# event.event  ← _inherit  (add camp_season_id FK)
# ──────────────────────────────────────────────────────────────────────────────

class EventEvent(models.Model):
    _inherit = "event.event"

    camp_season_id = fields.Many2one(
        "fayna.camp.season",
        string="Camp Season",
        index=True,
        ondelete="set null",
        help=(
            "Logical season bucket — used by the «Подвійна порція» loyalty rule "
            "(second paid booking within the same season grants −100 PLN)."
        ),
    )


# ──────────────────────────────────────────────────────────────────────────────
# loyalty.program  ← _inherit  (add Fayna camp rule type)
# ──────────────────────────────────────────────────────────────────────────────

class CampLoyaltyProgram(models.Model):
    """Extend the native loyalty.program with camp-specific qualification rules.

    The stock Odoo rule engine handles point earning / reward issuance.
    fayna_rule_type adds an extra gate: the order must ALSO satisfy the
    selected Fayna rule before the native reward fires.
    """

    _inherit = "loyalty.program"

    fayna_rule_type = fields.Selection(
        [
            ("repeat_customer", "Repeat camp customer (VIP-клуб)"),
            ("double_portion", "Second booking same season (Подвійна порція)"),
            ("large_family", "Large family ≥3 children (Велика родина)"),
        ],
        string="Fayna Rule Type",
        help=(
            "Custom Fayna camp loyalty condition enforced on top of the stock "
            "Odoo rule. Leave empty for native behaviour. The order is eligible "
            "only when BOTH the stock rule passes AND the Fayna rule qualifies."
        ),
    )


# ──────────────────────────────────────────────────────────────────────────────
# res.partner  ← _inherit  (KDR, large-family flag, BANDA referral code)
# ──────────────────────────────────────────────────────────────────────────────

class ResPartner(models.Model):
    _inherit = "res.partner"

    kdr_number = fields.Char(
        string="KDR Number",
        index=True,
        copy=False,
        help=(
            "Karta Dużej Rodziny — Polish state-issued large-family card. "
            "Presence triggers the −5% loyalty discount."
        ),
    )
    is_large_family_manual = fields.Boolean(
        string="Large Family (manual)",
        help=(
            "Manager override when KDR is missing but the family qualifies "
            "(foster care, single-parent 3+, …)."
        ),
    )
    is_large_family = fields.Boolean(
        compute="_compute_is_large_family",
        store=True,
        compute_sudo=True,
        index=True,
        help="True when ANY of: KDR set / manual flag / ≥3 children in cabinet.",
    )
    banda_code = fields.Char(
        string="BANDA Code",
        index=True,
        copy=False,
        readonly=True,
        help=(
            "Personal referral code generated on first paid camp registration. "
            "Shared by parent — friend's checkout grants both −50 PLN."
        ),
    )
    banda_referred = fields.Boolean(
        string="BANDA Referred",
        default=False,
        copy=False,
        index=True,
        help=(
            "True when at least one other partner has successfully redeemed "
            "this partner's BANDA code (M.5 reciprocal reward status)."
        ),
    )

    _sql_constraints = [
        (
            "unique_banda_code",
            "UNIQUE(banda_code)",
            "BANDA code must be unique across partners.",
        )
    ]

    @api.depends("kdr_number", "is_large_family_manual", "child_ids")
    def _compute_is_large_family(self):
        for rec in self:
            rec.is_large_family = bool(
                (rec.kdr_number and rec.kdr_number.strip())
                or rec.is_large_family_manual
                or len(rec.child_ids) >= 3
            )

    @api.constrains("kdr_number")
    def _check_kdr_format(self):
        for rec in self:
            if not rec.kdr_number:
                continue
            digits = rec.kdr_number.strip()
            if not digits.isdigit() or not (10 <= len(digits) <= 25):
                raise ValidationError(
                    _("KDR number must be 10–25 digits, got: %s") % rec.kdr_number
                )

    # ── BANDA helpers ────────────────────────────────────────────────────────

    def _generate_banda_code(self):
        """Return an unused BANDA-XXXXXX token.

        Idempotent for callers — check `not partner.banda_code` first; this
        method does NOT assign the code, it only generates and returns it.
        """
        self.ensure_one()
        alphabet = string.ascii_uppercase + string.digits
        partner_model = self.sudo().env["res.partner"]
        for _attempt in range(BANDA_MAX_TRIES):
            token = "".join(secrets.choice(alphabet) for _ in range(BANDA_RANDOM_LEN))
            code = f"{BANDA_PREFIX}{token}"
            if not partner_model.search_count([("banda_code", "=", code)]):
                return code
        raise ValidationError(
            _("Unable to generate a unique BANDA code after %s tries.") % BANDA_MAX_TRIES
        )

    def action_reset_banda_code(self):
        """Generate a new BANDA referral code for this partner.

        RODO right to erasure for referral data: archives the existing BANDA
        loyalty cards and issues a fresh BANDA-XXXXXX token.
        Restricted to ERP managers via the button's ``groups`` attribute.
        """
        self.ensure_one()
        old_cards = self.env["loyalty.card"].search(
            [
                ("partner_id", "=", self.id),
                ("program_id.name", "ilike", "BANDA"),
            ]
        )
        old_cards.write({"active": False})
        new_code = self._generate_banda_code()
        self.sudo().banda_code = new_code
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("BANDA code reset"),
                "message": _("New code: %s") % new_code,
                "sticky": False,
            },
        }


# ──────────────────────────────────────────────────────────────────────────────
# camp.loyalty.participant  (CUSTOM — per-partner tier + points tracker)
#
# NOT replaced by loyalty.card: loyalty.card is a coupon instance (one card
# per discount program per partner). camp.loyalty.participant is a life-time
# tier tracker (one record per partner, accumulates cross-program points and
# drives the tier upgrade path). These are complementary, not duplicates.
# ──────────────────────────────────────────────────────────────────────────────

class CampLoyaltyParticipant(models.Model):
    """Per-partner loyalty record — tier + accumulated points + referral log."""

    _name = "camp.loyalty.participant"
    _description = "Camp Loyalty Participant"
    _rec_name = "partner_id"
    _order = "points desc, partner_id"

    partner_id = fields.Many2one(
        "res.partner",
        string="Partner",
        required=True,
        index=True,
        ondelete="cascade",
    )
    points = fields.Integer(
        string="Points",
        default=0,
        required=True,
        help="Accumulated loyalty points. BANDA referral awards +100 pts per redemption.",
    )
    tier = fields.Selection(
        [
            ("bronze", "Bronze"),
            ("silver", "Silver"),
            ("gold", "Gold"),
            ("platinum", "Platinum"),
            ("banda", "BANDA"),
        ],
        string="Tier",
        default="bronze",
        required=True,
        index=True,
    )
    camps_count = fields.Integer(
        string="Camps Attended",
        default=0,
        help="Number of confirmed camp registrations for this partner.",
    )
    discount = fields.Float(
        string="Loyalty Discount (%)",
        compute="_compute_discount",
        store=True,
        compute_sudo=True,
        help="Current tier discount rate applied automatically at checkout.",
    )
    history_ids = fields.One2many(
        "camp.loyalty.history",
        "participant_id",
        string="History",
        readonly=True,
    )
    history_count = fields.Integer(
        compute="_compute_history_count",
        string="Events",
    )

    _sql_constraints = [
        (
            "unique_partner",
            "UNIQUE(partner_id)",
            "Each partner can only have one loyalty record.",
        )
    ]

    TIER_DISCOUNT = {
        "bronze": 0.0,
        "silver": 2.0,
        "gold": 5.0,
        "platinum": 7.0,
        "banda": 10.0,
    }

    @api.depends("tier")
    def _compute_discount(self):
        for rec in self:
            rec.discount = self.TIER_DISCOUNT.get(rec.tier, 0.0)

    @api.depends("history_ids")
    def _compute_history_count(self):
        for rec in self:
            rec.history_count = len(rec.history_ids)

    # ── tier logic ───────────────────────────────────────────────────────────

    def _recalc_tier(self):
        """Recalculate and set tier from current points. Idempotent."""
        self.ensure_one()
        for tier_name, threshold in TIER_THRESHOLDS:
            if self.points >= threshold:
                if self.tier != tier_name:
                    self.tier = tier_name
                return

    # ── referral ─────────────────────────────────────────────────────────────

    def _award_referral_points(self, referred_order):
        """Award REFERRAL_POINTS to this participant for referring `referred_order`.

        Called when another partner successfully redeems this participant's
        BANDA code at checkout. Idempotent per order: checks history for an
        existing referral log entry keyed on the order.

        Side effects:
          - adds REFERRAL_POINTS to self.points
          - recalculates tier (may upgrade)
          - creates a camp.loyalty.history record (type='referral')
        """
        self.ensure_one()
        referred_order.ensure_one()

        referee_name = referred_order.partner_id.name or _("Unknown")
        description = _("Referral from %(name)s") % {"name": referee_name}

        existing = self.env["camp.loyalty.history"].search(
            [
                ("participant_id", "=", self.id),
                ("event_type", "=", "referral"),
                ("sale_order_id", "=", referred_order.id),
            ],
            limit=1,
        )
        if existing:
            return

        self.sudo().points += REFERRAL_POINTS
        self.sudo()._recalc_tier()

        self.env["camp.loyalty.history"].sudo().create(
            {
                "participant_id": self.id,
                "event_type": "referral",
                "points_delta": REFERRAL_POINTS,
                "description": description,
                "sale_order_id": referred_order.id,
            }
        )

    # ── admin actions ─────────────────────────────────────────────────────────

    def action_reset_points(self):
        """Reset points to 0 and tier to bronze (admin-only).

        Restricted to base.group_system via the button's ``groups`` attribute.
        """
        self.ensure_one()
        old_points = self.points
        old_tier = self.tier
        self.sudo().write({"points": 0, "tier": "bronze"})
        self.env["camp.loyalty.history"].sudo().create(
            {
                "participant_id": self.id,
                "event_type": "reset",
                "points_delta": -old_points,
                "description": _(
                    "Points reset by administrator (was: %(pts)d pts, tier: %(tier)s)"
                )
                % {"pts": old_points, "tier": old_tier},
            }
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Points reset"),
                "message": _("Points set to 0, tier reset to Bronze."),
                "sticky": False,
                "type": "warning",
            },
        }


# ──────────────────────────────────────────────────────────────────────────────
# camp.loyalty.history  (CUSTOM — immutable audit trail)
# ──────────────────────────────────────────────────────────────────────────────

class CampLoyaltyHistory(models.Model):
    """Immutable audit trail: each row is one point-earning / reset event."""

    _name = "camp.loyalty.history"
    _description = "Camp Loyalty History"
    _order = "create_date desc, id desc"
    _rec_name = "description"

    participant_id = fields.Many2one(
        "camp.loyalty.participant",
        string="Participant",
        required=True,
        index=True,
        ondelete="cascade",
    )
    event_type = fields.Selection(
        [
            ("referral", "BANDA Referral"),
            ("camp_attend", "Camp Attendance"),
            ("reset", "Admin Reset"),
            ("manual", "Manual Adjustment"),
        ],
        string="Event Type",
        required=True,
        index=True,
    )
    points_delta = fields.Integer(
        string="Points Change",
        default=0,
        help="Positive = points added, negative = points removed.",
    )
    description = fields.Char(string="Description", required=True)
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Related Order",
        index=True,
        ondelete="set null",
        help="The sale order that triggered this event, if applicable.",
    )


# ──────────────────────────────────────────────────────────────────────────────
# sale.order  ← _inherit  (loyalty gate + BANDA issuance + RODO consent)
# ──────────────────────────────────────────────────────────────────────────────

class SaleOrderCommercial(models.Model):
    _inherit = "sale.order"

    # ── RODO consent link (fayna_camp_sales) ─────────────────────────────────

    rodo_consent_id = fields.Many2one(
        "fayna.rodo.consent.log",
        string="RODO consent (checkout)",
        ondelete="set null",
        copy=False,
        readonly=True,
        index=True,
        help=(
            "Consent log row created at order confirmation. The parent "
            "implicitly accepts processing of personal/transactional data "
            "(art. 6(1)(b) RODO — performance of contract) by confirming "
            "the order. Recorded once per sale.order; idempotent on re-confirm."
        ),
    )

    # ── Installment fields (fayna_payment_installments) ───────────────────────

    payment_installment_ids = fields.One2many(
        "fayna.payment.installment",
        "sale_order_id",
        string="Installments",
    )
    installment_plan_id = fields.Many2one(
        "fayna.payment.installment.plan",
        string="Installment Plan",
        domain=[("active", "=", True)],
        ondelete="restrict",
    )
    installment_count = fields.Integer(
        compute="_compute_installment_count",
        store=True,
        string="# Installments",
        compute_sudo=True,
    )
    has_installments = fields.Boolean(
        compute="_compute_has_installments",
        store=False,
        string="Has Installments",
        help="True when at least one installment exists for this order.",
    )
    has_overdue_installment = fields.Boolean(
        compute="_compute_has_overdue_installment",
        store=True,
        string="Has Overdue Installment",
        compute_sudo=True,
    )

    @api.depends("payment_installment_ids")
    def _compute_installment_count(self):
        for order in self:
            order.installment_count = len(order.payment_installment_ids)

    @api.depends("payment_installment_ids")
    def _compute_has_installments(self):
        for order in self:
            order.has_installments = bool(order.payment_installment_ids)

    @api.depends("payment_installment_ids.state")
    def _compute_has_overdue_installment(self):
        for order in self:
            order.has_overdue_installment = any(
                inst.state == "overdue" for inst in order.payment_installment_ids
            )

    # ── Feature flags ─────────────────────────────────────────────────────────

    @api.model
    def _fayna_loyalty_active(self):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(_PARAM_LOYALTY_ACTIVE, "False")
            .strip()
            .lower()
            == "true"
        )

    @api.model
    def _fayna_sales_active(self):
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(_PARAM_SALES_ACTIVE, "False")
        )
        return str(param).lower() == "true"

    # ── Loyalty qualifiers ────────────────────────────────────────────────────

    def _has_camp_registration_lines(self):
        self.ensure_one()
        return any(line.event_id for line in self.order_line)

    def _qualifies_repeat_customer(self):
        """VIP-клуб: ≥1 paid prior order with a camp registration in the last 2 years."""
        self.ensure_one()
        if not self.partner_id:
            return False
        cutoff = fields.Date.today() - timedelta(days=365 * REPEAT_CUSTOMER_LOOKBACK_YEARS)
        return bool(
            self.search_count(
                [
                    ("partner_id", "=", self.partner_id.id),
                    ("state", "in", PAID_STATES),
                    ("id", "!=", self.id or 0),
                    ("date_order", ">=", cutoff),
                    ("order_line.event_id", "!=", False),
                ]
            )
        )

    def _qualifies_double_portion(self):
        """Подвійна порція: current order shares a camp_season_id with a prior paid order."""
        self.ensure_one()
        if not self.partner_id:
            return False
        current_seasons = self.order_line.mapped("event_id.camp_season_id")
        if not current_seasons:
            return False
        prior = self.search(
            [
                ("partner_id", "=", self.partner_id.id),
                ("state", "in", PAID_STATES),
                ("id", "!=", self.id or 0),
            ]
        )
        prior_seasons = prior.mapped("order_line.event_id.camp_season_id")
        return bool(set(current_seasons.ids) & set(prior_seasons.ids))

    def _qualifies_large_family(self):
        """Велика родина: KDR set / manual flag / ≥3 children."""
        self.ensure_one()
        return bool(self.partner_id and self.partner_id.is_large_family)

    # ── Loyalty native hook — augment stock Odoo rule check ──────────────────

    def _program_check_compute_points(self, programs):
        """Block reward when Fayna custom rule does not pass even if native rule does."""
        res = super()._program_check_compute_points(programs)
        if not self._fayna_loyalty_active():
            return res
        for program in programs:
            rule_type = program.fayna_rule_type
            if not rule_type:
                continue
            if res.get(program, {}).get("error"):
                # Stock check already failed — preserve that diagnostic.
                continue
            qualified = False
            err = ""
            if rule_type == "repeat_customer":
                qualified = self._qualifies_repeat_customer()
                err = _(
                    "VIP Club inactive — a paid child camp registration "
                    "in the last 2 years is required."
                )
            elif rule_type == "double_portion":
                qualified = self._qualifies_double_portion()
                err = _(
                    "Double Portion inactive — this is the first booking in the current season."
                )
            elif rule_type == "large_family":
                qualified = self._qualifies_large_family()
                err = _(
                    "Large Family not confirmed — KDR number, "
                    "manager manual flag, or 3+ children in the cabinet are required."
                )
            if not qualified:
                res[program] = {"error": err}
        return res

    # ── action_confirm ────────────────────────────────────────────────────────

    def action_confirm(self):
        res = super().action_confirm()
        # RODO consent is always recorded — legal basis is performance of
        # contract (art. 6(1)(b) RODO), independent of the feature flag.
        self._log_checkout_consent()
        if self._fayna_loyalty_active():
            for order in self:
                order._issue_banda_code_if_first()
        if self._fayna_sales_active():
            for order in self:
                order.order_line._init_camp_registrations()
        return res

    # ── RODO consent ─────────────────────────────────────────────────────────

    def _log_checkout_consent(self):
        """Record a transactional RODO consent row for the order's customer.

        Idempotent: if rodo_consent_id is already populated the call is a
        no-op. Uses fayna.rodo.consent.log.log_consent helper so any future
        cross-cutting policy (retention tagging, async dispatch) applies
        uniformly across modules.
        """
        for order in self:
            if order.rodo_consent_id:
                continue
            partner = order.partner_id
            if not partner:
                continue
            try:
                consent = (
                    self.env["fayna.rodo.consent.log"]
                    .sudo()
                    .log_consent(
                        partner_id=partner.id,
                        source="website_form",
                        purpose="transactional",
                        legal_basis="contract",
                        channel="website",
                        exact_user_response=f"sale_order_confirm:{order.name}",
                        linked_record=order,
                        email=partner.email or False,
                        phone=partner.phone or False,
                        notes=_(
                            "Consent recorded automatically at sale-order "
                            "confirmation (checkout). Legal basis: "
                            "performance of contract (art. 6(1)(b) RODO)."
                        ),
                    )
                )
            except Exception:
                # Pinned broad-except: RODO audit must not block checkout.
                # Per feedback_broad_except_silent_ui: broad except is
                # acceptable here because this is a backend audit hook and
                # a logged failure is the correct degradation (not a 500).
                _logger.exception(
                    "fayna_campscout commercial: failed to record RODO consent "
                    "for order=%s",
                    order.id,
                )
                continue
            order.write({"rodo_consent_id": consent.id})
            _logger.info(
                "fayna_campscout commercial: RODO consent=%s linked to "
                "order=%s partner=%s",
                consent.id,
                order.id,
                partner.id,
            )

    # ── BANDA auto-issuance ───────────────────────────────────────────────────

    def _issue_banda_code_if_first(self):
        """Generate the partner's BANDA referral code on their first confirmed
        camp order. Idempotent — no-op if code already exists or order has no
        camp registration lines.

        Mirrors the code as a loyalty.card so Odoo's stock reward machinery
        resolves it at checkout. If the loyalty.program record is missing
        (e.g. data not loaded yet) only the partner field is populated.
        """
        self.ensure_one()
        partner = self.partner_id
        if not partner or partner.banda_code:
            return
        if not self._has_camp_registration_lines():
            return
        code = partner._generate_banda_code()
        partner.sudo().banda_code = code
        program = self.env.ref(BANDA_PROGRAM_XMLID, raise_if_not_found=False)
        if program:
            self.env["loyalty.card"].sudo().create(
                {
                    "program_id": program.id,
                    "partner_id": partner.id,
                    "code": code,
                    "points": 1.0,
                }
            )

    # ── BANDA redemption ─────────────────────────────────────────────────────

    def _try_apply_code(self, code):
        """Block partners from redeeming their own BANDA card.

        M.5: When a BANDA code is successfully redeemed, grant the code owner
        a next-order 50 PLN gift card (program_banda_referrer).
        """
        if (
            self._fayna_loyalty_active()
            and code
            and code.upper().startswith(BANDA_PREFIX)
            and self.partner_id
            and (self.partner_id.banda_code or "").upper() == code.upper()
        ):
            return {"error": _("You cannot redeem your own BANDA code.")}

        result = super()._try_apply_code(code)

        if (
            self._fayna_loyalty_active()
            and code
            and code.upper().startswith(BANDA_PREFIX)
            and not result.get("error")
        ):
            banda_card = self.env["loyalty.card"].search(
                [("code", "=ilike", code)], limit=1
            )
            if banda_card:
                self._fayna_grant_banda_referrer_reward(banda_card)

        return result

    def _fayna_get_or_create_participant(self, partner):
        """Return or create the camp.loyalty.participant record for partner.

        Safe to call from within a try/except — returns False on unexpected error.
        """
        try:
            participant = (
                self.env["camp.loyalty.participant"]
                .sudo()
                .search([("partner_id", "=", partner.id)], limit=1)
            )
            if not participant:
                participant = (
                    self.env["camp.loyalty.participant"]
                    .sudo()
                    .create({"partner_id": partner.id})
                )
            return participant
        except Exception as exc:  # noqa: BLE001
            _logger.exception(
                "Failed to get/create loyalty participant for %s: %s", partner, exc
            )
            return False

    def _fayna_grant_banda_referrer_reward(self, banda_card):
        """Grant a next-order 50 PLN gift card to the BANDA code owner (M.5).

        Idempotency: one reward card per (referrer, program). A referrer gets
        at most one outstanding next-order coupon regardless of how many times
        their code is redeemed.

        Side-effects:
          - Sets referrer.banda_referred = True (permanent flag).
          - Posts a mail.message notification to the referrer.
          - Awards REFERRAL_POINTS to the referrer's camp.loyalty.participant.
        """
        if not self._fayna_loyalty_active():
            return

        referrer = banda_card.partner_id
        if not referrer or referrer == self.partner_id:
            return

        program = self.env.ref(BANDA_REFERRER_PROGRAM_XMLID, raise_if_not_found=False)
        if not program:
            return

        # Idempotency: skip if referrer already holds an unredeemed card.
        existing = self.env["loyalty.card"].search(
            [
                ("partner_id", "=", referrer.id),
                ("program_id", "=", program.id),
            ],
            limit=1,
        )
        if existing:
            return

        referrer.sudo().write({"banda_referred": True})

        self.env["loyalty.card"].sudo().create(
            {
                "partner_id": referrer.id,
                "program_id": program.id,
                "points": 1.0,
            }
        )

        referee_name = self.partner_id.name or _("Someone")
        referrer.sudo().message_post(
            body=_(
                "%(name)s redeemed your BANDA code! "
                "You received a −50 PLN coupon for your next order. "
                "It will be applied automatically at checkout."
            )
            % {"name": referee_name},
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )

        try:
            participant = self._fayna_get_or_create_participant(referrer)
            if participant:
                participant._award_referral_points(referred_order=self)
        except Exception as exc:  # noqa: BLE001
            _logger.exception(
                "M.5 _award_referral_points failed for referrer %s: %s", referrer, exc
            )

    # ── Installment actions ───────────────────────────────────────────────────

    def action_generate_installments(self):
        """Generate installments from the selected plan.

        Raises UserError when no plan is selected or the order has no amount.
        """
        self.ensure_one()
        if not self.installment_plan_id:
            raise UserError(
                _("Please select an installment plan before generating the schedule.")
            )
        if not self.amount_total:
            raise UserError(_("The order total must be greater than zero."))
        return self.installment_plan_id.generate_installments(self)

    def action_create_installment_schedule(self):
        """Alias kept for backward-compat. Delegates to action_generate_installments."""
        return self.action_generate_installments()


# ──────────────────────────────────────────────────────────────────────────────
# sale.order.line  ← _inherit  (auto-link camp event + promo pricing)
# ──────────────────────────────────────────────────────────────────────────────

class SaleOrderLineCommercial(models.Model):
    _inherit = "sale.order.line"

    def _resolve_camp_event(self):
        """Resolve which event.event this sale-order line should link to.

        Resolution rules (replaces bs_campscout's bs_event_id):
          1. Product must belong to a camp-program template
             (product.template.event_ids non-empty).
          2. From product_tmpl.event_ids pick the earliest upcoming event
             (date_begin > now). If none upcoming, skip.
          3. Ticket: first ticket whose product_id matches the line's product;
             fall back to first ticket on the event; skip if no tickets.

        Returns: (event, ticket) tuple or (empty recordset, empty recordset).
        """
        self.ensure_one()
        empty_event = self.env["event.event"]
        empty_ticket = self.env["event.event.ticket"]
        if not self.product_id:
            return empty_event, empty_ticket
        tmpl = self.product_id.product_tmpl_id
        events = tmpl.event_ids
        if not events:
            return empty_event, empty_ticket
        now = fields.Datetime.now()
        upcoming = events.filtered(
            lambda e: e.date_begin and e.date_begin > now
        ).sorted(key=lambda e: e.date_begin)
        if not upcoming:
            return empty_event, empty_ticket
        event = upcoming[:1]
        ticket_match = event.event_ticket_ids.filtered(
            lambda t: t.product_id == self.product_id
        )
        ticket = ticket_match[:1] if ticket_match else event.event_ticket_ids[:1]
        return event, ticket

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not self.env["sale.order"]._fayna_sales_active():
            return lines
        for line in lines:
            if not line.event_id:
                event, ticket = line._resolve_camp_event()
                if event:
                    line.event_id = event.id
                    if ticket:
                        line.event_ticket_id = ticket.id
                    _logger.info(
                        "fayna_campscout: line=%s product=%s → event=%s ticket=%s",
                        line.id,
                        line.product_id.id,
                        event.id,
                        ticket.id if ticket else None,
                    )
            if not line.discount:
                pct = line._compute_camp_promo_discount()
                if pct:
                    line.discount = pct
                    _logger.info(
                        "fayna_campscout: line=%s applied %.2f%% camp promo",
                        line.id,
                        pct,
                    )
        return lines

    def _compute_camp_promo_discount(self):
        """Return the best percentage discount this line qualifies for.

        Picks the MAX of three stacking rules (single best deal, not additive):
          - early-bird: today < camp_early_bird_deadline → camp_early_bird_discount
            converted from absolute PLN to percentage of list price.
          - sibling: parent already has a signed camp.participant on this
            camp program → camp_sibling_discount_pct.
          - loyalty: ≥2 completed registrations on this program →
            camp_loyalty_tier_pct.

        Returns float percent (0.0 when nothing applies).
        """
        self.ensure_one()
        if not self.env["sale.order"]._fayna_sales_active():
            return 0.0
        tmpl = self.product_id.product_tmpl_id
        if not tmpl.event_ids:
            return 0.0

        partner = self.order_id.partner_id
        today = fields.Date.context_today(self)
        candidates = []

        # Early-bird
        if (
            tmpl.camp_early_bird_deadline
            and today < tmpl.camp_early_bird_deadline
            and tmpl.camp_early_bird_discount
            and tmpl.list_price
        ):
            candidates.append(
                min(100.0, 100.0 * tmpl.camp_early_bird_discount / tmpl.list_price)
            )

        # Sibling
        if partner and tmpl.camp_sibling_discount_pct:
            signed_siblings = (
                self.env["camp.participant"]
                .sudo()
                .search_count(
                    [
                        ("parent_partner_id", "=", partner.id),
                        ("qualification_signed", "=", True),
                        ("registration_ids.event_id", "in", tmpl.event_ids.ids),
                    ]
                )
            )
            if signed_siblings:
                candidates.append(tmpl.camp_sibling_discount_pct)

        # Loyalty (≥2 completed seasons)
        if partner and tmpl.camp_loyalty_tier_pct:
            past_seasons = (
                self.env["event.registration"]
                .sudo()
                .search_count(
                    [
                        ("partner_id", "=", partner.id),
                        ("state", "=", "done"),
                        ("event_id", "in", tmpl.event_ids.ids),
                    ]
                )
            )
            if past_seasons >= 2:
                candidates.append(tmpl.camp_loyalty_tier_pct)

        return max(candidates) if candidates else 0.0

    def _init_camp_registrations(self):
        """Create orphan event.registration rows for each camp-program line at
        order confirmation time.

        Orphan = participant_id not yet set (parent fills the qualification
        card in the portal flow — fayna_camp_qualification Step 4b).

        Runs AFTER core event_sale's own _init_registrations. Only catches
        service products with a camp_program link that event_sale skips.

        Idempotent: skips lines that already carry the expected registration count.
        """
        if not self.env["sale.order"]._fayna_sales_active():
            return True

        registrations_vals = []
        for line in self:
            if getattr(line, "product_type", False) == "event":
                continue
            if not line.event_id:
                continue
            tmpl = line.product_id.product_tmpl_id
            if not tmpl.event_ids:
                continue
            missing = int(line.product_uom_qty) - len(line.registration_ids)
            for _ in range(max(0, missing)):
                registrations_vals.append(
                    {
                        "sale_order_line_id": line.id,
                        "sale_order_id": line.order_id.id,
                        "event_id": line.event_id.id,
                        "event_ticket_id": line.event_ticket_id.id or False,
                        "partner_id": line.order_id.partner_id.id,
                    }
                )

        if registrations_vals:
            regs = self.env["event.registration"].sudo().create(registrations_vals)
            _logger.info(
                "fayna_campscout: created %d orphan registrations on order confirm",
                len(regs),
            )
        return True


# ──────────────────────────────────────────────────────────────────────────────
# product.template  ← _inherit  (camp pricing + FOMO + review stats)
# ──────────────────────────────────────────────────────────────────────────────

class ProductTemplateCommercial(models.Model):
    _inherit = "product.template"

    # ── Camp promo pricing fields (fayna_camp_sales §3.3) ─────────────────────

    camp_sibling_discount_pct = fields.Float(
        string="Sibling discount %",
        default=0.0,
        help=(
            "Discount applied when the parent already has another camp.participant "
            "booked for any event of this camp program."
        ),
    )
    camp_loyalty_tier_pct = fields.Float(
        string="Loyalty (2+ seasons) discount %",
        default=0.0,
        help=(
            "Discount applied to partners with 2+ completed registrations on "
            "this camp program (past events, state='done')."
        ),
    )

    # ── FOMO indicators (fayna_camp_sales §3.4) ───────────────────────────────

    camp_seats_available_total = fields.Integer(
        string="Seats left across upcoming shifts",
        compute="_compute_camp_fomo",
        help=(
            "Sum of event.event.seats_available across upcoming (date_begin > now) "
            "events linked to this camp program."
        ),
    )
    camp_is_almost_full = fields.Boolean(
        string="Almost full (FOMO badge)",
        compute="_compute_camp_fomo",
        help="True when 1 ≤ total upcoming seats_available ≤ 10.",
    )
    camp_early_bird_days_left = fields.Integer(
        string="Early-bird days left",
        compute="_compute_camp_fomo",
        help="Days between today and camp_early_bird_deadline; 0 if expired or unset.",
    )
    camp_early_bird_urgent = fields.Boolean(
        string="Early-bird ending soon (FOMO badge)",
        compute="_compute_camp_fomo",
        help="True when camp_early_bird_days_left is in range 1..7.",
    )

    # ── Review stats (fayna_reviews) ─────────────────────────────────────────

    review_rating_avg = fields.Float(
        string="Average rating",
        compute="_compute_review_stats",
        store=False,
        digits=(3, 1),
    )
    review_count = fields.Integer(
        string="Published review count",
        compute="_compute_review_stats",
        store=False,
    )

    _FOMO_SEATS_THRESHOLD = 10
    _FOMO_EARLYBIRD_WINDOW_DAYS = 7

    @api.depends(
        "event_ids",
        "event_ids.date_begin",
        "event_ids.seats_available",
        "camp_early_bird_deadline",
    )
    def _compute_camp_fomo(self):
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()
        for rec in self:
            upcoming = rec.event_ids.filtered(lambda e: e.date_begin and e.date_begin > now)
            total_seats = sum(upcoming.mapped("seats_available"))
            rec.camp_seats_available_total = total_seats
            rec.camp_is_almost_full = 1 <= total_seats <= rec._FOMO_SEATS_THRESHOLD

            if rec.camp_early_bird_deadline and rec.camp_early_bird_deadline >= today:
                delta = (rec.camp_early_bird_deadline - today).days
                rec.camp_early_bird_days_left = delta
                rec.camp_early_bird_urgent = 1 <= delta <= rec._FOMO_EARLYBIRD_WINDOW_DAYS
            else:
                rec.camp_early_bird_days_left = 0
                rec.camp_early_bird_urgent = False

    @api.depends_context("lang")
    def _compute_review_stats(self):
        """Average rating and published review count per product.

        Single read_group call — avoids N+1 when a page renders many products.
        """
        if not self:
            return
        groups = (
            self.env["camp.review"]
            .sudo()
            .read_group(
                domain=[
                    ("product_template_id", "in", self.ids),
                    ("state", "=", "published"),
                    ("is_public", "=", True),
                ],
                fields=["product_template_id", "rating:avg", "rating:count"],
                groupby=["product_template_id"],
            )
        )
        stats = {
            g["product_template_id"][0]: {
                "avg": g["rating"],
                "count": g["product_template_id_count"],
            }
            for g in groups
        }
        for tmpl in self:
            data = stats.get(tmpl.id, {})
            tmpl.review_rating_avg = data.get("avg") or 0.0
            tmpl.review_count = data.get("count") or 0


# ──────────────────────────────────────────────────────────────────────────────
# camp.review  (CUSTOM — no suitable Community native model)
#
# Rationale for NOT using rating.rating:
# - rating.rating attaches a single integer score to a mail.message thread.
# - camp.review needs: title, content, improvement (organizer-only), moderation
#   state machine (draft→submitted→published/rejected), is_anonymous, author
#   display name, product_template → event linkage.
# - website_rating is in depends for the widget JS only; the model is custom.
# ──────────────────────────────────────────────────────────────────────────────

class CampReview(models.Model):
    """Parent review of a camp, tied to the stable product.template.

    product_template_id = camp brand (lives forever across yearly events).
    event_id = the specific shift where the child participated (metadata).
    Reviews stay visible on /shop/<product> as new seasons are added.
    """

    _name = "camp.review"
    _description = "Parent review of a camp"
    _inherit = ["mail.thread"]
    _order = "submitted_date desc, id desc"

    # ── Core linkage ──────────────────────────────────────────────────────────

    product_template_id = fields.Many2one(
        "product.template",
        required=True,
        index=True,
        string="Camp (product)",
        help=(
            "Stable camp product — review stays on this product's page forever, "
            "visible across yearly events and tickets."
        ),
    )
    event_id = fields.Many2one(
        "event.event",
        required=True,
        ondelete="restrict",
        string="Event (shift)",
        help="The specific shift where the reviewer's child participated.",
    )
    event_year = fields.Integer(
        compute="_compute_event_year",
        store=True,
        compute_sudo=True,
        index=True,
        string="Year",
    )
    registration_id = fields.Many2one(
        "event.registration",
        ondelete="set null",
        help="The registration that entitled the author to leave this review.",
    )
    participant_id = fields.Many2one(
        "camp.participant",
        string="Child",
        help="Which child the review is about.",
    )

    # ── Authorship ────────────────────────────────────────────────────────────

    author_partner_id = fields.Many2one(
        "res.partner",
        required=True,
        string="Author (parent)",
        default=lambda self: self.env.user.partner_id,
    )
    author_display_name = fields.Char(
        compute="_compute_author_display_name",
        store=True,
        compute_sudo=True,
        string="Displayed as",
        help="Public display form — never the parent's real name.",
    )

    # ── Content ───────────────────────────────────────────────────────────────

    rating = fields.Integer(
        required=True,
        string="Rating (1–5)",
        help="Overall rating: 1 (bad) to 5 (excellent).",
    )
    title = fields.Char(required=True, string="Title")
    content = fields.Text(required=True, string="Review")
    highlight = fields.Text(
        string="What stood out",
        help="What the child remembered best.",
    )
    improvement = fields.Text(
        string="What to improve (private)",
        help="Only visible to camp organizers — honest criticism channel.",
    )

    # ── Moderation + visibility ───────────────────────────────────────────────

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted for review"),
            ("published", "Published"),
            ("rejected", "Rejected"),
        ],
        default="draft",
        tracking=True,
        required=True,
    )
    is_public = fields.Boolean(
        default=True,
        string="Public on product page",
    )
    is_anonymous = fields.Boolean(
        default=False,
        help="Show 'Анонімно' instead of author_display_name on public pages.",
    )
    submitted_date = fields.Datetime()
    moderation_notes = fields.Text(string="Moderator notes")

    # ── Optional fields ───────────────────────────────────────────────────────

    tags = fields.Char(string="Tags (comma-sep)")
    would_return = fields.Boolean(string="Would return next year?")
    recommend = fields.Boolean(string="Would recommend to friends?")
    helpful_count = fields.Integer(string="Helpful votes")

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends("event_id.date_begin")
    def _compute_event_year(self):
        for r in self:
            r.event_year = r.event_id.date_begin.year if r.event_id.date_begin else 0

    @api.depends("author_partner_id", "participant_id", "event_year", "is_anonymous")
    def _compute_author_display_name(self):
        for r in self:
            if r.is_anonymous:
                r.author_display_name = _("Anonymously")
                continue
            child_name = r.participant_id.first_name if r.participant_id else _("child")
            year = r.event_year or ""
            r.author_display_name = _("Parent of %(child)s, %(year)s") % {
                "child": child_name,
                "year": year,
            }

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains("rating")
    def _check_rating_range(self):
        for r in self:
            if r.rating < 1 or r.rating > 5:
                raise ValidationError(_("Rating must be between 1 and 5."))

    @api.constrains("product_template_id", "event_id")
    def _check_event_belongs_to_product(self):
        """Soft guard: event_id should be a shift of product_template_id."""
        for r in self:
            event_product = r.event_id.event_ticket_ids.mapped("product_id.product_tmpl_id")
            if event_product and r.product_template_id not in event_product:
                # Soft: log rather than block (some events link via camp_program_id,
                # not tickets). A hard raise would break legacy imports.
                _logger.warning(
                    "camp.review %s: event %s may not belong to product %s",
                    r.id,
                    r.event_id.id,
                    r.product_template_id.id,
                )

    # ── State machine actions ─────────────────────────────────────────────────

    _VALID_SUBMIT_FROM = {"draft"}
    _VALID_PUBLISH_FROM = {"submitted"}
    _VALID_REJECT_FROM = {"submitted", "published"}

    def action_submit(self):
        for r in self:
            if r.state not in self._VALID_SUBMIT_FROM:
                raise UserError(_("Cannot submit a review in state '%s'.") % r.state)
            r.write({"state": "submitted", "submitted_date": fields.Datetime.now()})

    def action_publish(self):
        for r in self:
            if r.state not in self._VALID_PUBLISH_FROM:
                raise UserError(_("Cannot publish a review in state '%s'.") % r.state)
            r.state = "published"

    def action_reject(self):
        for r in self:
            if r.state not in self._VALID_REJECT_FROM:
                raise UserError(_("Cannot reject a review in state '%s'.") % r.state)
            r.state = "rejected"


# ──────────────────────────────────────────────────────────────────────────────
# fayna.payment.installment.plan  (CUSTOM — per-order payment schedule template)
#
# NOT replaced by account.payment.term:
# - account.payment.term = billing template that splits invoice due dates.
# - fayna.payment.installment.plan = a camp-specific schedule template with
#   equal / deposit+equal / custom plan types, interval_days, deposit_pct.
# ──────────────────────────────────────────────────────────────────────────────

class FaynaPaymentInstallmentPlanLine(models.Model):
    _name = "fayna.payment.installment.plan.line"
    _description = "Installment Plan Line (for custom plans)"
    _order = "sequence, id"

    plan_id = fields.Many2one(
        "fayna.payment.installment.plan",
        required=True,
        ondelete="cascade",
        string="Plan",
        index=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)
    day_offset = fields.Integer(
        string="Day Offset",
        required=True,
        default=0,
        help="Days from sale order date when this installment is due.",
    )
    percent = fields.Float(
        string="Percent (%)",
        required=True,
        digits=(5, 2),
        help="Percentage of the total order amount for this installment.",
    )

    _sql_constraints = [
        ("percent_positive", "CHECK(percent > 0)", "Percent must be positive"),
        ("day_offset_non_negative", "CHECK(day_offset >= 0)", "Day offset must be ≥ 0"),
    ]


class FaynaPaymentInstallmentPlan(models.Model):
    _name = "fayna.payment.installment.plan"
    _description = "Installment Payment Plan Template"
    _order = "name"

    name = fields.Char(
        required=True,
        string="Plan Name",
        help="e.g. '2 рівні рати', 'Депозит 25% + 2 рати'",
        translate=True,
    )
    plan_type = fields.Selection(
        [
            ("equal", "Equal Installments"),
            ("deposit_plus_equal", "Deposit + Equal Installments"),
            ("custom", "Custom"),
        ],
        required=True,
        default="equal",
        string="Plan Type",
    )
    installment_count = fields.Integer(
        required=True,
        default=2,
        string="Number of Installments",
        help="Total number of installments (2, 3 or 4). Unused for 'custom' type.",
    )
    deposit_pct = fields.Float(
        default=25.0,
        string="Deposit %",
        help=(
            "Percentage of total as first payment. "
            "Only used when plan_type='deposit_plus_equal'."
        ),
        digits=(5, 2),
    )
    interval_days = fields.Integer(
        required=True,
        default=30,
        string="Interval (days)",
        help="Days between consecutive installments. Unused for 'custom' type.",
    )
    active = fields.Boolean(default=True, string="Active")
    # backward-compat alias
    is_active = fields.Boolean(related="active", store=True, string="Is Active")
    installment_line_ids = fields.One2many(
        "fayna.payment.installment.plan.line",
        "plan_id",
        string="Custom Lines",
    )

    _sql_constraints = [
        (
            "name_unique",
            "UNIQUE(name)",
            "An installment plan with this name already exists.",
        ),
        (
            "installment_count_positive",
            "CHECK(installment_count > 0)",
            "Number of installments must be positive",
        ),
        (
            "interval_days_positive",
            "CHECK(interval_days > 0)",
            "Interval days must be positive",
        ),
        (
            "deposit_pct_range",
            "CHECK(deposit_pct >= 0 AND deposit_pct < 100)",
            "Deposit % must be between 0 and 100",
        ),
    ]

    @api.constrains("plan_type", "installment_count", "deposit_pct", "installment_line_ids")
    def _check_plan_consistency(self):
        for plan in self:
            if plan.installment_count < 1:
                raise ValidationError(_("Number of installments must be at least 1."))
            if plan.plan_type == "deposit_plus_equal":
                if plan.deposit_pct <= 0 or plan.deposit_pct >= 100:
                    raise ValidationError(
                        _("Deposit % must be between 0 and 100 for deposit+equal plans.")
                    )
                if plan.installment_count < 2:
                    raise ValidationError(
                        _("Deposit+equal plan must have at least 2 installments (deposit + 1).")
                    )
            if plan.plan_type == "custom" and not plan.installment_line_ids:
                raise ValidationError(
                    _("Custom plan must have at least one installment line.")
                )

    def generate_installments(self, sale_order):
        """Generate fayna.payment.installment records for the given sale.order.

        Clears any existing installments for this order first.
        Returns the created recordset.
        """
        self.ensure_one()
        sale_order.ensure_one()

        sale_order.payment_installment_ids.unlink()

        total_amount = sale_order.amount_total
        start_date = fields.Date.today()
        schedule = self.compute_schedule(total_amount, start_date)

        vals_list = [
            {
                "sale_order_id": sale_order.id,
                "installment_plan_id": self.id,
                "sequence": idx * 10,
                "installment_number": idx,
                "due_date": due_date,
                "amount": amount,
                "state": "pending",
            }
            for idx, (due_date, amount) in enumerate(schedule, start=1)
        ]
        return self.env["fayna.payment.installment"].create(vals_list)

    def compute_schedule(self, total_amount, start_date):
        """Return list of (due_date, amount) tuples for this plan.

        Args:
            total_amount: float — total order amount
            start_date: date — first payment date

        Returns:
            list of (date, float) tuples, length = installment_count
        """
        self.ensure_one()
        schedule = []

        if self.plan_type == "equal":
            base = total_amount / self.installment_count
            remainder = total_amount - base * self.installment_count
            for i in range(self.installment_count):
                due = start_date + timedelta(days=self.interval_days * i)
                amount = base + (remainder if i == self.installment_count - 1 else 0.0)
                schedule.append((due, round(amount, 2)))

        elif self.plan_type == "deposit_plus_equal":
            deposit_amount = round(total_amount * self.deposit_pct / 100.0, 2)
            remaining = total_amount - deposit_amount
            equal_count = self.installment_count - 1
            base = remaining / equal_count if equal_count > 0 else remaining
            remainder = remaining - base * equal_count
            schedule.append((start_date, deposit_amount))
            for i in range(equal_count):
                due = start_date + timedelta(days=self.interval_days * (i + 1))
                amount = base + (remainder if i == equal_count - 1 else 0.0)
                schedule.append((due, round(amount, 2)))

        elif self.plan_type == "custom":
            lines = self.installment_line_ids.sorted("sequence")
            total_pct = sum(ln.percent for ln in lines)
            for line in lines:
                due = start_date + timedelta(days=line.day_offset)
                amount = round(total_amount * line.percent / total_pct, 2)
                schedule.append((due, amount))
            # Correct rounding drift on last installment
            if schedule:
                diff = total_amount - sum(a for _, a in schedule)
                if diff:
                    last_due, last_amount = schedule[-1]
                    schedule[-1] = (last_due, round(last_amount + diff, 2))

        return schedule


# ──────────────────────────────────────────────────────────────────────────────
# fayna.payment.installment  (CUSTOM — per-order installment row with state machine)
#
# NOT replaced by account.payment.term lines:
# - account.payment.term line = percentage/fixed rule for invoice due-date calc.
# - fayna.payment.installment = actual instance row with its own state
#   machine (pending → paid/overdue/cancelled), payment_date, invoice link,
#   overdue cron, and email notification.
# ──────────────────────────────────────────────────────────────────────────────

class FaynaPaymentInstallment(models.Model):
    _name = "fayna.payment.installment"
    _description = "Single Payment Installment for a Sale Order"
    _order = "due_date, sequence, installment_number, id"
    _rec_name = "name"

    name = fields.Char(string="Name", compute="_compute_name", store=True)
    sale_order_id = fields.Many2one(
        "sale.order",
        required=True,
        ondelete="cascade",
        index=True,
        string="Sale Order",
    )
    installment_plan_id = fields.Many2one(
        "fayna.payment.installment.plan",
        ondelete="set null",
        string="Installment Plan",
        index=True,
    )
    # backward-compat alias used by fayna_admin_dashboard _inherit
    plan_id = fields.Many2one(
        "fayna.payment.installment.plan",
        ondelete="set null",
        string="Plan",
        index=True,
        related="installment_plan_id",
        store=True,
    )
    sequence = fields.Integer(string="Sequence", default=10)
    installment_number = fields.Integer(string="# Installment", default=1)
    due_date = fields.Date(required=True, string="Due Date", index=True)
    amount = fields.Monetary(
        required=True,
        string="Amount",
        currency_field="currency_id",
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="sale_order_id.currency_id",
        store=True,
        readonly=True,
        string="Currency",
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("paid", "Paid"),
            ("overdue", "Overdue"),
            ("cancelled", "Cancelled"),
        ],
        default="pending",
        required=True,
        string="Status",
        index=True,
    )
    payment_date = fields.Datetime(
        string="Payment Date",
        readonly=True,
        help="When this installment was actually paid.",
    )
    payment_reference = fields.Char(string="Payment Reference")
    notes = fields.Char(string="Notes")
    invoice_id = fields.Many2one(
        "account.move",
        ondelete="set null",
        string="Invoice",
        domain=[("move_type", "in", ["out_invoice", "out_refund"])],
    )

    _sql_constraints = [
        ("amount_positive", "CHECK(amount > 0)", "Amount must be positive"),
    ]

    @api.depends("sale_order_id.name", "installment_number")
    def _compute_name(self):
        for rec in self:
            order_name = rec.sale_order_id.name or ""
            rec.name = f"{order_name} / #{rec.installment_number}"

    @api.constrains("state", "payment_date")
    def _check_paid_has_date(self):
        for rec in self:
            if rec.state == "paid" and not rec.payment_date:
                raise ValidationError(
                    _("A paid installment must have a payment date (installment #%s).")
                    % rec.installment_number
                )

    def action_mark_paid(self):
        """Mark this installment as paid (pending/overdue → paid)."""
        for rec in self:
            if rec.state == "cancelled":
                raise UserError(_("Cannot mark a cancelled installment as paid."))
            rec.write({"state": "paid", "payment_date": fields.Datetime.now()})

    def action_cancel(self):
        """Cancel this installment (pending/overdue → cancelled)."""
        for rec in self:
            if rec.state == "paid":
                raise UserError(_("Cannot cancel an already paid installment."))
            rec.write({"state": "cancelled"})

    @api.model
    def _cron_mark_overdue(self):
        """Cron entry point: flip pending installments past their due_date to overdue."""
        return self._mark_overdue()

    # backward-compat alias
    @api.model
    def _cron_mark_overdue_installments(self):
        return self._mark_overdue()

    @api.model
    def _mark_overdue(self):
        """Flip pending installments past their due_date to overdue.

        Sends email notification per partner. Returns count of flipped records.
        """
        today = fields.Date.today()
        overdue_recs = self.search([("state", "=", "pending"), ("due_date", "<", today)])
        if not overdue_recs:
            return 0
        overdue_recs.write({"state": "overdue"})
        for rec in overdue_recs:
            try:
                self._notify_overdue(rec)
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "[INSTALLMENTS] failed to send overdue notification for id=%s", rec.id
                )
        _logger.info("[INSTALLMENTS] marked %d installments as overdue", len(overdue_recs))
        return len(overdue_recs)

    def _notify_overdue(self, installment):
        """Send overdue email via template; fall back to chatter message."""
        partner = installment.sale_order_id.partner_id
        if not partner or not partner.email:
            return
        template = self.env.ref(
            "fayna_campscout.email_template_overdue_installment",
            raise_if_not_found=False,
        )
        if template:
            try:
                template.send_mail(installment.id, force_send=True)
                return
            except Exception:  # noqa: BLE001
                _logger.exception(
                    "[INSTALLMENTS] template send_mail failed for id=%s, falling back",
                    installment.id,
                )
        installment.sale_order_id.message_post(
            body=_(
                "Installment #%(num)s (%(amount)s %(currency)s) was due on %(date)s "
                "and has been marked <b>overdue</b>."
            )
            % {
                "num": installment.installment_number,
                "amount": installment.amount,
                "currency": installment.currency_id.name or "",
                "date": installment.due_date,
            },
            partner_ids=[partner.id],
            message_type="email",
            subtype_xmlid="mail.mt_comment",
        )


# ──────────────────────────────────────────────────────────────────────────────
# camp.support.request  (CUSTOM — no helpdesk in Community)
# ──────────────────────────────────────────────────────────────────────────────

class CampSupportRequest(models.Model):
    """Parent feedback / cancellation requests (CAMPSCOUT_MASTER_TZ §2.7.7).

    Three request types in one model:
    - 'question'  → general support inquiry
    - 'cancel'    → formal cancellation per contract §6, with refund% calc
    - 'transfer'  → reschedule to another shift (illness exception §6.3)

    Submission triggers an admin email copy (legally required per contract §6.1)
    and creates a fayna.rodo.consent.log entry for RODO audit trail.

    Kept as a custom model because Odoo Helpdesk is Enterprise-only.
    """

    _name = "camp.support.request"
    _description = "Parent support request (question / cancel / transfer)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "submission_date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True, string="Reference")

    # ── Linkage ───────────────────────────────────────────────────────────────

    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
        string="Author",
        default=lambda self: self.env.user.partner_id,
    )
    event_id = fields.Many2one(
        "event.event",
        string="Event",
        index=True,
        ondelete="set null",
        help="Camp shift this request is related to.",
    )
    request_type = fields.Selection(
        [
            ("question", "Запитання"),
            ("cancel", "Скасування участі"),
            ("transfer", "Перенос на інший термін"),
        ],
        required=True,
        tracking=True,
    )
    registration_id = fields.Many2one(
        "event.registration",
        ondelete="set null",
        string="Registration",
        index=True,
        help="Required for cancel/transfer requests.",
    )
    participant_id = fields.Many2one(
        "camp.participant",
        related="registration_id.participant_id",
        store=True,
        readonly=True,
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        related="registration_id.sale_order_id",
        store=True,
        readonly=True,
    )

    # ── Content ───────────────────────────────────────────────────────────────

    subject = fields.Char(string="Subject", index=True, tracking=True)
    description = fields.Text(string="Description")
    category = fields.Selection(
        [
            ("billing", "Billing"),
            ("registration", "Registration"),
            ("medical", "Medical"),
            ("logistics", "Logistics"),
            ("other", "Other"),
        ],
        string="Category",
        default="other",
        index=True,
        tracking=True,
    )
    priority = fields.Selection(
        [
            ("normal", "Normal"),
            ("high", "High"),
            ("urgent", "Urgent"),
        ],
        string="Priority",
        default="normal",
        tracking=True,
        index=True,
    )
    assigned_to = fields.Many2one(
        "res.users",
        string="Assigned To",
        index=True,
        tracking=True,
    )
    response = fields.Text(
        string="Response",
        help="Admin response shown to the parent in the portal.",
        tracking=True,
    )

    # ── Cancel reason + medical cert ─────────────────────────────────────────

    reason = fields.Selection(
        [
            ("my_decision", "Моє рішення"),
            ("illness_child", "Хвороба учасника (§6.3 — перенос без штрафу)"),
            ("illness_parent", "Хвороба замовника (§6.3)"),
            ("force_majeure", "Форс-мажор"),
            ("other", "Інше"),
        ],
        tracking=True,
    )
    note = fields.Text(string="Коментар батьків")
    medical_cert = fields.Binary(
        string="Медична довідка",
        groups="fayna_campscout.group_medical_officer",
    )
    medical_cert_name = fields.Char()

    # ── Refund calculation per contract §6.2 ─────────────────────────────────

    days_to_event = fields.Integer(
        compute="_compute_days_to_event",
        store=True,
        help="Calendar days from submission to event.date_begin.",
    )
    retention_pct = fields.Integer(
        compute="_compute_refund",
        store=True,
        string="Retention %",
        help="Per §6.2: 30+ days=10%, 16–30=30%, 8–15=50%, 3–7=75%, 0–2=100%.",
    )
    refund_pct = fields.Integer(compute="_compute_refund", store=True, string="Refund %")
    estimated_refund = fields.Monetary(compute="_compute_refund", store=True)
    currency_id = fields.Many2one(
        "res.currency",
        related="sale_order_id.currency_id",
        readonly=True,
    )
    refund_due_date = fields.Date(
        compute="_compute_refund_due_date",
        store=True,
        help="Per §6.4: refund within 14 days of submission.",
    )
    moderator_response = fields.Text(string="Відповідь організатора")

    # ── Workflow ──────────────────────────────────────────────────────────────

    state = fields.Selection(
        [
            ("draft", "Чернетка"),
            ("submitted", "Надіслано"),
            ("new", "New"),
            ("in_progress", "In Progress"),
            ("under_review", "Розглядається"),
            ("approved", "Схвалено"),
            ("rejected", "Відхилено"),
            ("refund_processing", "Повернення в обробці"),
            ("resolved", "Resolved"),
            ("completed", "Завершено"),
            ("closed", "Closed"),
        ],
        default="draft",
        tracking=True,
        required=True,
    )
    submission_date = fields.Datetime(tracking=True)
    date_submitted = fields.Datetime(
        string="Date Submitted",
        related="submission_date",
        store=True,
        readonly=True,
    )
    date_resolved = fields.Datetime(string="Date Resolved", tracking=True)

    # ── Computed ──────────────────────────────────────────────────────────────

    @api.depends("request_type", "registration_id.event_id.name", "partner_id.name")
    def _compute_name(self):
        type_label = dict(self._fields["request_type"].selection)
        for r in self:
            label = type_label.get(r.request_type, "Звернення")
            ref = f"#{r.id}" if r.id else "(new)"
            r.name = f"{label} {ref}"

    @api.depends("registration_id.event_id.date_begin", "submission_date")
    def _compute_days_to_event(self):
        for r in self:
            r.days_to_event = 0
            if r.registration_id and r.registration_id.event_id.date_begin:
                ref = r.submission_date or fields.Datetime.now()
                delta = r.registration_id.event_id.date_begin - ref
                r.days_to_event = max(delta.days, 0)

    @api.depends("days_to_event", "request_type", "sale_order_id.amount_total")
    def _compute_refund(self):
        for r in self:
            if r.request_type != "cancel":
                r.retention_pct = 0
                r.refund_pct = 0
                r.estimated_refund = 0.0
                continue
            d = r.days_to_event
            if d > 30:
                ret = 10
            elif d >= 16:
                ret = 30
            elif d >= 8:
                ret = 50
            elif d >= 3:
                ret = 75
            else:
                ret = 100
            r.retention_pct = ret
            r.refund_pct = 100 - ret
            r.estimated_refund = (r.sale_order_id.amount_total or 0.0) * r.refund_pct / 100.0

    @api.depends("submission_date")
    def _compute_refund_due_date(self):
        for r in self:
            if r.submission_date:
                r.refund_due_date = (r.submission_date + timedelta(days=14)).date()
            else:
                r.refund_due_date = False

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains("request_type", "registration_id")
    def _check_registration_for_cancel(self):
        for r in self:
            if r.request_type in ("cancel", "transfer") and not r.registration_id:
                raise ValidationError(
                    _("Реєстрація обов'язкова для скасування або переносу.")
                )

    @api.constrains("request_type", "reason", "medical_cert")
    def _check_medical_cert(self):
        for r in self:
            illness = r.reason in ("illness_child", "illness_parent")
            if r.request_type == "transfer" and illness and not r.medical_cert:
                raise ValidationError(
                    _("Для переносу через хворобу медична довідка обов'язкова (§6.3).")
                )

    # ── State machine write() guard ───────────────────────────────────────────

    _STATE_TRANSITIONS = {
        "draft": {"submitted", "new"},
        "new": {"in_progress", "resolved", "closed"},
        "submitted": {"under_review", "approved", "rejected"},
        "in_progress": {"resolved", "closed"},
        "under_review": {"approved", "rejected", "refund_processing"},
        "approved": {"refund_processing", "completed"},
        "rejected": set(),
        "refund_processing": {"completed"},
        "resolved": {"closed", "in_progress"},
        "completed": set(),
        "closed": set(),
    }

    def write(self, vals):
        if "state" in vals:
            new_state = vals["state"]
            is_portal = self.env.user.has_group("base.group_portal")
            for rec in self:
                if is_portal:
                    if rec.state != "draft" or new_state != "submitted":
                        raise UserError(_("You cannot change the status of this request."))
                else:
                    allowed = self._STATE_TRANSITIONS.get(rec.state, set())
                    if new_state not in allowed:
                        raise UserError(
                            _(
                                "Cannot move support request from '%(from)s' to '%(to)s'.",
                                from_=rec.state,
                                to=new_state,
                            )
                        )
        return super().write(vals)

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_submit(self):
        for r in self:
            if r.state != "draft":
                continue
            r.write({"state": "submitted", "submission_date": fields.Datetime.now()})
            r._send_admin_email()
            r._log_rodo_consent()

    def action_start_review(self):
        for r in self:
            if r.state == "submitted":
                r.write({"state": "under_review"})

    def action_approve(self):
        for r in self:
            if r.state in ("submitted", "under_review"):
                r.write({"state": "approved"})

    def action_reject(self):
        for r in self:
            if r.state in ("submitted", "under_review"):
                r.write({"state": "rejected"})

    def action_start_refund(self):
        for r in self:
            if r.state == "approved":
                r.write({"state": "refund_processing"})

    def action_complete(self):
        for r in self:
            if r.state in ("approved", "refund_processing"):
                r.write({"state": "completed"})

    def action_start(self):
        """Move new → in_progress."""
        for r in self:
            if r.state == "new":
                r.write({"state": "in_progress"})

    def action_resolve(self):
        """Move in_progress / new → resolved; stamp date_resolved."""
        for r in self:
            if r.state in ("new", "in_progress"):
                r.write({"state": "resolved", "date_resolved": fields.Datetime.now()})
                r._send_resolved_email()

    def action_close(self):
        """Move resolved / in_progress / new → closed."""
        for r in self:
            if r.state in ("new", "in_progress", "resolved"):
                r.write({"state": "closed"})

    # ── Email helpers ─────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._send_confirmation_email()
        return records

    def _send_confirmation_email(self):
        """Send confirmation email to the parent on record creation."""
        self.ensure_one()
        if not self.partner_id.email:
            return
        template = self.env.ref(
            "fayna_campscout.support_request_confirmation",
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=False)
            return
        subject_text = self.subject or self.name or _("Support Request")
        body = _(
            "<p>Dear %(name)s,</p>"
            "<p>We have received your support request <strong>%(ref)s</strong>. "
            "Our team will get back to you shortly.</p>"
            "<p>CampScout Team</p>",
            name=self.partner_id.name,
            ref=subject_text,
        )
        self.env["mail.mail"].sudo().create(
            {
                "subject": _("Support request received: %s", subject_text),
                "body_html": body,
                "email_from": "noreply@campscout.eu",
                "email_to": self.partner_id.email,
            }
        )

    def _send_resolved_email(self):
        """Send resolved notification email to the parent."""
        self.ensure_one()
        if not self.partner_id.email:
            return
        template = self.env.ref(
            "fayna_campscout.support_request_resolved",
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=False)
            return
        subject_text = self.subject or self.name or _("Support Request")
        body = _(
            "<p>Dear %(name)s,</p>"
            "<p>Your support request <strong>%(ref)s</strong> has been resolved.</p>"
            "<p>%(response)s</p>"
            "<p>CampScout Team</p>",
            name=self.partner_id.name,
            ref=subject_text,
            response=self.response or "",
        )
        self.env["mail.mail"].sudo().create(
            {
                "subject": _("Support request resolved: %s", subject_text),
                "body_html": body,
                "email_from": "noreply@campscout.eu",
                "email_to": self.partner_id.email,
            }
        )

    def _send_admin_email(self):
        """Send formal copy to admin@campscout.eu (required by contract §6.1)."""
        self.ensure_one()
        admin_email = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(_PARAM_SUPPORT_ADMIN_EMAIL, "admin@campscout.eu")
        )
        type_label = dict(self._fields["request_type"].selection).get(self.request_type)
        reason_label = dict(self._fields["reason"].selection).get(self.reason) or "—"
        body = (
            f"<p><strong>Тип:</strong> {type_label}</p>"
            f"<p><strong>Автор:</strong> {self.partner_id.name} ({self.partner_id.email})</p>"
            f"<p><strong>Реєстрація:</strong> "
            f"{self.registration_id.event_id.name if self.registration_id else '—'}</p>"
            f"<p><strong>Дитина:</strong> "
            f"{self.participant_id.display_name if self.participant_id else '—'}</p>"
            f"<p><strong>Причина:</strong> {reason_label}</p>"
            f"<p><strong>Днів до табору:</strong> {self.days_to_event}</p>"
            f"<p><strong>Розрахунок повернення:</strong> "
            f"{self.refund_pct}% ≈ {self.estimated_refund} "
            f"{self.currency_id.symbol or ''}</p>"
            f"<p><strong>Коментар:</strong><br/>{self.note or '—'}</p>"
            f"<p><em>Ref:</em> {self.name}</p>"
        )
        self.env["mail.mail"].sudo().create(
            {
                "subject": f"[CampScout] {type_label} — {self.name}",
                "body_html": body,
                "email_from": self.partner_id.email or "noreply@campscout.eu",
                "email_to": admin_email,
                "reply_to": self.partner_id.email or admin_email,
            }
        ).send()

    def _log_rodo_consent(self):
        """Trace evidence of formal request submission per RODO."""
        self.ensure_one()
        if "fayna.rodo.consent.log" not in self.env:
            return
        self.env["fayna.rodo.consent.log"].sudo().create(
            {
                "partner_id": self.partner_id.id,
                "email": self.partner_id.email,
                "channel": "website",
                "purpose": "transactional",
                "legal_basis": "contract",
                "consent_given": True,
                "source": "support_request",
                "consent_timestamp": fields.Datetime.now(),
                "exact_user_response": (
                    f"Support request {self.name} type={self.request_type}"
                ),
                "notes": self.note or "",
            }
        )


# ──────────────────────────────────────────────────────────────────────────────
# fayna.rodo.consent.log  ← _inherit  (extend evidence_model dropdown)
# ──────────────────────────────────────────────────────────────────────────────

class FaynaRodoConsentLog(models.Model):
    _inherit = "fayna.rodo.consent.log"

    @api.model
    def _evidence_model_selection(self):
        """Extend the Reference dropdown so checkout consent rows render a
        clickable link to the originating sale.order in the audit UI."""
        return super()._evidence_model_selection() + [
            ("sale.order", "Sale order (checkout)"),
        ]
