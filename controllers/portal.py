import logging
from datetime import datetime

from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal

_logger = logging.getLogger(__name__)


class CampscoutPortal(CustomerPortal):
    """Parent portal for CampScout — stories, documents, loyalty.

    /my/participants is handled by fayna_camp_qualification module (not here).
    """

    def _prepare_portal_layout_values(self):
        """Inject children + current/upcoming camps for /my hero banner.

        Odoo 17: portal.home() route calls THIS method to build the
        HTML render context. _prepare_home_portal_values is only used
        by the /my/counters JSON endpoint for badge counts — NOT for
        template values. Core sale/account don't pass dynamic values
        to HTML (all static text), but we need dynamic (child names,
        event dates), so _prepare_portal_layout_values is the right
        hook.
        """
        values = super()._prepare_portal_layout_values()
        partner = http.request.env.user.partner_id

        try:
            # Standard Odoo portal pattern: use sudo() with explicit
            # partner_id filter. The filter itself scopes the result to
            # the logged-in user — we don't need record rules on
            # event.event / event.registration on top of that.
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
                lambda r: r.event_id.date_begin
                and r.event_id.date_end
                and r.event_id.date_begin <= now <= r.event_id.date_end
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

            # Upcoming camps for "Забронювати табір" modal — published
            # events whose start is in the future, grouped by product when
            # possible. We use event.event (not product.template) because
            # that's what drives availability and has concrete dates.
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
        except Exception as e:
            # Broad catch so any unexpected error still yields a valid
            # values dict (earlier AccessError-only except let TypeError
            # swallow cs_has_hero, producing a silent undefined in qweb).
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
    def portal_my_stories(self, **kw):
        """View published camp stories for parent's events."""
        partner = http.request.env.user.partner_id
        env_sudo = http.request.env(su=True)

        try:
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
        except Exception:
            _logger.exception("[CS] stories load failed")
            stories = env_sudo["camp.story"]

        return http.request.render(
            "fayna_campscout.portal_stories",
            {
                "stories": stories,
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
        except Exception:
            _logger.exception("[CS] documents load failed")
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
        except Exception:
            _logger.exception("[CS] loyalty load failed")
            loyalty_records = False

        return http.request.render(
            "fayna_campscout.portal_loyalty",
            {
                "loyalties": loyalty_records,
                "page_name": "loyalty",
            },
        )
