# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Camp stories — daily logs / adventures / team moments published to parents.

Migrated 2026-04-30 from the standalone ``fayna_camp_stories`` module
(uninstalled, scheduled for deletion) into ``fayna_camp_portal`` per
CAMPSCOUT_MASTER_TZ §9 step 4.

Notes on the migration:

* Removed ``program_id`` Many2one — it referenced ``camp.program`` which
  lives in ``fayna_camp_program`` (currently uninstalled). Re-add when
  that module is brought online.
* Removed loyalty bridge views — that lives in ``fayna_camp_loyalty``.
* Added ``portal.mixin`` so ``/my/stories/<id>`` can render
  ``portal.message_thread`` chatter (token-based access for guardians).
"""

from odoo import _, fields, models
from odoo.exceptions import UserError, ValidationError


class CampStory(models.Model):
    _name = "camp.story"
    _description = "Camp stories and memories (blog posts, camp logs)"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "event_id, date desc, create_date desc"

    event_id = fields.Many2one(
        "event.event",
        required=True,
        ondelete="cascade",
        index=True,
        tracking=True,
        string="Camp shift (event)",
        help="The specific shift/заїзд this story is from",
    )

    date = fields.Date(
        required=True,
        string="Date",
        tracking=True,
        help="Date the story occurred",
    )

    title = fields.Char(
        required=True,
        string="Title",
        tracking=True,
        help="Story headline",
    )

    content = fields.Html(
        required=True,
        string="Story content",
        help="Detailed story text",
    )

    story_type = fields.Selection(
        [
            ("daily_log", "Daily log"),
            ("participant_spotlight", "Participant spotlight"),
            ("adventure", "Adventure/activity"),
            ("lesson_learned", "Lesson learned"),
            ("team_moment", "Team moment"),
            ("life_skill", "Life skill"),
            ("memory", "Memory/nostalgia"),
        ],
        default="daily_log",
        string="Story type",
        tracking=True,
    )

    author_id = fields.Many2one(
        "res.users",
        required=True,
        index=True,
        default=lambda self: self.env.user,
        string="Author",
        help="Staff member who wrote the story",
    )

    # Tagging & categorization
    tags = fields.Char(
        string="Tags",
        help="Comma-separated tags (e.g. 'friendship, adventure, learning')",
    )

    featured_participants = fields.Char(
        string="Featured participants",
        help="Names or IDs of children mentioned in story (free-text caption)",
    )

    tagged_participant_ids = fields.Many2many(
        "camp.participant",
        string="Tagged children (photo consent-gated)",
        help="Children shown/identified in this story's photos. On publish each "
        "must have signed image consent (Dodatek 4a = 'yes'); enforces RODO "
        "wizerunek — a tagged child without consent cannot be published.",
    )

    # Media
    photo_ids = fields.Many2many(
        "ir.attachment",
        string="Photos",
        help="Photos from the story/event",
    )

    # Publishing workflow
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("published", "Published"),
            ("archived", "Archived"),
        ],
        default="draft",
        string="Status",
        tracking=True,
        index=True,
    )

    publish_date = fields.Datetime(
        string="Published at",
        help="When story was published to parents",
    )

    # Visibility
    public = fields.Boolean(
        string="Public (parents can read)",
        default=True,
        tracking=True,
        help="Show to parents in portal?",
    )

    parent_message = fields.Html(
        string="Parent message",
        help="Optional message from camp to parents about this story",
    )

    # ──────────────────────────────────────────────────────────────────────
    # portal.mixin
    # ──────────────────────────────────────────────────────────────────────

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = f"/my/stories/{rec.id}"

    # ──────────────────────────────────────────────────────────────────────
    # Workflow actions
    # ──────────────────────────────────────────────────────────────────────

    def action_publish(self):
        """Publish story to parents.

        Only draft stories can be published. Attempting to publish an already
        published or archived story raises UserError to prevent accidental
        state corruption (e.g. resetting publish_date on a live story).
        """
        for record in self:
            if record.state != "draft":
                raise UserError(
                    _("Cannot publish a story in state '%s'. Only draft stories can be published.")
                    % record.state
                )
            record._check_image_consent_before_publish()
            record.write({"state": "published", "publish_date": fields.Datetime.now()})

    def _check_image_consent_before_publish(self):
        """RODO wizerunek gate: every tagged child must have signed image
        consent ('yes') before a public story is published. Publishing a
        child's image without consent violates RODO (art. 6/9) and prawo do
        wizerunku (art. 81 pr. aut.). Non-public stories are not shown to
        parents, so the gate applies only when ``public`` is set."""
        self.ensure_one()
        if not self.public:
            return
        missing = self.tagged_participant_ids.filtered(lambda p: p.image_consent_state != "yes")
        if missing:
            raise ValidationError(
                _(
                    "Cannot publish: %s lack(s) signed image consent (Dodatek 4a "
                    "— zgoda na wizerunek). Publishing a child's image without "
                    "consent violates RODO and prawo do wizerunku (art. 81 pr. "
                    "aut.). Collect consent or untag the child."
                )
                % ", ".join(missing.mapped("display_name"))
            )

    def action_archive(self):
        """Archive story.

        Both draft and published stories can be archived. Archiving an already
        archived story raises UserError (idempotency guard — prevents silent
        no-op writes that mask workflow bugs).
        """
        for record in self:
            if record.state == "archived":
                raise UserError(_("Story is already archived."))
            record.write({"state": "archived"})
