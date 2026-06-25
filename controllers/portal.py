# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
import logging
from datetime import datetime

from odoo import fields as odoo_fields
from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError

_logger = logging.getLogger(__name__)

# Поля картки, які батько РЕДАГУЄ в кабінеті (секції I/II + kontakty).
# Секції III-VI заповнює персонал (kierownik/wychowawca) — їх сюди НЕ кладемо.
# Цей whitelist — єдиний бар'єр: submit пише через sudo() (portal ACL read-only),
# тож будь-яке поле поза списком не може потрапити у write з порталу.
PARTICIPANT_PORTAL_EDITABLE_FIELDS = (
    "special_needs",
    "emergency_contact_1_name",
    "emergency_contact_1_phone",
    "emergency_contact_1_relation",
    "emergency_contact_2_name",
    "emergency_contact_2_phone",
    "emergency_contact_2_relation",
)

# Strict whitelist of camp.daily.report fields exposed to parents on
# /my/camp-day. Service fields (health_incidents, discipline_notes,
# staff_count_present, kierownik_notes, medical_notes, incidents, …)
# MUST NEVER be added here — the route reads via sudo(), so this list
# is the only barrier between staff-only data and the parent portal.
CAMP_DAY_PUBLIC_REPORT_FIELDS = (
    "report_date",
    "weather",
    "weather_condition",
    "morning_activities",
    "afternoon_activities",
    "evening_activities",
    "meals_summary",
)


class CampscoutPortal(CustomerPortal):
    """Parent portal for CampScout — hero, participants list, stories, documents, loyalty."""

    @http.route(["/my", "/my/home"], type="http", auth="user", website=True)
    def home(self, **kw):
        """Override home to inject hero block data into the initial render.

        In Odoo 17, CustomerPortal.home() only calls _prepare_portal_layout_values()
        which returns minimal values. _prepare_home_portal_values() is only called
        via the /my/counters AJAX endpoint (for badge counts). Hero data (participants,
        active/upcoming registrations) must be added to the initial render here.
        """
        values = self._prepare_portal_layout_values()
        values.update(self._prepare_campscout_hero_values())
        return http.request.render("portal.portal_my_home", values)

    def _prepare_campscout_hero_values(self):
        """Gather hero block data for the /my home page initial render.

        Each sub-query is wrapped in its own try/except so that a single
        failed read doesn't blank the entire hero (e.g. if event.event
        isn't accessible the parent still sees their children).
        Per `feedback_broad_except_silent_ui.md`.
        """
        partner = http.request.env.user.partner_id
        env_sudo = http.request.env(su=True)
        now = datetime.now()
        user = http.request.env.user

        # 1) Children
        try:
            participants = env_sudo["camp.participant"].search(
                [("parent_partner_id", "=", partner.id)]
            )
        except (AccessError, MissingError) as e:
            _logger.warning("[CS-HERO] participants load failed: %s", e)
            participants = env_sudo["camp.participant"]

        # 2) Registrations
        try:
            regs = env_sudo["event.registration"].search(
                [("partner_id", "=", partner.id), ("state", "!=", "cancel")]
            )
        except (AccessError, MissingError) as e:
            _logger.warning("[CS-HERO] registrations load failed: %s", e)
            regs = env_sudo["event.registration"]

        # 3) Filter active/upcoming (pure Python — won't raise ORM errors)
        active_regs = regs.filtered(
            lambda r: (
                r.event_id.date_begin
                and r.event_id.date_end
                and r.event_id.date_begin <= now <= r.event_id.date_end
            )
        )
        upcoming_regs = regs.filtered(
            lambda r: r.event_id.date_begin and r.event_id.date_begin > now
        ).sorted(key=lambda r: r.event_id.date_begin)

        # Target event for the «Dzień w obozie» home card: the camp a child
        # is at right now; otherwise the most recently started past camp.
        past_regs = regs.filtered(
            lambda r: r.event_id.date_begin and r.event_id.date_begin <= now
        ).sorted(key=lambda r: r.event_id.date_begin, reverse=True)
        camp_day_event = (active_regs[:1] or past_regs[:1]).event_id

        is_parent_only = (
            user.has_group("base.group_portal")
            and not user.has_group("base.group_user")
            and bool(participants or regs)
        )

        # 4) Public catalog of upcoming camps (independent of partner)
        try:
            cs_upcoming_camps = env_sudo["event.event"].search(
                [
                    ("date_begin", ">", now),
                    ("website_published", "=", True),
                ],
                order="date_begin asc",
                limit=24,
            )
        except (AccessError, MissingError) as e:
            _logger.warning("[CS-HERO] upcoming camps load failed: %s", e)
            cs_upcoming_camps = env_sudo["event.event"]

        return {
            "cs_participants": participants,
            "cs_active_regs": active_regs,
            "cs_upcoming_regs": upcoming_regs[:3],
            "cs_has_hero": bool(participants or regs),
            "cs_today": now.date(),
            "cs_parent_only": is_parent_only,
            "cs_upcoming_camps": cs_upcoming_camps,
            "cs_camp_day_event": camp_day_event,
        }

    def _prepare_home_portal_values(self, counters):
        """Odoo 17 /my/counters AJAX endpoint — badge counts for portal cards."""
        values = super()._prepare_home_portal_values(counters)
        partner = http.request.env.user.partner_id
        env_sudo = http.request.env(su=True)

        if "stories_count" in counters:
            try:
                event_ids = (
                    env_sudo["event.registration"]
                    .search([("partner_id", "=", partner.id), ("state", "!=", "cancel")])
                    .mapped("event_id")
                    .ids
                )
                domain = [("state", "=", "published"), ("public", "=", True)]
                if event_ids:
                    domain.append(("event_id", "in", event_ids))
                values["stories_count"] = env_sudo["camp.story"].search_count(domain)
            except (AccessError, MissingError, KeyError):
                values["stories_count"] = 0

        if "camp_day_count" in counters:
            try:
                event_ids = (
                    env_sudo["event.registration"]
                    .search([("partner_id", "=", partner.id), ("state", "!=", "cancel")])
                    .mapped("event_id")
                    .ids
                )
                if event_ids:
                    values["camp_day_count"] = env_sudo["camp.daily.report"].search_count(
                        [
                            ("event_id", "in", event_ids),
                            ("state", "in", ["submitted", "approved"]),
                        ]
                    )
                else:
                    values["camp_day_count"] = 0
            except (AccessError, MissingError, KeyError):
                values["camp_day_count"] = 0

        if "documents_count" in counters:
            try:
                values["documents_count"] = env_sudo["legal.document.version"].search_count(
                    [("is_active", "=", True)]
                )
            except (AccessError, MissingError, KeyError):
                values["documents_count"] = 0

        if "support_count" in counters:
            try:
                values["support_count"] = env_sudo["camp.support.request"].search_count(
                    [("partner_id", "=", partner.id)]
                )
            except (AccessError, MissingError, KeyError):
                values["support_count"] = 0

        if "loyalty_count" in counters:
            try:
                values["loyalty_count"] = env_sudo["camp.loyalty.participant"].search_count(
                    [("partner_id", "=", partner.id)]
                )
            except (AccessError, MissingError, KeyError):
                values["loyalty_count"] = 0

        return values

    @http.route("/my/participants", type="http", auth="user", website=True)
    def portal_my_participants(self, **kw):
        """List all children (camp.participant) linked to this parent."""
        partner = http.request.env.user.partner_id
        env_sudo = http.request.env(su=True)
        try:
            participants = env_sudo["camp.participant"].search(
                [("parent_partner_id", "=", partner.id)],
                order="name asc",
            )
        except (AccessError, MissingError) as e:
            _logger.exception("[CS] participants list load failed: %s", e)
            participants = env_sudo["camp.participant"]
        return http.request.render(
            "fayna_camp_portal.portal_participants",
            {
                "participants": participants,
                "page_name": "participants",
            },
        )

    # ──────────────────────────────────────────────────────────────────────
    # Нативний підпис картки kwalifikacyjnej (TZ §5, патерн escort_portal)
    # ──────────────────────────────────────────────────────────────────────

    def _get_own_participant(self, participant_id):
        """Повертає participant лише якщо дитина належить поточному батьку.

        Копія _get_own_escort: portal user не має read на res.partner дитини,
        тож browse/exists/перевірку власності робимо під sudo (env(su=True)),
        але саме лінкування «дитина→батько» лишається жорстким бар'єром.
        """
        env_sudo = http.request.env(su=True)
        participant = env_sudo["camp.participant"].browse(int(participant_id))
        if not participant.exists():
            raise MissingError("Participant not found")
        if participant.parent_partner_id != http.request.env.user.partner_id:
            raise AccessError("Not your child")
        return participant

    @http.route(
        ["/my/participants/<int:participant_id>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_participant_detail(self, participant_id, **kw):
        """Картка дитини з формою картки kwalifikacyjnej + canvas-підписом."""
        try:
            participant = self._get_own_participant(participant_id)
        except (AccessError, MissingError):
            return http.request.redirect("/my/participants")
        return http.request.render(
            "fayna_camp_portal.portal_participants_detail",
            {
                "participant": participant,
                "page_name": "participants",
            },
        )

    @http.route(
        ["/my/participants/<int:participant_id>/submit"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_my_participant_submit(self, participant_id, **post):
        """Збереження полів картки (секції I/II + kontakty). Лишається draft."""
        try:
            participant = self._get_own_participant(participant_id)
        except (AccessError, MissingError):
            return http.request.redirect("/my/participants")
        vals = {
            k: post.get(k)
            for k in PARTICIPANT_PORTAL_EDITABLE_FIELDS
            if k in post
        }
        try:
            # sudo після ownership-check: portal ACL read-only; whitelist вище
            # гарантує, що секції III-VI (персонал) сюди не потраплять.
            participant.sudo().write(vals)
        except (UserError, ValidationError) as e:
            return http.request.render(
                "fayna_camp_portal.portal_participants_detail",
                {
                    "participant": participant,
                    "page_name": "participants",
                    "error": str(e),
                },
            )
        return http.request.redirect(f"/my/participants/{participant.id}")

    @http.route(
        ["/my/participants/<int:participant_id>/sign"],
        type="json",
        auth="user",
        website=True,
    )
    def portal_my_participant_sign(self, participant_id, signature=None, **kw):
        """Підпис картки (canvas dataURL → base64 PNG → sign_qualification)."""
        try:
            participant = self._get_own_participant(participant_id)
        except (AccessError, MissingError):
            return {"error": "access"}
        if not signature:
            return {"error": "no_signature"}
        # canvas dataURL: "data:image/png;base64,XXXX" → лишаємо raw base64
        if "," in signature:
            signature = signature.split(",", 1)[1]
        try:
            # sudo після ownership-check; signed_by_id=справжній батько (юр-доказ)
            participant.sudo().sign_qualification(
                ip_address=http.request.httprequest.remote_addr,
                signature=signature,
                signed_by_id=http.request.env.user.id,
            )
        except (UserError, ValidationError) as e:
            return {"error": str(e)}
        return {"success": True}

    @http.route("/my/loyalty", type="http", auth="user", website=True)
    def portal_my_loyalty(self, **kw):
        """Show loyalty tier, points and discount for this partner."""
        partner = http.request.env.user.partner_id
        env_sudo = http.request.env(su=True)
        loyalty = False
        try:
            rec = env_sudo["camp.loyalty.participant"].search(
                [("partner_id", "=", partner.id)], limit=1
            )
            loyalty = rec or False
        except (AccessError, MissingError) as e:
            _logger.exception("[CS] loyalty load failed: %s", e)
        return http.request.render(
            "fayna_camp_portal.portal_loyalty",
            {
                "loyalty": loyalty,
                "page_name": "loyalty",
            },
        )

    @http.route("/my/stories", type="http", auth="user", website=True)
    def portal_my_stories(self, participant_id=None, **kw):
        """View published camp stories — optionally filtered to one child.

        Without `participant_id`: shows stories for всіх дітей цього батька
        (всі реєстрації aggregate-ом). Falls back to latest public stories
        if the parent has no registrations yet.
        With `participant_id` (must belong to this parent): scopes до events
        where this specific child registered. Гарантує per-child privacy +
        enables «Щоденники Anny» від лінку у детальному кабінеті дитини.
        """
        partner = http.request.env.user.partner_id
        env_sudo = http.request.env(su=True)
        selected_child = False
        children = env_sudo["camp.participant"]

        try:
            children = env_sudo["camp.participant"].search([("parent_partner_id", "=", partner.id)])
            if participant_id:
                try:
                    candidate = children.filtered(lambda c: c.id == int(participant_id))
                    if candidate:
                        selected_child = candidate[:1]
                except (ValueError, TypeError):
                    selected_child = False

            if selected_child:
                regs = selected_child.registration_ids.filtered(lambda r: r.state != "cancel")
            else:
                regs = env_sudo["event.registration"].search(
                    [("partner_id", "=", partner.id), ("state", "!=", "cancel")]
                )

            event_ids = regs.mapped("event_id").ids
            base_domain = [("state", "=", "published"), ("public", "=", True)]

            if event_ids:
                # Show stories from events this parent's children attended
                stories = env_sudo["camp.story"].search(
                    [("event_id", "in", event_ids)] + base_domain,
                    order="date desc",
                    limit=50,
                )
            else:
                # No registrations yet — show recent public stories as a preview
                stories = env_sudo["camp.story"].search(
                    base_domain,
                    order="date desc",
                    limit=10,
                )
        except (AccessError, MissingError) as e:
            _logger.exception("[CS] stories load failed: %s", e)
            stories = env_sudo["camp.story"]

        return http.request.render(
            "fayna_camp_portal.portal_stories",
            {
                "stories": stories,
                "selected_child": selected_child,
                "children": children,
                "page_name": "stories",
            },
        )

    @http.route("/my/documents", type="http", auth="user", website=True)
    def portal_my_documents(self, **kw):
        """View legal documents and policies."""
        env_sudo = http.request.env(su=True)
        try:
            documents = env_sudo["legal.document.version"].search(
                [("is_active", "=", True)],
                order="version_date desc",
            )
        except (AccessError, MissingError, KeyError) as e:
            # KeyError: модель legal.document.version (fayna_legal_versioning)
            # може бути не встановлена (Strangler) — graceful degradation.
            _logger.warning("[CS] documents load skipped: %s", e)
            documents = False

        return http.request.render(
            "fayna_camp_portal.portal_documents",
            {
                "documents": documents,
                "page_name": "documents",
            },
        )

    @http.route(["/my/stories/<int:story_id>"], type="http", auth="user", website=True)
    def portal_my_story_detail(self, story_id, access_token=None, **kw):
        """Single story detail page with chatter (TZ §5A.4)."""
        try:
            story_sudo = self._document_check_access(
                "camp.story", story_id, access_token=access_token
            )
        except (AccessError, MissingError):
            return http.request.redirect("/my/stories")
        if story_sudo.state != "published" or not story_sudo.public:
            return http.request.redirect("/my/stories")
        values = self._prepare_portal_layout_values()
        values.update(
            {
                "story": story_sudo,
                "page_name": "story",
                "user_id": http.request.env.user,
                "token": access_token,
            }
        )
        return http.request.render("fayna_camp_portal.portal_stories_detail", values)

    @http.route("/my/transport", type="http", auth="user", website=True)
    def portal_my_transport(self, **kw):
        """List transport trips for any participant linked to this parent."""
        partner = http.request.env.user.partner_id
        env_sudo = http.request.env(su=True)
        try:
            participants = env_sudo["camp.participant"].search(
                [("parent_partner_id", "=", partner.id)]
            )
            transports = env_sudo["camp.transport"].search(
                [("participant_ids", "in", participants.ids)],
                order="departure_datetime desc",
            )
        except (AccessError, MissingError) as e:
            _logger.exception("[CS] transport list load failed: %s", e)
            transports = env_sudo["camp.transport"]
            participants = env_sudo["camp.participant"]
        return http.request.render(
            "fayna_camp_portal.portal_transport",
            {
                "transports": transports,
                "participants": participants,
                "page_name": "transport",
            },
        )

    @http.route(["/my/transport/<int:transport_id>"], type="http", auth="user", website=True)
    def portal_my_transport_detail(self, transport_id, access_token=None, **kw):
        """Detail page for a single transport trip — token-aware via portal.mixin."""
        try:
            transport_sudo = self._document_check_access(
                "camp.transport", transport_id, access_token
            )
        except (AccessError, MissingError):
            return http.request.redirect("/my/transport")
        return http.request.render(
            "fayna_camp_portal.portal_transport_detail",
            {
                "transport": transport_sudo,
                "page_name": "transport",
            },
        )

    # ──────────────────────────────────────────────────────────────────────
    # /my/camp-day — «Dzień w obozie» (TZ_SPRINT_2026-06-10 §7)
    # ──────────────────────────────────────────────────────────────────────

    def _get_parent_camp_events(self):
        """Events of all non-cancelled registrations of the current partner.

        Same access pattern as the /my hero and /my/stories: sudo() with an
        explicit `partner_id` scope (portal users have no read access on
        event.event / event.registration core models).
        """
        partner = http.request.env.user.partner_id
        env_sudo = http.request.env(su=True)
        regs = env_sudo["event.registration"].search(
            [("partner_id", "=", partner.id), ("state", "!=", "cancel")]
        )
        return regs.mapped("event_id")

    @http.route(["/my/camp-day/<int:event_id>"], type="http", auth="user", website=True)
    def portal_my_camp_day(self, event_id, date=None, **kw):
        """«Dzień w obozie» — per-day weather, activities, meals and photos.

        Access gate: the event must belong to a registration of THIS parent
        (children of the current user) — otherwise redirect to /my. Data is
        read via sudo(), therefore:

        * camp.story — filtered MANUALLY to state=published AND public=True
          AND this event (do not rely on rule_story_portal_own_events: the
          record rule does not apply under sudo).
        * camp.daily.report — only the CAMP_DAY_PUBLIC_REPORT_FIELDS
          whitelist is copied into plain dicts; the recordset itself is
          never passed to the template, so service fields (health_incidents,
          staff_count_present, kierownik_notes, medical_notes, …) physically
          cannot leak into the rendered page.
        """
        env_sudo = http.request.env(su=True)

        # 1) Access gate — event must be one of this parent's registrations
        try:
            allowed_events = self._get_parent_camp_events()
        except (AccessError, MissingError) as e:
            _logger.warning("[CS-CAMPDAY] parent events load failed: %s", e)
            return http.request.redirect("/my")
        if event_id not in allowed_events.ids:
            return http.request.redirect("/my")
        event = env_sudo["event.event"].browse(event_id)

        # 2) Published public stories of this event (manual filter — sudo!)
        stories = env_sudo["camp.story"].search(
            [
                ("event_id", "=", event_id),
                ("state", "=", "published"),
                ("public", "=", True),
            ],
            order="date desc, id desc",
        )

        # 3) Daily reports of this event — drafts excluded, whitelist only
        reports = env_sudo["camp.daily.report"].search(
            [
                ("event_id", "=", event_id),
                ("state", "in", ["submitted", "approved"]),
            ],
            order="report_date desc",
        )
        report_by_date = {}
        for rep in reports:
            report_by_date[rep.report_date] = {
                field: rep[field] for field in CAMP_DAY_PUBLIC_REPORT_FIELDS
            }

        # 4) Photos of the day — attachments served via /web/image with an
        #    access token (portal users have no direct ACL on staff-uploaded
        #    ir.attachment records).
        stories_by_date = {}
        for story in stories:
            photos = []
            attachments = story.photo_ids
            if attachments:
                tokens = attachments.generate_access_token()
                for att, token in zip(attachments, tokens, strict=False):
                    photos.append(
                        {
                            "name": att.name or "",
                            "url": f"/web/image/{att.id}?access_token={token}",
                        }
                    )
            stories_by_date.setdefault(story.date, []).append(
                {"id": story.id, "title": story.title, "photos": photos}
            )

        # 5) Group by date, newest day first; ?date=YYYY-MM-DD selects one day
        all_dates = sorted(set(report_by_date) | set(stories_by_date), reverse=True)
        selected_date = None
        if date:
            try:
                candidate = odoo_fields.Date.from_string(date)
                if candidate in all_dates:
                    selected_date = candidate
            except ValueError:
                selected_date = None

        days = [
            {
                "date": day,
                "report": report_by_date.get(day),
                "stories": stories_by_date.get(day, []),
            }
            for day in all_dates
            if not selected_date or day == selected_date
        ]

        return http.request.render(
            "fayna_camp_portal.portal_camp_day",
            {
                "event": event,
                "days": days,
                "all_dates": all_dates,
                "selected_date": selected_date,
                "page_name": "camp_day",
            },
        )

    # ──────────────────────────────────────────────────────────────────────
    # /my/support — Звернення (camp.support.request)
    #
    # The model already inherits portal.mixin with access_url
    # `/my/support/<id>` (models/portal_mixin_extensions.py) and the home
    # hero links here, but the matching HTTP routes were missing — every
    # «Звернення» link 404'd. These two read-only routes close that gap.
    # Records are scoped to the current partner via portal.mixin's own
    # access-token check (_document_check_access) on the detail page and an
    # explicit partner_id domain on the list.
    # ──────────────────────────────────────────────────────────────────────

    @http.route("/my/support", type="http", auth="user", website=True)
    def portal_my_support(self, **kw):
        """List support requests (question / cancel / transfer) of this parent."""
        partner = http.request.env.user.partner_id
        env_sudo = http.request.env(su=True)
        try:
            supports = env_sudo["camp.support.request"].search(
                [("partner_id", "=", partner.id)],
                order="submission_date desc, id desc",
            )
        except (AccessError, MissingError) as e:
            _logger.exception("[CS] support list load failed: %s", e)
            supports = env_sudo["camp.support.request"]
        return http.request.render(
            "fayna_camp_portal.portal_support",
            {
                "supports": supports,
                "page_name": "support",
            },
        )

    @http.route(["/my/support/<int:support_id>"], type="http", auth="user", website=True)
    def portal_my_support_detail(self, support_id, access_token=None, **kw):
        """Single support request detail with chatter — token-aware via portal.mixin."""
        try:
            support_sudo = self._document_check_access(
                "camp.support.request", support_id, access_token
            )
        except (AccessError, MissingError):
            return http.request.redirect("/my/support")
        values = self._prepare_portal_layout_values()
        values.update(
            {
                "support": support_sudo,
                "page_name": "support",
                "user_id": http.request.env.user,
                "token": access_token,
            }
        )
        return http.request.render(
            "fayna_camp_portal.portal_support_detail", values
        )
