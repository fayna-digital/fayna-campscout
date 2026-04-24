import logging

from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError

_logger = logging.getLogger(__name__)


class CampscoutPortal(CustomerPortal):
    """Parent portal for CampScout — stories, documents, loyalty.

    /my/participants is handled by fayna_camp_qualification module (not here).
    """

    def _prepare_home_portal_values(self, counters):
        """Odoo 17 pattern: prepare home portal values."""
        values = super()._prepare_home_portal_values(counters)
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
