import logging
from datetime import datetime

from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError

_logger = logging.getLogger(__name__)


class CampscoutPortal(CustomerPortal):
    """Parent portal for CampScout — stories, documents.

    /my/participants is handled by fayna_camp_qualification module (not here).
    /my/loyalty is handled by fayna_camp_loyalty module (not here).
    """

    @http.route(["/my", "/my/home"], type="http", auth="user", website=True)
    def home(self, **kw):
        # Explicit override so Odoo routing uses this class for /my,
        # which makes _prepare_home_portal_values below get called (BP-010).
        return super().home(**kw)

    def _prepare_home_portal_values(self, counters):
        """Odoo 17: Home portal values hook — adds CampScout hero + counters.

        Called by portal.home() route to render /my home page.
        Adds:
          - Hero block data (children, active/upcoming registrations)
          - stories_count / documents_count for portal entry cards
        """
        values = super()._prepare_home_portal_values(counters)
        partner = http.request.env.user.partner_id
        env_sudo = http.request.env(su=True)

        # --- Hero block data ---
        try:
            participants = env_sudo["camp.participant"].search(
                [("parent_partner_id", "=", partner.id)]
            )
            regs = env_sudo["event.registration"].search(
                [("partner_id", "=", partner.id), ("state", "!=", "cancel")]
            )

            now = datetime.now()
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

            user = http.request.env.user
            is_parent_only = (
                user.has_group("base.group_portal")
                and not user.has_group("base.group_user")
                and bool(participants or regs)
            )

            cs_upcoming_camps = env_sudo["event.event"].search(
                [
                    ("date_begin", ">", now),
                    ("is_published", "=", True),
                ],
                order="date_begin asc",
                limit=24,
            )

            values.update(
                {
                    "cs_participants": participants,
                    "cs_active_regs": active_regs,
                    "cs_upcoming_regs": upcoming_regs[:3],
                    "cs_has_hero": bool(participants or regs),
                    "cs_today": now.date(),
                    "cs_parent_only": is_parent_only,
                    "cs_upcoming_camps": cs_upcoming_camps,
                }
            )
        except (AccessError, MissingError) as e:
            _logger.exception("[CS-HERO] home values prep failed: %s", e)
            values.update(
                {
                    "cs_participants": env_sudo["camp.participant"],
                    "cs_active_regs": env_sudo["event.registration"],
                    "cs_upcoming_regs": env_sudo["event.registration"],
                    "cs_has_hero": False,
                    "cs_today": datetime.now().date(),
                    "cs_parent_only": False,
                    "cs_upcoming_camps": env_sudo["event.event"],
                }
            )

        # --- Portal entry card counters ---
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
            except (AccessError, MissingError):
                values["stories_count"] = 0

        if "documents_count" in counters:
            try:
                values["documents_count"] = env_sudo["legal.document.version"].search_count(
                    [("is_active", "=", True)]
                )
            except (AccessError, MissingError):
                values["documents_count"] = 0

        return values

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
            "fayna_campscout.portal_stories",
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
            "fayna_campscout.portal_documents",
            {
                "documents": documents,
                "page_name": "documents",
            },
        )
