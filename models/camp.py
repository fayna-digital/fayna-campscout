# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
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
    # F-WIZ-7: high-risk activities (ski, water, …) require licensed instructor
    # + mandatory insurance before the camp shift can be approved.
    is_high_risk = fields.Boolean(
        string="High-risk activity",
        default=False,
        index=True,
        help=_(
            "High-risk activities (e.g. skiing, water sports) require a licensed "
            "instructor and mandatory insurance before the camp is approved (F-WIZ-7)."
        ),
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
    # R6.1: the wizard's step-1 «Typ obozu» declaration lands HERE (before,
    # the chosen value was silently dropped) and prefills the Zgłoszenie
    # Wypoczynku (camp.kuratorium.notification) via its event onchange.
    vacation_form = fields.Selection(
        [
            ("kolonia", "Kolonia"),
            ("oboz", "Obóz"),
            ("biwak", "Biwak"),
            ("zimowisko", "Zimowisko"),
            ("polkolonia", "Półkolonia"),
            ("zielona_szkola", "Zielona szkoła"),
            ("inne", "Inne"),
        ],
        string=_("Forma wypoczynku"),
        help=_("Formal MEN form of leisure declared when the camp was created."),
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

    # --- F-WIZ-7: high-risk camps (ski / water → licensed instructor + insurance)
    is_high_risk = fields.Boolean(
        string="High-risk camp",
        compute="_compute_is_high_risk",
        store=True,
        index=True,
        help=_(
            "True when the linked camp program includes a high-risk activity "
            "(ski, water, …). Such camps require a licensed instructor and "
            "mandatory insurance before approval (F-WIZ-7)."
        ),
    )
    insurance_required = fields.Boolean(
        string="Insurance required",
        compute="_compute_is_high_risk",
        store=True,
        help=_(
            "Mandatory insurance attachment is required for high-risk camps "
            "(F-WIZ-7). Mirrors is_high_risk for clarity in forms."
        ),
    )
    insurance_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Insurance policy",
        ondelete="restrict",
        copy=False,
        help=_(
            "Uploaded insurance policy covering the high-risk activity. "
            "Required before a high-risk camp can be approved (F-WIZ-7)."
        ),
    )

    # --- Structured program (ADR Фаза A §1) ----------------------------------

    structured_program_ids = fields.One2many(
        "camp.program.structured",
        "event_id",
        string=_("Structured programs"),
        help=_("Day-by-day structured programs (normal + rain plan) for this shift."),
    )

    # --- Camp groups (reverse of camp.group.event_id) — needed for record rules
    camp_group_ids = fields.One2many(
        "camp.group",
        "event_id",
        string=_("Camp groups"),
        help=_("Participant groups for this shift (used in record rules for wychowawca access)."),
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

    # --- Approval workflow (ADR-13, TZ §6) ----------------------------------
    # State lives on native event.event — no mirror model.

    camp_approval_state = fields.Selection(
        selection=[
            ("draft", "Чернетка"),
            ("pending_approval", "На погодженні"),
            ("approved", "Погоджено"),
            ("rejected", "Відхилено"),
        ],
        string="Стан погодження",
        default="draft",
        tracking=True,
        copy=False,
        index=True,
        help=_(
            "Lifecycle approval state for this camp shift. "
            "draft → pending_approval (kierownik submits) → approved/rejected (organizator)."
        ),
    )
    approved_by_id = fields.Many2one(
        "res.users",
        string="Погоджено користувачем",
        readonly=True,
        copy=False,
        tracking=True,
    )
    approved_date = fields.Datetime(
        string="Дата погодження",
        readonly=True,
        copy=False,
    )
    rejection_reason = fields.Text(
        string="Причина відхилення",
        copy=False,
        help=_("Mandatory when rejecting a pending camp shift."),
    )

    def _post_note(self, body):
        """Post an internal chatter note resiliently — a mail/email-config
        failure must NEVER block the approval workflow (TZ §0b reliability)."""
        try:
            self.message_post(
                body=body,
                message_type="notification",
                subtype_xmlid="mail.mt_note",
            )
        except Exception:  # noqa: BLE001
            _logger.warning(
                "fayna_camp_portal: chatter note skipped for event=%s (non-blocking)",
                self.id,
            )

    # --- F-WIZ-7: high-risk detection + instructor vacancy -------------------

    @api.depends("camp_program_id", "camp_program_id.camp_activities_ids.is_high_risk")
    def _compute_is_high_risk(self):
        """A camp is high-risk when any linked activity is flagged high-risk
        (ski, water, …). Also drives insurance_required (F-WIZ-7)."""
        for event in self:
            high_risk = bool(
                event.camp_program_id
                and event.camp_program_id.camp_activities_ids.filtered(lambda a: a.is_high_risk)
            )
            event.is_high_risk = high_risk
            event.insurance_required = high_risk

    def _ensure_high_risk_vacancy(self):
        """Auto-create an instructor vacancy for a high-risk camp (F-WIZ-7).

        Idempotent: does nothing if an open/candidate/hired instructor vacancy
        already exists for this event. Never raises — a vacancy-creation failure
        must not silently break approval (it is re-checked at approve time).
        """
        self.ensure_one()
        if not self.is_high_risk:
            return
        try:
            existing = self.staff_vacancy_ids.filtered(
                lambda v: (v.role == "instruktor" and v.state in ("open", "candidate", "hired"))
            )
            if existing:
                return
            self.env["camp.staff.vacancy"].sudo().create(
                {
                    "event_id": self.id,
                    "role": "instruktor",
                    "name": _("Wakat instruktor (high-risk)"),
                    "created_reason": "F-WIZ-7 high-risk camp",
                }
            )
            self._post_note(
                _(
                    "High-risk табір: створено вакансію інструктора з обов'язковою "
                    "ліцензією та страхуванням (F-WIZ-7)."
                )
            )
        except Exception:  # noqa: BLE001
            _logger.exception(
                "fayna_camp_portal: failed to auto-create instructor vacancy for event=%s",
                self.id,
            )

    def _check_high_risk_approval(self):
        """Block approval of a high-risk camp lacking insurance or a licensed
        instructor vacancy (F-WIZ-7). Returns a list of blocking reasons."""
        self.ensure_one()
        if not self.is_high_risk:
            return []
        problems = []
        if not self.insurance_attachment_id:
            problems.append(
                _("High-risk табір потребує завантаженого страхового полісу (insurance).")
            )
        instructor_vacancy = self.staff_vacancy_ids.filtered(
            lambda v: (v.role == "instruktor" and v.state in ("open", "candidate", "hired"))
        )
        if not instructor_vacancy:
            problems.append(_("High-risk табір потребує вакансії ліцензованого інструктора."))
        return problems

    def action_submit_for_approval(self):
        """Kierownik submits the shift to organizator for approval.
        Event stays unpublished (website_published=False, sale_ok=False on ticket).
        """
        self.ensure_one()
        if self.camp_approval_state != "draft":
            raise UserError(
                _("Тільки чернетку можна надіслати на погодження (поточний стан: %s).")
                % self.camp_approval_state
            )
        # F-WIZ-7: ensure a licensed-instructor vacancy exists for high-risk camps.
        self._ensure_high_risk_vacancy()
        self.sudo().write({"camp_approval_state": "pending_approval"})
        self._post_note(_("Табір надіслано на погодження організатора."))

    def action_approve(self):
        """Organizator approves the shift → publish event + ticket products."""
        self.ensure_one()
        if not self.env.user.has_group("fayna_camp_portal.group_camp_organizator"):
            raise UserError(_("Тільки Organizator може погоджувати табори."))
        if self.camp_approval_state == "approved":
            raise UserError(_("Цей табір вже погоджено."))
        if self.camp_approval_state != "pending_approval":
            raise UserError(
                _("Погодити можна лише табір зі статусом «На погодженні» (поточний: %s).")
                % self.camp_approval_state
            )
        # F-WIZ-7: block approval of a high-risk camp missing insurance or a
        # licensed-instructor vacancy.
        high_risk_problems = self._check_high_risk_approval()
        if high_risk_problems:
            raise UserError(
                _("High-risk табір не можна погодити: %s") % ("; ".join(high_risk_problems))
            )
        self.sudo().write(
            {
                "camp_approval_state": "approved",
                "approved_by_id": self.env.uid,
                "approved_date": fields.Datetime.now(),
                "website_published": True,
            }
        )
        # Publish linked camp program product if set (website_sale)
        if self.camp_program_id:
            self.camp_program_id.sudo().write({"website_published": True, "sale_ok": True})
        # F-generator: populate product card from structured program data (TZ §8)
        try:
            self._generate_product_card()
        except Exception:  # noqa: BLE001
            # Graceful skip: card generation must never block approval/publish.
            # Failure is logged; operator can re-trigger manually.
            _logger.exception(
                "fayna_camp_portal: _generate_product_card failed for event=%s — "
                "approval continues, card must be filled manually.",
                self.id,
            )
        self._post_note(_("Табір погоджено та опубліковано організатором %s.") % self.env.user.name)

    # F-GENERATOR (TZ §8) ─────────────────────────────────────────────────────

    def _generate_product_card(self):
        """Populate the linked product.template (camp program card) from this
        event's structured program data.

        Mapping (TZ §8 F-generator):
          structured_program_ids (Plan A, non-rain) → camp_daily_routine  (Html)
          activity_line_ids category=activity       → camp_activities_ids (m2m)
          activity_line_ids category=activity       → camp_highlights      (Html)
          budget_id.price_per_child                 → list_price           (native)

        Rules:
          - Only Plan A (is_rain_plan=False), published preferred, first found.
          - Idempotent: skips each target field if already non-empty (operator
            content is never overwritten). Pass force=True to override.
          - Graceful: missing budget / no structured program → skip that field,
            log at INFO level. Never raises.
          - Never blocks approval (caller wraps in try/except BLE001).
        """
        self.ensure_one()
        product = self.camp_program_id
        if not product:
            _logger.info(
                "fayna_camp_portal._generate_product_card: event=%s has no camp_program_id — skip.",
                self.id,
            )
            return

        vals = {}

        # ── 1. Structured program days → camp_daily_routine (Html) ─────────
        if not product.camp_daily_routine:
            routine_html = self._build_daily_routine_html()
            if routine_html:
                vals["camp_daily_routine"] = routine_html

        # ── 2. Activity lines → camp_activities_ids (m2m existing records) ─
        if not product.camp_activities_ids:
            activity_ids = self._collect_activity_ids()
            if activity_ids:
                vals["camp_activities_ids"] = [(6, 0, activity_ids)]

        # ── 3. Activity lines → camp_highlights (Html bullet points) ───────
        if not product.camp_highlights:
            highlights_html = self._build_highlights_html()
            if highlights_html:
                vals["camp_highlights"] = highlights_html

        # ── 4. Budget price_per_child → list_price ──────────────────────────
        if not product.list_price:
            price = self._get_price_per_child()
            if price:
                vals["list_price"] = price

        if vals:
            product.sudo().write(vals)
            _logger.info(
                "fayna_camp_portal._generate_product_card: event=%s product=%s updated fields=%s",
                self.id,
                product.id,
                list(vals.keys()),
            )
        else:
            _logger.info(
                "fayna_camp_portal._generate_product_card: event=%s product=%s "
                "— all target fields already populated, nothing to update.",
                self.id,
                product.id,
            )

    def _get_plan_a_program(self):
        """Return the first Plan A (non-rain) structured program for this event.

        Prefers published records; falls back to any draft if none published.
        Returns empty recordset if none found.
        """
        programs = self.structured_program_ids.filtered(lambda p: not p.is_rain_plan)
        published = programs.filtered(lambda p: p.state == "published")
        return published[:1] if published else programs[:1]

    @staticmethod
    def _float_to_hhmm(value):
        """Convert float hour (e.g. 9.5) to 'HH:MM' string (e.g. '09:30')."""
        hours = int(value)
        minutes = round((value - hours) * 60)
        return f"{hours:02d}:{minutes:02d}"

    def _build_daily_routine_html(self):
        """Build Html for camp_daily_routine from structured program days.

        Format: one <h4> per day, <ul> of time-boxed activity slots.
        Only non-sleep/free lines are shown (meals, rest, activities).
        Returns empty string if no structured program or no days.
        """
        program = self._get_plan_a_program()
        if not program or not program.day_ids:
            return ""

        # Rамковий день header (meal/rest anchor times from program)
        ramowy_parts = []
        anchor_map = [
            ("Pobudka", program.wake_time),
            ("Śniadanie", program.breakfast),
            ("Obiad", program.lunch),
            ("Cisza poobiednia", program.afternoon_rest),
            ("Podwieczorek", program.snack),
            ("Kolacja", program.dinner),
            ("Cisza nocna", program.lights_out),
        ]
        for label, t in anchor_map:
            ramowy_parts.append(f"<li><strong>{self._float_to_hhmm(t)}</strong> — {label}</li>")
        ramowy_html = "<h4>Ramowy dzień obozu</h4><ul>" + "".join(ramowy_parts) + "</ul>"

        # Per-day detail (from activity lines, skip sleep/free)
        day_blocks = []
        for day in program.day_ids.sorted("date"):
            lines = day.activity_line_ids.filtered(
                lambda ln: ln.category not in ("sleep", "free")
            ).sorted("time_from")
            if not lines:
                continue
            items = []
            for line in lines:
                time_str = self._float_to_hhmm(line.time_from)
                items.append(f"<li><strong>{time_str}</strong> — {line.title}</li>")
            day_label = day.display_name or str(day.date)
            day_blocks.append(f"<h4>{day_label}</h4><ul>" + "".join(items) + "</ul>")

        if not day_blocks:
            # No per-day detail available — return ramowy only
            return ramowy_html

        return ramowy_html + "\n" + "\n".join(day_blocks)

    def _collect_activity_ids(self):
        """Return list of camp.activity IDs matched by name from activity lines.

        Only matches EXISTING camp.activity records by case-insensitive name.
        Does NOT create new records (sellable-ready: no org-specific data).
        Source: Plan A lines with category='activity', non-skeleton titles.
        """
        program = self._get_plan_a_program()
        if not program:
            return []

        activity_lines = program.day_ids.mapped("activity_line_ids").filtered(
            lambda ln: (
                ln.category == "activity" and ln.title and ln.title != "Czas wolny — do wypełnienia"
            )
        )
        names = list({line.title.strip() for line in activity_lines if line.title.strip()})
        if not names:
            return []

        matched = self.env["camp.activity"].sudo().search([("name", "in", names)])
        if not matched:
            # Try case-insensitive fallback (ilike search per name)
            matched_ids = []
            for name in names:
                rec = self.env["camp.activity"].sudo().search([("name", "=ilike", name)], limit=1)
                if rec:
                    matched_ids.append(rec.id)
            return matched_ids

        return matched.ids

    def _build_highlights_html(self):
        """Build Html bullet list of camp highlights from activity lines.

        Logic: collect unique activity titles (category=activity, non-free,
        non-skeleton-only names) from Plan A, deduplicate, return as <ul>.
        Returns empty string if nothing found.
        """
        program = self._get_plan_a_program()
        if not program:
            return ""

        _SKIP_TITLES = {
            "Czas wolny — do wypełnienia",
            "Śniadanie",
            "Obiad",
            "Kolacja",
            "Podwieczorek",
            "Cisza poobiednia",
            "Cisza nocna",
            "Sen (noc)",
        }

        seen = set()
        items = []
        for day in program.day_ids.sorted("date"):
            for line in day.activity_line_ids.filtered(
                lambda ln: ln.category == "activity" and ln.title
            ).sorted("time_from"):
                title = line.title.strip()
                if title in _SKIP_TITLES or title in seen:
                    continue
                seen.add(title)
                items.append(f"<li>{title}</li>")

        if not items:
            return ""
        return "<ul>" + "".join(items) + "</ul>"

    def _get_price_per_child(self):
        """Return price_per_child from the linked camp budget, or 0.0 if absent.

        budget.py adds `camp_budget_id` (Many2one computed from camp_budget_ids
        One2many, UNIQUE(event_id)) on event.event via _inherit.
        """
        try:
            budget = self.camp_budget_id  # set by budget.py _inherit on event.event
        except AttributeError:
            # camp_budget_id not yet available (module load order) — fallback search
            try:
                budget = (
                    self.env["camp.budget"].sudo().search([("event_id", "=", self.id)], limit=1)
                )
            except Exception:  # noqa: BLE001
                return 0.0
        if not budget:
            return 0.0
        price = budget.price_per_child if hasattr(budget, "price_per_child") else 0.0
        return price or 0.0

    def action_reject(self):
        """Organizator rejects the shift. rejection_reason must be filled."""
        self.ensure_one()
        if not self.env.user.has_group("fayna_camp_portal.group_camp_organizator"):
            raise UserError(_("Тільки Organizator може відхиляти табори."))
        if self.camp_approval_state not in ("pending_approval", "approved"):
            raise UserError(
                _("Відхилити можна лише табір зі статусом «На погодженні» або «Погоджено».")
            )
        if not self.rejection_reason:
            raise UserError(_("Вкажіть причину відхилення перед збереженням."))
        self.sudo().write(
            {
                "camp_approval_state": "rejected",
                "website_published": False,
            }
        )
        # Unpublish linked camp program product if set
        if self.camp_program_id:
            self.camp_program_id.sudo().write({"website_published": False})
        self._post_note(_("Табір відхилено: %s") % self.rejection_reason)

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
        help=_("Lifecycle state of the camp program. Controls visibility on the website."),
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
        help=_("Free-text HTML fallback. Prefer the structured Plan A/B schedule below."),
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
        help=_("Extra photos for the camp gallery — in addition to the main product images."),
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
        help=_("Preview of the top banner of the camp page — auto-built from the fields above."),
    )
    camp_bot_html = fields.Html(
        string="BOT rendered",
        compute="_compute_camp_rendered_html",
        sanitize=False,
        help=_(
            "Preview of the main content block of the camp page — auto-built from the fields above."
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
