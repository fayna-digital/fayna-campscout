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
        _logger.warning(
            "[CS-HERO] _prepare_portal_layout_values partner=%s",
            partner.id,
        )

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
            ).sorted("event_id.date_begin")

            values.update(
                {
                    "cs_participants": participants,
                    "cs_active_regs": active_regs,
                    "cs_upcoming_regs": upcoming_regs[:3],
                    "cs_has_hero": bool(participants or regs),
                    "cs_today": now.date(),
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
                }
            )
        return values

    @http.route("/my/stories", type="http", auth="user", website=True)
    def portal_my_stories(self, **kw):
        """View published camp stories for parent's events."""
        partner = http.request.env.user.partner_id

        try:
            regs = (
                http.request.env["event.registration"]
                .sudo()
                .search([("partner_id", "=", partner.id), ("state", "!=", "cancel")])
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

            stories = http.request.env["camp.story"].search(
                domain,
                order="date desc",
                limit=50,
            )
        except (AccessError, MissingError):
            http.request.redirect("/my")
            return

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
        try:
            documents = http.request.env["legal.document.version"].search(
                [("is_active", "=", True)],
                order="version_date desc",
            )
        except (AccessError, MissingError):
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

        try:
            participants = http.request.env["camp.participant"].search(
                [("parent_partner_id", "=", partner.id)]
            )
            loyalty_records = http.request.env["camp.loyalty"].search(
                [("participant_id", "in", participants.ids)],
                order="loyalty_tier desc, camp_count desc",
            )
        except (AccessError, MissingError):
            loyalty_records = False

        return http.request.render(
            "fayna_campscout.portal_loyalty",
            {
                "loyalties": loyalty_records,
                "page_name": "loyalty",
            },
        )
