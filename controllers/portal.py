from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal


class CampscoutPortal(CustomerPortal):
    """Parent portal for CampScout — view camp progress, stories, documents"""

    def _prepare_portal_layout_values(self):
        values = super()._prepare_portal_layout_values()

        # Count active camps, messages, pending docs
        partner = http.request.env.user.partner_id

        values.update(
            {
                "active_camps_count": self._get_active_camps_count(partner),
                "unread_messages_count": self._get_unread_messages(partner),
                "pending_documents": self._get_pending_documents(partner),
            }
        )
        return values

    @http.route("/my/participants", type="http", auth="user", website=True)
    def portal_my_participants(self, **kw):
        """View all children in all camps"""
        partner = http.request.env.user.partner_id

        participants = http.request.env["camp.participant"].search(
            [("partner_id", "=", partner.id)]
        )

        return http.request.render(
            "fayna_campscout.portal_participants",
            {
                "participants": participants,
            },
        )

    @http.route("/my/stories", type="http", auth="user", website=True)
    def portal_my_stories(self, **kw):
        """View daily stories from camps"""
        partner = http.request.env.user.partner_id

        stories = http.request.env["camp.story"].search(
            [("public", "=", True), ("state", "=", "published")],
            order="date desc",
            limit=50,
        )

        return http.request.render(
            "fayna_campscout.portal_stories",
            {
                "stories": stories,
            },
        )

    @http.route("/my/documents", type="http", auth="user", website=True)
    def portal_my_documents(self, **kw):
        """View legal documents and acceptances"""
        documents = http.request.env["legal.document.version"].search(
            [("is_active", "=", True)]
        )

        return http.request.render(
            "fayna_campscout.portal_documents",
            {
                "documents": documents,
            },
        )

    @http.route("/my/loyalty", type="http", auth="user", website=True)
    def portal_my_loyalty(self, **kw):
        """View loyalty program status"""
        partner = http.request.env.user.partner_id

        loyalty_records = http.request.env["camp.loyalty"].search(
            [("participant_id.partner_id", "=", partner.id)]
        )

        return http.request.render(
            "fayna_campscout.portal_loyalty",
            {
                "loyalties": loyalty_records,
            },
        )

    def _get_active_camps_count(self, partner):
        return http.request.env["event.registration"].search_count(
            [("partner_id", "=", partner.id), ("state", "!=", "cancel")]
        )

    def _get_unread_messages(self, partner):
        return http.request.env["mail.message"].search_count(
            [("partner_ids", "=", partner.id), ("is_discussion", "=", False)]
        )

    def _get_pending_documents(self, partner):
        # Count unsigned legal documents
        return 0  # TODO: implement acceptance tracking
