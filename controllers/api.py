from odoo import _, http
from odoo.http import request


class CampscoutAPI(http.Controller):
    """REST API for mobile apps and portals"""

    @http.route("/api/v1/participants", type="json", auth="user")
    def api_get_participants(self, **kw):
        """Get list of children for logged-in parent"""
        partner = request.env.user.partner_id

        participants = request.env["camp.participant"].search(
            [("parent_partner_id", "=", partner.id)]
        )

        return {
            "data": [
                {
                    "id": p.id,
                    "name": p.display_name,
                    "age": p.age,
                    "gender": p.gender,
                }
                for p in participants
            ]
        }

    @http.route("/api/v1/participants/<int:participant_id>/camp", type="json", auth="user")
    def api_participant_camp(self, participant_id, **kw):
        """Get current camp info for a child"""
        participant = request.env["camp.participant"].browse(participant_id)

        # Find active registration for this child's parent
        registration = request.env["event.registration"].search(
            [("participant_id", "=", participant.id), ("state", "!=", "cancel")],
            limit=1,
        )

        if not registration:
            return {"error": _("No active camp found")}

        return {
            "camp": {
                "id": registration.event_id.id,
                "name": registration.event_id.name,
                "date_start": registration.event_id.date_begin,
                "date_end": registration.event_id.date_end,
                "days_remaining": (
                    registration.event_id.date_end - request.context.get("today")
                ).days,
            }
        }

    @http.route("/api/v1/stories", type="json", auth="user")
    def api_get_stories(self, **kw):
        """Get published stories scoped to the logged-in parent's events."""
        partner = request.env.user.partner_id
        regs = request.env["event.registration"].search([("partner_id", "=", partner.id)])
        event_ids = regs.mapped("event_id").ids
        domain = [("state", "=", "published"), ("public", "=", True)]
        if event_ids:
            domain.append(("event_id", "in", event_ids))
        stories = request.env["camp.story"].search(
            domain,
            order="date desc",
            limit=20,
        )

        return {
            "data": [
                {
                    "id": s.id,
                    "title": s.title,
                    "date": s.date,
                    "type": s.story_type,
                    "summary": s.content[:200],
                }
                for s in stories
            ]
        }

    @http.route("/api/v1/stories/<int:story_id>", type="json", auth="user")
    def api_get_story_detail(self, story_id, **kw):
        """Get full story"""
        story = request.env["camp.story"].browse(story_id)

        return {
            "id": story.id,
            "title": story.title,
            "date": story.date,
            "content": story.content,
            "author": story.author_id.name,
            "photos": [
                {"id": a.id, "name": a.name, "url": f"/web/image/{a.id}"} for a in story.photo_ids
            ],
        }

    @http.route("/api/v1/loyalty", type="json", auth="user")
    def api_get_loyalty(self, **kw):
        """Get loyalty program status for the logged-in parent."""
        partner = request.env.user.partner_id

        loyalty = (
            request.env["camp.loyalty.participant"]
            .sudo()
            .search([("partner_id", "=", partner.id)], limit=1)
        )

        if not loyalty:
            return {"status": "not_enrolled"}

        return {
            "tier": loyalty.tier,
            "camps_attended": loyalty.camps_count,
            "points": loyalty.points,
            "discount": loyalty.discount,
            "next_tier": "gold" if loyalty.tier == "silver" else None,
        }

    @http.route("/api/v1/documents", type="json", auth="user")
    def api_get_documents(self, **kw):
        """Get legal documents to sign"""
        documents = request.env["legal.document.version"].search(
            [("is_active", "=", True), ("required_acceptance", "=", True)]
        )

        return {
            "data": [
                {
                    "id": d.id,
                    "type": d.document_type,
                    "version": d.version_number,
                    "language": d.language,
                    "requires_signature": True,
                }
                for d in documents
            ]
        }

    @http.route("/api/v1/messages", type="json", auth="user")
    def api_get_messages(self, **kw):
        """Get unread messages from camp"""
        partner = request.env.user.partner_id

        messages = request.env["mail.message"].search(
            [("partner_ids", "=", partner.id), ("message_type", "!=", "notification")],
            order="date desc",
            limit=20,
        )

        return {
            "unread_count": len(messages),
            "data": [
                {
                    "id": m.id,
                    "subject": m.subject,
                    "body": m.body[:200],
                    "date": m.date,
                    "from": m.author_id.name,
                }
                for m in messages
            ],
        }
