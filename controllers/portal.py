import logging
from datetime import datetime

from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError

_logger = logging.getLogger(__name__)


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
        except (AccessError, MissingError) as e:
            _logger.exception("[CS] documents load failed: %s", e)
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
