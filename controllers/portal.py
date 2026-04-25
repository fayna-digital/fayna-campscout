import logging
from datetime import datetime

from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError

_logger = logging.getLogger(__name__)


class CampscoutPortal(CustomerPortal):
    """Parent portal for CampScout — stories, documents, loyalty.

    /my/participants is handled by fayna_camp_qualification module (not here).
    """

    def _prepare_home_portal_values(self, counters):
        """Odoo 17: Home portal values hook (for future dashboard integration).

        Called by portal.home() route. Currently delegates to parent.
        """
        return super()._prepare_home_portal_values(counters)

    def _prepare_portal_layout_values(self):
        """Layout values for sidebar + hero banner.

        Called by portal.layout template for render context (children, events, etc).
        """
        values = super()._prepare_portal_layout_values()
        partner = http.request.env.user.partner_id

        try:
            participants = (
                http.request.env["camp.participant"]
                .sudo()
                .search([("parent_partner_id", "=", partner.id)])
            )
            regs = (
                http.request.env["event.registration"]
                .sudo()
                .search(
                    [
                        ("partner_id", "=", partner.id),
                        ("state", "!=", "cancel"),
                    ]
                )
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

            cs_upcoming_camps = (
                http.request.env["event.event"]
                .sudo()
                .search(
                    [
                        ("date_begin", ">", now),
                        ("is_published", "=", True),
                    ],
                    order="date_begin asc",
                    limit=24,
                )
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
            _logger.exception("[CS-HERO] hero data prep failed: %s", e)
            empty_p = http.request.env["camp.participant"]
            empty_r = http.request.env["event.registration"]
            values.update(
                {
                    "cs_participants": empty_p,
                    "cs_active_regs": empty_r,
                    "cs_upcoming_regs": empty_r,
                    "cs_has_hero": False,
                    "cs_today": datetime.now().date(),
                    "cs_parent_only": False,
                    "cs_upcoming_camps": http.request.env["event.event"],
                }
            )
        return values

    @http.route("/my/stories", type="http", auth="user", website=True)
    def portal_my_stories(self, participant_id=None, **kw):
        """View published camp stories — optionally filtered to one child.

        Without `participant_id`: shows stories for всіх дітей цього батька
        (всі реєстрації aggregate-ом).
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
            domain = [
                ("state", "=", "published"),
                ("public", "=", True),
            ]
            if event_ids:
                domain.insert(0, ("event_id", "in", event_ids))
            else:
                domain.insert(0, (1, "=", 0))

            stories = env_sudo["camp.story"].search(
                domain,
                order="date desc",
                limit=50,
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

    @http.route("/my/loyalty", type="http", auth="user", website=True)
    def portal_my_loyalty(self, **kw):
        """View loyalty program status for all children."""
        partner = http.request.env.user.partner_id
        env_sudo = http.request.env(su=True)

        try:
            participants = env_sudo["camp.participant"].search(
                [("parent_partner_id", "=", partner.id)]
            )
            loyalty_records = env_sudo["camp.loyalty"].search(
                [("participant_id", "in", participants.ids)],
                order="loyalty_tier desc, camp_count desc",
            )
        except (AccessError, MissingError) as e:
            _logger.exception("[CS] loyalty load failed: %s", e)
            loyalty_records = False

        return http.request.render(
            "fayna_campscout.portal_loyalty",
            {
                "loyalties": loyalty_records,
                "page_name": "loyalty",
            },
        )
