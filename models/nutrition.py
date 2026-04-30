# Copyright 2026 Fayna Digital — Volodymyr Shevchenko
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Nutrition domain — consolidated from fayna_camp_nutrition.

Models:
  - camp.allergen         EU Regulation (EU) No 1169/2011 allergen registry
  - camp.diet.profile     Structured dietary profile (participant or partner)
  - camp.meal.plan        Daily meal plan per camp event (draft/confirmed)
  - camp.meal.plan.line   Single ingredient/product row within a meal plan
  - camp.menu.day         Full daily menu per event per date (5 meals PL MEN)
  - camp.participant.diet Kitchen-facing diet card linked to camp.participant
  - CampNutrition         Legacy daily menu model (camp.nutrition)
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# EU-14 allergen codes — Regulation (EU) No 1169/2011 Annex II
# ---------------------------------------------------------------------------

EU14_ALLERGEN_CODES = [
    ("gluten", "Gluten (cereals containing gluten)"),
    ("crustaceans", "Crustaceans and crustacean products"),
    ("eggs", "Eggs and egg products"),
    ("fish", "Fish and fish products"),
    ("peanuts", "Peanuts and peanut products"),
    ("soybeans", "Soybeans and soybean products"),
    ("milk", "Milk and dairy products (including lactose)"),
    ("nuts", "Nuts (tree nuts)"),
    ("celery", "Celery and celeriac products"),
    ("mustard", "Mustard and mustard products"),
    ("sesame", "Sesame seeds and sesame products"),
    ("so2_sulphites", "Sulphur dioxide and sulphites"),
    ("lupin", "Lupin and lupin products"),
    ("molluscs", "Molluscs and mollusc products"),
]

DIET_TYPES = [
    ("standard", "Standard"),
    ("vegetarian", "Vegetarian"),
    ("vegan", "Vegan"),
    ("gluten_free", "Gluten-free"),
    ("lactose_free", "Lactose-free"),
    ("halal", "Halal"),
    ("other", "Other"),
]


# ===========================================================================
# camp.allergen
# ===========================================================================


class CampAllergen(models.Model):
    """EU-14 allergen registry + camp-specific custom entries.

    Provides a controlled vocabulary so kitchen reports and participant
    diet cards reference standardised allergen codes rather than free text.
    """

    _name = "camp.allergen"
    _description = "Camp Allergen"
    _order = "code"
    _rec_name = "name"

    name = fields.Char(
        string=_("Allergen name"),
        required=True,
        translate=True,
        index=True,
    )
    code = fields.Char(
        string=_("Code"),
        required=True,
        size=40,
        index=True,
        help=_(
            "Short identifier used in kitchen reports (e.g. 'gluten', 'milk'). "
            "EU-14 codes are pre-seeded; custom allergens use a camp-specific code."
        ),
    )
    description = fields.Text(
        string=_("Description"),
        translate=True,
        help=_("Full EU Regulation (EU) No 1169/2011 Annex II wording or camp note."),
    )
    color = fields.Integer(
        string=_("Badge colour"),
        default=0,
        help=_(
            "Kanban/badge colour index (0–11). Used in list views to visually "
            "distinguish high-risk allergens (e.g. red=1 for peanuts)."
        ),
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "allergen_name_unique",
            "UNIQUE(name)",
            "An allergen with this name already exists.",
        ),
        (
            "allergen_code_unique",
            "UNIQUE(code)",
            "An allergen with this code already exists.",
        ),
    ]

    @api.model
    def _load_eu14_defaults(self):
        """Seed the EU-14 mandatory allergen list if not already present.

        Idempotent — safe to call repeatedly (e.g. from post-install hook).
        """
        existing_codes = set(self.sudo().search([]).mapped("code"))
        to_create = []
        for code, name in EU14_ALLERGEN_CODES:
            if code not in existing_codes:
                to_create.append({"code": code, "name": name})
        if to_create:
            self.sudo().create(to_create)
            _logger.info(
                "camp.allergen: seeded %d EU-14 allergen records",
                len(to_create),
            )


# ===========================================================================
# camp.diet.profile
# ===========================================================================


class CampDietProfile(models.Model):
    """Structured dietary profile for a camp participant or partner.

    Prefers linking to camp.participant (from fayna_camp_qualification) when
    that module is installed. Falls back to res.partner for standalone use.
    At least one of participant_id or partner_id must be set — enforced by
    Python constraint rather than SQL so the fallback remains valid.

    One profile per participant/partner — SQL unique constraints on each FK.
    """

    _name = "camp.diet.profile"
    _description = "Camp Diet Profile"
    _order = "participant_id, partner_id"
    _rec_name = "display_name"

    participant_id = fields.Many2one(
        "camp.participant",
        string=_("Participant"),
        index=True,
        ondelete="cascade",
        help=_(
            "Link to the camp participant record. "
            "Required when fayna_camp_qualification is installed."
        ),
    )
    partner_id = fields.Many2one(
        "res.partner",
        string=_("Contact"),
        index=True,
        ondelete="cascade",
        help=_(
            "Fallback link to a res.partner when camp.participant is not available. "
            "Use participant_id when possible."
        ),
    )
    diet_type = fields.Selection(
        selection=DIET_TYPES,
        string=_("Diet type"),
        index=True,
        help=_("Primary diet classification. Use 'Other' for complex combinations."),
    )
    allergen_ids = fields.Many2many(
        "camp.allergen",
        "camp_diet_profile_allergen_rel",
        "profile_id",
        "allergen_id",
        string=_("Allergens"),
        help=_("EU-14 allergens the person cannot consume."),
    )
    notes = fields.Text(
        string=_("Additional dietary notes"),
        translate=True,
        help=_(
            "Free-text notes for kitchen: severity of reactions, cross-contamination "
            "risk, accepted substitutions. Supplement the structured allergen list."
        ),
    )

    # --- Computed -----------------------------------------------------------

    display_name = fields.Char(
        string=_("Profile"),
        compute="_compute_display_name",
        store=True,
    )
    allergen_summary = fields.Char(
        string=_("Allergen summary"),
        compute="_compute_allergen_summary",
        store=False,
        help=_("Comma-separated allergen codes for quick display."),
    )

    @api.depends("participant_id", "partner_id")
    def _compute_display_name(self):
        for rec in self:
            if rec.participant_id:
                rec.display_name = rec.participant_id.display_name or str(rec.participant_id.id)
            elif rec.partner_id:
                rec.display_name = rec.partner_id.name or str(rec.partner_id.id)
            else:
                rec.display_name = _("Unknown")

    @api.depends("allergen_ids", "allergen_ids.code")
    def _compute_allergen_summary(self):
        for rec in self:
            rec.allergen_summary = ", ".join(rec.allergen_ids.mapped("code")) or ""

    # --- Constraints --------------------------------------------------------

    @api.constrains("participant_id", "partner_id")
    def _check_participant_or_partner(self):
        """At least one of participant_id or partner_id must be set."""
        for rec in self:
            if not rec.participant_id and not rec.partner_id:
                raise ValidationError(
                    _("A diet profile must be linked to a participant or a contact.")
                )

    _sql_constraints = [
        (
            "diet_profile_participant_unique",
            "EXCLUDE (participant_id WITH =) WHERE (participant_id IS NOT NULL)",
            "A diet profile for this participant already exists.",
        ),
        (
            "diet_profile_partner_unique",
            "EXCLUDE (partner_id WITH =) WHERE (partner_id IS NOT NULL)",
            "A diet profile for this contact already exists.",
        ),
    ]


# ===========================================================================
# camp.meal.plan
# ===========================================================================


class CampMealPlan(models.Model):
    """Daily meal plan attached to a camp event (one row per meal slot per day).

    Kitchen staff create plans in 'draft'; coordinator confirms to lock
    the plan before it goes to the kitchen team.
    """

    _name = "camp.meal.plan"
    _description = "Camp Meal Plan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, meal_type"
    _rec_name = "name"

    name = fields.Char(
        string=_("Plan name"),
        required=True,
        tracking=True,
        index=True,
    )
    event_id = fields.Many2one(
        "event.event",
        string=_("Camp event"),
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
    )
    date = fields.Date(
        string=_("Date"),
        required=True,
        index=True,
        tracking=True,
    )
    meal_type = fields.Selection(
        selection=[
            ("breakfast", _("Breakfast")),
            ("lunch", _("Lunch")),
            ("dinner", _("Dinner")),
            ("snack", _("Snack")),
        ],
        string=_("Meal type"),
        required=True,
        tracking=True,
        index=True,
    )
    description = fields.Text(
        string=_("Description"),
        translate=True,
    )
    notes = fields.Text(
        string=_("Kitchen notes"),
        translate=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", _("Draft")),
            ("confirmed", _("Confirmed")),
        ],
        string=_("Status"),
        default="draft",
        required=True,
        tracking=True,
        index=True,
        copy=False,
    )
    line_ids = fields.One2many(
        "camp.meal.plan.line",
        "meal_plan_id",
        string=_("Menu items"),
        copy=True,
    )

    # --- Computed -----------------------------------------------------------

    participant_count = fields.Integer(
        string=_("Participants"),
        compute="_compute_participant_count",
        store=True,
        compute_sudo=True,
        help=_(
            "Number of confirmed/open registrations for the linked camp event. "
            "Used by the kitchen to plan portions."
        ),
    )

    @api.depends("event_id", "event_id.registration_ids", "event_id.registration_ids.state")
    def _compute_participant_count(self):
        for plan in self:
            if not plan.event_id:
                plan.participant_count = 0
                continue
            plan.participant_count = len(
                plan.event_id.registration_ids.filtered(lambda r: r.state in ("open", "done"))
            )

    # --- Actions ------------------------------------------------------------

    def action_confirm(self):
        """Transition plan from draft to confirmed."""
        for plan in self:
            if plan.state != "draft":
                continue
            plan.write({"state": "confirmed"})
            plan.message_post(body=_("Meal plan confirmed."))
        return True

    def action_reset_draft(self):
        """Return a confirmed plan to draft (coordinator only)."""
        for plan in self:
            if plan.state != "confirmed":
                continue
            plan.write({"state": "draft"})
            plan.message_post(body=_("Meal plan reset to draft."))
        return True


# ===========================================================================
# camp.meal.plan.line
# ===========================================================================


class CampMealPlanLine(models.Model):
    """Single product/ingredient line within a camp.meal.plan.

    Tracks quantity, unit of measure and which EU-14 allergens the item
    contains so the kitchen report can aggregate per-participant warnings.
    """

    _name = "camp.meal.plan.line"
    _description = "Camp Meal Plan Line"
    _order = "sequence, id"

    meal_plan_id = fields.Many2one(
        "camp.meal.plan",
        string=_("Meal plan"),
        required=True,
        index=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(
        string=_("Sequence"),
        default=10,
        help=_("Order within the meal plan for display and printing."),
    )
    product_id = fields.Many2one(
        "product.product",
        string=_("Product / ingredient"),
        required=True,
        index=True,
        ondelete="restrict",
    )
    quantity = fields.Float(
        string=_("Quantity"),
        required=True,
        default=1.0,
        digits=(16, 3),
    )
    unit = fields.Char(
        string=_("Unit"),
        required=True,
        default="pcs",
        help=_("Unit of measure (kg, l, pcs, portions …). Free text for flexibility."),
    )
    allergen_ids = fields.Many2many(
        "camp.allergen",
        "camp_meal_plan_line_allergen_rel",
        "line_id",
        "allergen_id",
        string=_("Contains allergens"),
        help=_(
            "EU-14 allergens present in this ingredient. "
            "Used to generate participant-specific warnings on the kitchen report."
        ),
    )
    notes = fields.Text(
        string=_("Line notes"),
        translate=True,
    )

    # --- Computed display --------------------------------------------------

    allergen_names = fields.Char(
        string=_("Allergen summary"),
        compute="_compute_allergen_names",
        store=False,
    )

    def _compute_allergen_names(self):
        for line in self:
            line.allergen_names = ", ".join(line.allergen_ids.mapped("code")) or ""


# ===========================================================================
# camp.menu.day
# ===========================================================================


class CampMenuDay(models.Model):
    """Daily menu per camp event — one record per event+date combination.

    Stores the full day's menu as five text fields (five standard Polish
    children's camp meals per MEN nutrition guidelines). Nutritionist notes
    can flag substitutions for dietary groups.
    """

    _name = "camp.menu.day"
    _description = "Camp Daily Menu"
    _order = "menu_date desc, event_id"
    _rec_name = "display_name"

    event_id = fields.Many2one(
        "event.event",
        string=_("Camp event"),
        required=True,
        index=True,
        ondelete="cascade",
    )
    menu_date = fields.Date(
        string=_("Date"),
        required=True,
        index=True,
    )
    breakfast = fields.Text(
        string=_("Breakfast"),
        translate=True,
    )
    second_breakfast = fields.Text(
        string=_("Second breakfast / snack"),
        translate=True,
    )
    lunch = fields.Text(
        string=_("Lunch"),
        translate=True,
    )
    afternoon_snack = fields.Text(
        string=_("Afternoon snack"),
        translate=True,
    )
    dinner = fields.Text(
        string=_("Dinner"),
        translate=True,
    )
    notes = fields.Text(
        string=_("Nutritionist notes"),
        translate=True,
        help=_(
            "Substitutions, allergen warnings, or portion notes from the nutritionist. "
            "Visible to kitchen staff and camp leaders."
        ),
    )

    # --- Computed display ---------------------------------------------------

    display_name = fields.Char(
        string=_("Menu"),
        compute="_compute_display_name",
        store=True,
    )

    @api.depends("event_id", "menu_date")
    def _compute_display_name(self):
        for rec in self:
            event_name = rec.event_id.name if rec.event_id else "?"
            date_str = str(rec.menu_date) if rec.menu_date else "?"
            rec.display_name = f"{event_name} — {date_str}"

    # --- Constraints --------------------------------------------------------

    _sql_constraints = [
        (
            "menu_day_event_date_unique",
            "UNIQUE(event_id, menu_date)",
            "A daily menu for this event and date already exists.",
        ),
    ]

    @api.constrains("event_id", "menu_date")
    def _check_date_within_event(self):
        """Warn if the menu date falls outside the event's date range."""
        for rec in self:
            if not rec.event_id or not rec.menu_date:
                continue
            event = rec.event_id
            event_start = event.date_begin.date() if event.date_begin else None
            event_end = event.date_end.date() if event.date_end else None
            if event_start and rec.menu_date < event_start:
                raise ValidationError(
                    _(
                        "Menu date %(date)s is before the event start %(start)s.",
                        date=rec.menu_date,
                        start=event_start,
                    )
                )
            if event_end and rec.menu_date > event_end:
                raise ValidationError(
                    _(
                        "Menu date %(date)s is after the event end %(end)s.",
                        date=rec.menu_date,
                        end=event_end,
                    )
                )


# ===========================================================================
# camp.participant.diet
# ===========================================================================


class CampParticipantDiet(models.Model):
    """Dietary profile for a camp participant.

    Links the participant's allergen set and free-text restrictions from the
    qualification card (camp.participant.diet_restrictions / allergies) into a
    structured record the kitchen module can query per event.

    One record per participant — upsert pattern (no duplicates enforced via
    _sql_constraints). Medical officers and camp leaders can write; portal
    parent reads own child's diet via the record rule.
    """

    _name = "camp.participant.diet"
    _description = "Camp Participant Diet Profile"
    _order = "participant_id"
    _rec_name = "participant_id"

    participant_id = fields.Many2one(
        "camp.participant",
        string=_("Participant"),
        required=True,
        index=True,
        ondelete="cascade",
    )
    allergen_ids = fields.Many2many(
        "camp.allergen",
        "camp_participant_diet_allergen_rel",
        "diet_id",
        "allergen_id",
        string=_("Allergens"),
        groups="fayna_camp_portal.group_nutrition_officer",
        help=_("EU-14 allergens the participant cannot consume."),
    )
    dietary_restrictions = fields.Text(
        string=_("Dietary restrictions"),
        translate=True,
        groups="fayna_camp_portal.group_nutrition_officer",
        help=_(
            "Free-text description of dietary rules: halal, vegan, no pork, "
            "lactose-free, gluten-free, etc. Use allergen_ids for the structured "
            "EU-14 list; this field captures qualitative rules."
        ),
    )
    notes = fields.Text(
        string=_("Kitchen notes"),
        translate=True,
        groups="fayna_camp_portal.group_nutrition_officer",
        help=_(
            "Additional context for the kitchen team: severity of reactions, "
            "cross-contamination risk, alternative substitutions."
        ),
    )

    # --- Computed display --------------------------------------------------

    allergen_names = fields.Char(
        string=_("Allergen codes"),
        compute="_compute_allergen_names",
        store=False,
        help=_("Comma-separated allergen codes for display in list views."),
    )

    @api.depends("allergen_ids", "allergen_ids.code")
    def _compute_allergen_names(self):
        for diet in self:
            diet.allergen_names = ", ".join(diet.allergen_ids.mapped("code")) or ""

    # --- Constraints -------------------------------------------------------

    _sql_constraints = [
        (
            "participant_diet_unique",
            "UNIQUE(participant_id)",
            "A diet profile for this participant already exists.",
        ),
    ]

    # --- Security override -------------------------------------------------

    def read(self, fields_list=None, load="_classic_read"):
        """Enforce medical-data read restriction.

        Portal users receive their own record via ir.rule. Internal users
        need group_camp_coordinator or higher. Raises AccessError otherwise.
        """
        try:
            return super().read(fields_list=fields_list, load=load)
        except AccessError:
            raise


# ===========================================================================
# camp.nutrition  (legacy daily menu model — kept for migration compatibility)
# ===========================================================================


class CampNutrition(models.Model):
    """Legacy daily menu record for a camp shift.

    Tracks breakfast/lunch/dinner/snacks along with special dietary requirements
    per date. One record = one full day of menus for one shift.

    NOTE: New code should use camp.menu.day + camp.meal.plan instead.
    This model is retained for data-migration compatibility with
    bs_campscout_addon records.
    """

    _name = "camp.nutrition"
    _description = "Camp daily menu"
    _inherit = ["mail.thread"]
    _order = "menu_date desc"

    # ── Core ───────────────────────────────────────────────────────────────
    event_id = fields.Many2one(
        "event.event",
        string=_("Camp shift"),
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    menu_date = fields.Date(
        string=_("Date"),
        required=True,
        tracking=True,
    )

    # ── Meals ──────────────────────────────────────────────────────────────
    breakfast = fields.Text(
        string=_("Breakfast (Śniadanie)"),
        help=_("Menu items for breakfast"),
    )
    lunch = fields.Text(
        string=_("Lunch (Obiad)"),
        help=_("Menu items for lunch / main meal"),
    )
    dinner = fields.Text(
        string=_("Dinner (Kolacja)"),
        help=_("Menu items for dinner"),
    )
    snacks = fields.Text(
        string=_("Snacks (Podwieczorek)"),
        help=_("Afternoon snack / additional meals"),
    )

    # ── Special diets ──────────────────────────────────────────────────────
    vegetarian_count = fields.Integer(
        string=_("Vegetarian"),
        default=0,
        help=_("Number of participants requiring vegetarian meals"),
    )
    vegan_count = fields.Integer(
        string=_("Vegan"),
        default=0,
        help=_("Number of participants requiring vegan meals"),
    )
    gluten_free_count = fields.Integer(
        string=_("Gluten-free"),
        default=0,
        help=_("Number of participants requiring gluten-free meals"),
    )
    lactose_free_count = fields.Integer(
        string=_("Lactose-free"),
        default=0,
        help=_("Number of participants requiring lactose-free meals"),
    )
    allergy_notes = fields.Text(
        string=_("Inne alergie i diety specjalne"),
        help=_("Other allergies and special diets (free text)"),
    )

    # ── State ──────────────────────────────────────────────────────────────
    state = fields.Selection(
        [
            ("draft", "Szkic"),
            ("confirmed", "Zatwierdzone"),
        ],
        string=_("Status"),
        default="draft",
        required=True,
        tracking=True,
    )

    # ── Meta ───────────────────────────────────────────────────────────────
    prepared_by = fields.Many2one(
        "res.users",
        string=_("Prepared by"),
        index=True,
        default=lambda self: self.env.user,
    )
    notes = fields.Text(string=_("Internal notes"))

    # ── Constraints ────────────────────────────────────────────────────────
    _sql_constraints = [
        (
            "event_date_uniq",
            "UNIQUE(event_id, menu_date)",
            "A daily menu already exists for this shift and date.",
        ),
    ]

    @api.constrains("vegetarian_count", "vegan_count", "gluten_free_count", "lactose_free_count")
    def _check_diet_counts_non_negative(self):
        for rec in self:
            for fname in (
                "vegetarian_count",
                "vegan_count",
                "gluten_free_count",
                "lactose_free_count",
            ):
                if rec[fname] < 0:
                    raise UserError(_("Diet count fields cannot be negative."))

    # ── Actions ────────────────────────────────────────────────────────────
    def action_confirm(self):
        """Confirm (approve) the daily menu."""
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Menu '%(date)s' is already confirmed.", date=rec.menu_date))
            rec.write({"state": "confirmed"})
        return True

    def action_reset_to_draft(self):
        """Reset a confirmed menu back to draft for editing."""
        for rec in self:
            rec.write({"state": "draft"})
        return True
