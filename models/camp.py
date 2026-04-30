# Fayna CampScout — Camp & Event models
import logging
import os
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.modules.module import get_module_path

_logger = logging.getLogger(__name__)

_TIME_RE = re.compile(r"^\d{1,2}:\d{2}$")


# ---------------------------------------------------------------------------
# Lookup models
# ---------------------------------------------------------------------------


class CampCategory(models.Model):
    _name = "camp.category"
    _description = "Camp Category"
    _order = "sequence, name"

    name = fields.Char(
        translate=True,
        required=True,
        help=_("Display name of the camp category (sport, language, adventure …)."),
    )
    sequence = fields.Integer(default=10)
    icon = fields.Selection(
        selection=[
            ("sport", "Sport"),
            ("language", "Language"),
            ("creative", "Creative"),
            ("adventure", "Adventure"),
            ("technology", "Technology"),
            ("nature", "Nature"),
        ],
        default="sport",
        help=_("Icon style for this category used in website listing."),
    )
    description = fields.Text(
        translate=True,
        help=_("Short description of the category, shown on the website."),
    )
    active = fields.Boolean(default=True)


class CampActivity(models.Model):
    _name = "camp.activity"
    _description = "Camp Activity"
    _order = "name"

    name = fields.Char(
        translate=True,
        required=True,
        help=_("Name of the activity (e.g. 'Swimming', 'Archery')."),
    )
    category_id = fields.Many2one(
        "camp.category",
        string="Category",
        ondelete="set null",
        index=True,
        help=_("Group this activity belongs to."),
    )
    icon = fields.Char(
        help=_("FontAwesome class shown next to the activity (e.g. 'fa-volleyball-ball')."),
    )
    active = fields.Boolean(default=True)


class CampRoomType(models.Model):
    _name = "camp.room.type"
    _description = "Camp Room Type"
    _order = "sequence, name"

    name = fields.Char(
        translate=True,
        required=True,
        help=_("Accommodation type name (e.g. 'Dormitory', 'Tent', 'Cabin')."),
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "camp_room_type_name_uniq",
            "UNIQUE(name)",
            "Room type already exists — reuse the existing one.",
        ),
    ]


class CampFAQ(models.Model):
    _name = "camp.faq"
    _description = "Camp FAQ entry"
    _order = "product_tmpl_id, sequence, id"

    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Camp Program",
        ondelete="cascade",
        required=True,
        index=True,
        help=_("The camp program this FAQ entry belongs to."),
    )
    sequence = fields.Integer(default=10)
    question = fields.Char(
        translate=True,
        required=True,
        help=_("Short question as shown to parents on the camp page."),
    )
    answer = fields.Html(
        translate=True,
        required=True,
        sanitize=True,
        help=_("Full answer. HTML formatting is supported."),
    )


class CampScheduleEntry(models.Model):
    _name = "camp.schedule.entry"
    _description = "Camp Daily Schedule Entry"
    _order = "product_tmpl_id, sequence, time"

    product_tmpl_id = fields.Many2one(
        "product.template",
        ondelete="cascade",
        required=True,
        index=True,
        help=_("Camp program this schedule entry belongs to."),
    )
    sequence = fields.Integer(default=10)
    time = fields.Char(
        required=True,
        help=_("Start time in HH:MM format (24-hour clock), e.g. '07:00'."),
    )
    activity_a = fields.Char(
        string="Plan A — activity",
        translate=True,
        required=True,
        help=_("Activity name for a sunny day (Plan A)."),
    )
    description_a = fields.Text(
        string="Plan A — details",
        translate=True,
        help=_("Optional details / notes for Plan A activity."),
    )
    activity_b = fields.Char(
        string="Plan B — activity",
        translate=True,
        help=_("Activity name for a rainy day (Plan B). Leave empty to copy Plan A."),
    )
    description_b = fields.Text(
        string="Plan B — details",
        translate=True,
        help=_("Optional details / notes for Plan B activity."),
    )

    @api.constrains("time")
    def _check_time_format(self):
        for rec in self:
            if rec.time and not _TIME_RE.match(rec.time.strip()):
                raise ValidationError(
                    _("Time must be HH:MM (e.g. 07:00, 14:30). Got: %s") % rec.time
                )


# ---------------------------------------------------------------------------
# event.event extension — individual camp shift / zaїzd
# ---------------------------------------------------------------------------


class CampEvent(models.Model):
    _inherit = "event.event"

    camp_program_id = fields.Many2one(
        "product.template",
        string="Camp Program",
        domain=[("is_camp_program", "=", True)],
        index=True,
        help=_("The parent camp program (product.template) this shift belongs to."),
    )
    camp_shift_color = fields.Selection(
        selection=[
            ("orange", "Orange"),
            ("yellow", "Yellow"),
            ("blue", "Blue"),
            ("green", "Green"),
            ("red", "Red"),
            ("purple", "Purple"),
        ],
        string="Shift Color",
        help=_(
            "Marketing label for the shift (Orange / Yellow / …) — "
            "shown to parents instead of 'Shift I'."
        ),
    )

    # --- Dziennik zajęć (daily activity register) ----------------------------

    dziennik_ids = fields.One2many(
        "fayna.camp.dziennik",
        "event_id",
        string=_("Dzienniki zajęć"),
        help=_("Daily activity registers (dzienniki zajęć) for this camp shift."),
    )
    dziennik_count = fields.Integer(
        compute="_compute_dziennik_stats",
        store=False,
        string=_("# Dzienniki"),
        help=_("Total number of dziennik records for this shift."),
    )
    dziennik_submitted_count = fields.Integer(
        compute="_compute_dziennik_stats",
        store=False,
        string=_("# Submitted"),
        help=_("Number of submitted (signed-off) dziennik records."),
    )

    @api.depends("dziennik_ids", "dziennik_ids.state")
    def _compute_dziennik_stats(self):
        for event in self:
            event.dziennik_count = len(event.dziennik_ids)
            event.dziennik_submitted_count = len(
                event.dziennik_ids.filtered(lambda d: d.state == "submitted")
            )

    def action_open_dziennik(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Dzienniki zajęć"),
            "res_model": "fayna.camp.dziennik",
            "view_mode": "tree,form",
            "domain": [("event_id", "=", self.id)],
            "context": {"default_event_id": self.id},
        }

    # --- Kuratorium notifications -------------------------------------------

    kuratorium_notification_ids = fields.One2many(
        "camp.kuratorium.notification",
        "event_id",
        string=_("Kuratorium Notifications"),
        help=_("Zgłoszenia wypoczynku submitted to Kuratorium Oświaty for this shift."),
    )
    kuratorium_notification_count = fields.Integer(
        compute="_compute_kuratorium_count",
        store=False,
        string=_("Kuratorium"),
        help=_("Number of Kuratorium notifications for this shift."),
    )

    @api.depends("kuratorium_notification_ids")
    def _compute_kuratorium_count(self):
        for ev in self:
            ev.kuratorium_notification_count = len(ev.kuratorium_notification_ids)

    def action_open_kuratorium(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Zgłoszenia Kuratorium"),
            "res_model": "camp.kuratorium.notification",
            "domain": [("event_id", "=", self.id)],
            "view_mode": "tree,form",
            "context": {"default_event_id": self.id},
        }


# ---------------------------------------------------------------------------
# product.template extension — camp program (the shop product)
# ---------------------------------------------------------------------------


class CampProduct(models.Model):
    _inherit = "product.template"

    # --- State machine -------------------------------------------------------

    camp_status = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("published", "Published"),
            ("sold_out", "Sold Out"),
            ("archived", "Archived"),
        ],
        default="draft",
        string="Camp Status",
        tracking=True,
        copy=False,
        help=_("Lifecycle state of the camp program. " "Controls visibility on the website."),
    )

    def action_publish(self):
        for rec in self:
            if rec.camp_status not in ("draft",):
                raise UserError(_("Only draft camps can be published."))
            rec.camp_status = "published"

    def action_mark_sold_out(self):
        for rec in self:
            if rec.camp_status != "published":
                raise UserError(_("Only published camps can be marked as sold out."))
            rec.camp_status = "sold_out"

    def action_archive_camp(self):
        for rec in self:
            if rec.camp_status not in ("published", "sold_out"):
                raise UserError(_("Only published or sold out camps can be archived."))
            rec.camp_status = "archived"

    # --- Camp flag -----------------------------------------------------------

    is_camp_program = fields.Boolean(
        string="Is Camp Program",
        default=False,
        help=_(
            "Enable if this product is a children's camp program — "
            "extra fields and the camp page layout become available."
        ),
    )

    # --- Group A: Identification ---------------------------------------------

    camp_age_min = fields.Integer(
        string="Age min",
        help=_("Minimum age of participants (inclusive)."),
    )
    camp_age_max = fields.Integer(
        string="Age max",
        help=_("Maximum age of participants (inclusive)."),
    )
    camp_location = fields.Char(
        string="Camp Location",
        translate=True,
        help=_("Human-readable location name (city, region, lake name…)."),
    )
    camp_location_country = fields.Selection(
        selection=[
            ("PL", "Poland"),
            ("UA", "Ukraine"),
            ("IT", "Italy"),
            ("FR", "France"),
            ("ES", "Spain"),
            ("CH", "Switzerland"),
            ("other", "Other"),
        ],
        string="Country",
        help=_("Country where the camp takes place."),
    )
    camp_category_id = fields.Many2one(
        "camp.category",
        string="Camp Category",
        index=True,
        help=_("Category that best describes this camp program."),
    )
    camp_hiking_route = fields.Char(
        string="Hiking route",
        translate=True,
        help=_(
            "Route description if this is a hiking / travelling camp. "
            "Required on the qualification card by Polish law."
        ),
    )

    # --- Group B: Dates + shifts ---------------------------------------------

    camp_season = fields.Selection(
        selection=[
            ("spring", "Spring"),
            ("summer", "Summer"),
            ("autumn", "Autumn"),
            ("winter", "Winter"),
        ],
        string="Season",
        default="summer",
        help=_("Season when this camp program runs."),
    )
    event_ids = fields.One2many(
        "event.event",
        "camp_program_id",
        string="Shifts / Events",
    )
    camp_shift_count = fields.Integer(
        string="Shifts count",
        compute="_compute_camp_shift_count",
        store=True,
        help=_("Number of individual shifts (event.event records) linked to this program."),
    )

    @api.depends("event_ids")
    def _compute_camp_shift_count(self):
        for rec in self:
            rec.camp_shift_count = len(rec.event_ids)

    # --- Group C: Program content --------------------------------------------

    camp_concept = fields.Html(
        string="Concept",
        translate=True,
        sanitize=True,
        help=_("General idea and theme of the camp — shown in the top section of the camp page."),
    )
    camp_goals = fields.Html(
        string="Goals",
        translate=True,
        sanitize=True,
        help=_("Educational and developmental goals. Shown to parents in the description."),
    )
    camp_daily_routine = fields.Html(
        string="Daily routine (legacy HTML)",
        translate=True,
        sanitize=True,
        help=_("Free-text HTML fallback. " "Prefer the structured Plan A/B schedule below."),
    )
    schedule_ids = fields.One2many(
        "camp.schedule.entry",
        "product_tmpl_id",
        string="Daily schedule",
    )
    schedule_plan_a_label = fields.Char(
        string="Plan A label",
        translate=True,
        default="☀️ Plan A — активний день",
        help=_("Column header for sunny-day schedule (Plan A)."),
    )
    schedule_plan_b_label = fields.Char(
        string="Plan B label",
        translate=True,
        default="🌧️ Plan B — максимум драйву",
        help=_("Column header for rainy-day schedule (Plan B)."),
    )
    schedule_primary_color = fields.Char(
        string="Schedule accent color",
        default="#2A8AAA",
        help=_("Hex color for timeline dots and header accents (e.g. #2A8AAA)."),
    )
    camp_activities_ids = fields.Many2many(
        "camp.activity",
        "camp_product_activity_rel",
        "product_tmpl_id",
        "activity_id",
        string="Camp Activities",
        help=_("Activities available during this camp — shown as icons on the camp page."),
    )
    camp_highlights = fields.Html(
        string="Highlights",
        translate=True,
        sanitize=True,
        help=_(
            "Short bullet points shown at the top of the camp page "
            "— main selling points (5-10 lines)."
        ),
    )

    # --- Group D: Accommodation + meals --------------------------------------

    camp_accommodation = fields.Html(
        string="Accommodation",
        translate=True,
        sanitize=True,
        help=_("Description of sleeping arrangements and facilities."),
    )
    camp_room_type_id = fields.Many2one(
        "camp.room.type",
        string="Room type",
        ondelete="restrict",
        index=True,
        help=_("Start typing to filter existing types or create a new one."),
    )
    camp_meals_count = fields.Integer(
        string="Meals per day",
        help=_("Number of meals served each day (typically 3–5)."),
    )
    camp_meals_description = fields.Html(
        string="Meals description",
        translate=True,
        sanitize=True,
        help=_("Details about cuisine, diet options and allergens."),
    )

    # --- Group E: Safety + medical -------------------------------------------

    camp_safety_description = fields.Html(
        string="Safety",
        translate=True,
        sanitize=True,
        help=_("Safety procedures, supervision ratios, and emergency contacts."),
    )
    camp_medical_onsite = fields.Boolean(
        string="Medical on-site",
        help=_("Check if a nurse or doctor is present at the camp location."),
    )
    camp_insurance_description = fields.Html(
        string="Insurance",
        translate=True,
        sanitize=True,
        help=_("Insurance coverage details for participants."),
    )

    # --- Group F: Pricing structure ------------------------------------------

    camp_price_includes = fields.Html(
        string="Price includes",
        translate=True,
        sanitize=True,
        help=_("List of what the camp fee covers (transport, meals, accommodation…)."),
    )
    camp_price_excludes = fields.Html(
        string="Price excludes",
        translate=True,
        sanitize=True,
        help=_("List of what parents need to pay separately."),
    )
    camp_early_bird_deadline = fields.Date(
        string="Early-bird deadline",
        help=_("Date until which the early-bird discount applies."),
    )
    camp_early_bird_discount = fields.Monetary(
        string="Early-bird discount",
        currency_field="currency_id",
        help=_("Amount subtracted from the list price for early-bird registrations."),
    )
    camp_installment_available = fields.Boolean(
        string="Installment available",
        help=_("Enable to offer instalment payments for this camp."),
    )

    # --- Group G: Marketing + FAQ --------------------------------------------

    camp_tagline = fields.Char(
        string="Tagline",
        translate=True,
        help=_("Short marketing slogan shown in the hero section (max ~80 chars)."),
    )
    camp_faq_ids = fields.One2many(
        "camp.faq",
        "product_tmpl_id",
        string="FAQ",
    )
    camp_gallery_ids = fields.Many2many(
        "ir.attachment",
        "camp_product_gallery_rel",
        "product_tmpl_id",
        "attachment_id",
        string="Gallery",
        help=_("Extra photos for the camp gallery " "— in addition to the main product images."),
    )
    camp_program_pdf_id = fields.Many2one(
        "ir.attachment",
        string="Program PDF",
        help=_("PDF brochure shown as a download button on the camp page."),
    )

    # --- Computed rendered HTML (read-only preview) --------------------------

    camp_top_html = fields.Html(
        string="TOP rendered",
        compute="_compute_camp_rendered_html",
        sanitize=False,
        help=_("Preview of the top banner of the camp page " "— auto-built from the fields above."),
    )
    camp_bot_html = fields.Html(
        string="BOT rendered",
        compute="_compute_camp_rendered_html",
        sanitize=False,
        help=_(
            "Preview of the main content block of the camp page "
            "— auto-built from the fields above."
        ),
    )

    # --- Feature flag + render sync ------------------------------------------

    _CAMP_RENDER_PARAM = "fayna_camp_portal.render_mode"

    def _camp_render_mode(self):
        """Return current feature flag value ('legacy' | 'qweb')."""
        return self.env["ir.config_parameter"].sudo().get_param(self._CAMP_RENDER_PARAM, "legacy")

    def apply_qweb_render(self, force=False):
        """Copy computed camp_top_html / camp_bot_html into the core website fields
        (description_ecommerce / website_description) so website_sale pages show
        the QWeb-rendered camp layout without requiring a template xpath override.

        Called:
          - manually via the admin button on the product form
          - daily cron (when fayna_camp_portal.render_mode == 'qweb')

        Args:
            force: bypass the feature-flag check (useful for testing or manual
                   preview when the admin wants to see qweb output without
                   flipping the global flag).
        """
        mode = self._camp_render_mode()
        if not force and mode != "qweb":
            return False
        camps = self.filtered(lambda p: p.is_camp_program)
        for camp in camps:
            camp.write(
                {
                    "description_ecommerce": camp.camp_top_html or "",
                    "website_description": camp.camp_bot_html or "",
                }
            )
        _logger.info(
            "fayna_camp_portal.render_sync: mode=%s force=%s synced=%d",
            mode,
            force,
            len(camps),
        )
        return True

    # --- One-off backfill from monolith HTML ---------------------------------

    # Visible marker (HTML comment would be stripped by the Html field sanitiser).
    _BACKFILL_MARKER = (
        '<p class="alert alert-warning backfill-marker">'
        "<strong>⚠ BACKFILL:</strong> raw monolith HTML dumped below. "
        "Split into camp_concept / camp_goals / camp_daily_routine / camp_highlights "
        "through the admin form. Delete this notice when done."
        "</p>"
    )

    @api.model
    def backfill_from_monolith_html(self, directory=None):
        """Dump raw HTML from campscout_management/data/pages/camps/ into camp_concept
        for each camp-product that has no content yet. The copywriter then splits
        the content into sections (concept/goals/daily_routine/highlights/…) via the
        admin form.

        Idempotent — skips products that already have camp_concept content.
        Safe to call on install (no-op when the directory is absent).
        """
        if directory is None:
            path = get_module_path("campscout_management")
            if not path:
                _logger.info("backfill: campscout_management not installed — skip")
                return {"status": "skipped", "reason": "monolith not found"}
            directory = os.path.join(path, "data", "pages", "camps")

        if not os.path.isdir(directory):
            _logger.info("backfill: directory %s missing — skip", directory)
            return {"status": "skipped", "reason": "directory missing"}

        camps = self.search(
            [
                ("is_camp_program", "=", True),
                ("default_code", "like", "CS-%"),
                ("camp_concept", "in", [False, ""]),
            ]
        )

        touched = skipped = 0
        for camp in camps:
            slug = camp.default_code.lower()
            top_path = os.path.join(directory, f"{slug}_top.html")
            bot_path = os.path.join(directory, f"{slug}_bot.html")

            blocks = []
            for label, fpath in (("TOP", top_path), ("BOT", bot_path)):
                if not os.path.isfile(fpath):
                    continue
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
                blocks.append(
                    f"<h3>=== {label} (from {os.path.basename(fpath)}) ===</h3>\n{content}"
                )

            if not blocks:
                skipped += 1
                continue

            camp.camp_concept = self._BACKFILL_MARKER + "\n\n" + "\n\n<hr/>\n\n".join(blocks)
            touched += 1

        _logger.info("backfill: touched=%d skipped=%d of %d", touched, skipped, len(camps))
        return {"status": "done", "touched": touched, "skipped": skipped}

    def action_apply_qweb_render_forced(self):
        """Admin form button — sync render regardless of the global flag."""
        self.apply_qweb_render(force=True)
        return True

    @api.model
    def _cron_apply_qweb_render(self):
        """Daily cron — sync all camp-products when flag=qweb. No-op otherwise."""
        if self._camp_render_mode() != "qweb":
            _logger.info("fayna_camp_portal.render_sync cron: mode=legacy, skipping")
            return True
        camps = self.search([("is_camp_program", "=", True)])
        camps.apply_qweb_render()
        return True

    @api.depends(
        "is_camp_program",
        "camp_tagline",
        "camp_age_min",
        "camp_age_max",
        "camp_season",
        "camp_location",
        "camp_location_country",
        "camp_category_id",
        "camp_activities_ids",
        "camp_highlights",
        "camp_concept",
        "camp_goals",
        "camp_daily_routine",
        "schedule_ids",
        "schedule_ids.time",
        "schedule_ids.activity_a",
        "schedule_ids.description_a",
        "schedule_ids.activity_b",
        "schedule_ids.description_b",
        "schedule_plan_a_label",
        "schedule_plan_b_label",
        "schedule_primary_color",
        "camp_accommodation",
        "camp_room_type_id",
        "camp_room_type_id.name",
        "camp_meals_count",
        "camp_meals_description",
        "camp_safety_description",
        "camp_medical_onsite",
        "camp_insurance_description",
        "camp_price_includes",
        "camp_price_excludes",
        "camp_early_bird_deadline",
        "camp_early_bird_discount",
        "camp_faq_ids",
        "camp_faq_ids.question",
        "camp_faq_ids.answer",
        "camp_faq_ids.sequence",
        "camp_program_pdf_id",
        "event_ids",
        "event_ids.camp_shift_color",
        "list_price",
    )
    def _compute_camp_rendered_html(self):
        for rec in self:
            if not rec.is_camp_program:
                rec.camp_top_html = False
                rec.camp_bot_html = False
                continue
            rec.camp_top_html = self.env["ir.qweb"]._render(
                "fayna_camp_portal.camp_top", {"product": rec}
            )
            rec.camp_bot_html = self.env["ir.qweb"]._render(
                "fayna_camp_portal.camp_bot", {"product": rec}
            )

    # --- Constraints ---------------------------------------------------------

    @api.constrains("camp_age_min", "camp_age_max", "is_camp_program")
    def _check_age_range(self):
        for rec in self:
            if not rec.is_camp_program:
                continue
            if rec.camp_age_min and rec.camp_age_max and rec.camp_age_max < rec.camp_age_min:
                raise ValidationError(
                    _(
                        "Age max (%(max)s) cannot be less than age min (%(min)s).",
                        max=rec.camp_age_max,
                        min=rec.camp_age_min,
                    )
                )
