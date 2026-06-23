# Fayna CampScout — Grupa wychowawcza (§2 / art. 92c ustawy o systemie oświaty)
#
# Legal basis: art. 92c ust. 2 pkt 1 ustawy z 7.09.1991 o systemie oświaty +
# Rozp. MEN 30.03.2016 — each camp shift is divided into "grupy wychowawcze":
#   * max 20 participants per group;
#   * max 15 participants when the group includes a child under 10 years old;
#   * participants with disabilities — limited per group (sprint TZ §2: <= 2).
#
# Design notes (sprint 2026-06-10, TZ_SPRINT §2):
#   * `wychowawca_ids` is a Many2many to res.users (NOT camp.staff).
#     camp.staff carries `user_id` for record-rule scoping; linking groups
#     straight to res.users keeps the wychowawca record rule a simple
#     `('group_id.wychowawca_ids', 'in', [user.id])` without an extra hop
#     through camp.staff. The staff card stays the HR source of truth;
#     the group link is the ACL source of truth.
#   * `camp.participant.group_id` is added here (same vertical slice) so the
#     whole feature ships in one file; integration only needs the import.
import math

from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Legal capacity limits — art. 92c ust. 2 pkt 1 ustawy o systemie oświaty.
GROUP_LIMIT_DEFAULT = 20
GROUP_LIMIT_UNDER_10 = 15
UNDER_10_AGE = 10
# Sprint TZ §2: at most 2 participants with disabilities per group.
GROUP_LIMIT_DISABLED = 2


class CampGroup(models.Model):
    """Grupa wychowawcza — legal unit of supervision inside a camp shift.

    One wychowawca group per art. 92c: max 20 children (15 when any child is
    under 10 on the shift start date). The dziennik zajęć (Załącznik 5) is
    kept per group; the wychowawca record rule on camp.participant scopes
    visibility to the children of the wychowawca's own groups.
    """

    _name = "camp.group"
    _description = "Grupa wychowawcza (art. 92c)"
    _inherit = ["mail.thread"]
    _order = "event_id, sequence, name, id"

    name = fields.Char(
        required=True,
        index=True,
        tracking=True,
        string=_("Group name"),
        help=_("Group designation, e.g. 'Grupa A' or 'Poszumymi-1'."),
    )
    sequence = fields.Integer(
        default=10,
        string=_("Sequence"),
        help=_("Ordering of groups inside the camp shift."),
    )
    active = fields.Boolean(
        default=True,
        string=_("Active"),
        help=_("Inactive groups are hidden from lists but kept for archival."),
    )
    event_id = fields.Many2one(
        "event.event",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
        string=_("Camp shift (event)"),
        help=_(
            "The camp shift this group belongs to. Participants must be "
            "registered to the same shift (hard constraint)."
        ),
    )
    wychowawca_ids = fields.Many2many(
        "res.users",
        relation="camp_group_wychowawca_rel",
        column1="group_id",
        column2="user_id",
        string=_("Wychowawcy"),
        domain=lambda self: [
            ("groups_id", "in", self.env.ref("fayna_camp_portal.group_camp_wychowawca").ids)
        ],
        help=_(
            "Counselors responsible for this group (login accounts). "
            "Drives the record rule: a wychowawca sees only participants of "
            "their own groups. Kept as res.users (not camp.staff) so the "
            "ACL domain stays a direct membership check."
        ),
    )
    participant_ids = fields.One2many(
        "camp.participant",
        "group_id",
        string=_("Participants"),
        help=_("Children assigned to this wychowawca group."),
    )
    notes = fields.Text(
        string=_("Notes"),
        help=_("Internal remarks about the group (age mix, special arrangements)."),
    )

    participant_count = fields.Integer(
        compute="_compute_participant_count",
        string=_("# participants"),
        help=_("Number of children currently assigned to this group."),
    )
    has_under_10 = fields.Boolean(
        compute="_compute_capacity",
        string=_("Has children under 10"),
        help=_(
            "True when at least one assigned child is younger than 10 years "
            "on the shift start date — lowers the legal limit to 15 (art. 92c)."
        ),
    )
    capacity_limit = fields.Integer(
        compute="_compute_capacity",
        string=_("Legal capacity limit"),
        help=_(
            "Art. 92c ust. 2 pkt 1: 20 participants per group, or 15 when "
            "the group includes a child under 10 years old."
        ),
    )
    disabled_count = fields.Integer(
        compute="_compute_disabled_count",
        string=_("# special needs"),
        help=_(
            "Participants counted against the per-group disability limit "
            "(sprint TZ §2: max 2 per group)."
        ),
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends("participant_ids")
    def _compute_participant_count(self):
        for rec in self:
            rec.participant_count = len(rec.participant_ids)

    @api.depends("participant_ids.birth_date", "event_id.date_begin")
    def _compute_capacity(self):
        for rec in self:
            start = rec._shift_start_date()
            rec.has_under_10 = any(
                p.birth_date and relativedelta(start, p.birth_date).years < UNDER_10_AGE
                for p in rec.participant_ids
            )
            rec.capacity_limit = GROUP_LIMIT_UNDER_10 if rec.has_under_10 else GROUP_LIMIT_DEFAULT

    @api.depends("participant_ids.has_disability")
    def _compute_disabled_count(self):
        # has_disability — окремий boolean (kierownik/organizator за картою).
        # Апроксимація по special_needs хибно рахувала «не їсть гречку» як
        # niepełnosprawność і валила auto-split на живих даних (INC 11.06).
        for rec in self:
            rec.disabled_count = len(rec.participant_ids.filtered("has_disability"))

    def _shift_start_date(self):
        """Date used as the age anchor — shift start, fallback today."""
        self.ensure_one()
        if self.event_id and self.event_id.date_begin:
            return self.event_id.date_begin.date()
        return fields.Date.context_today(self)

    # ------------------------------------------------------------------
    # Constraints (§2 — hard, no override)
    # ------------------------------------------------------------------

    @api.constrains("participant_ids", "event_id")
    def _check_composition(self):
        self._validate_composition()

    def _validate_composition(self):
        """Full legal validation of the group composition (art. 92c).

        Called both from this model's constrains and from
        camp.participant._check_group_composition (writing `group_id` on the
        many2one side does not trigger constrains on the group record).
        """
        for group in self:
            count = len(group.participant_ids)
            limit = group.capacity_limit
            if count > limit:
                raise ValidationError(
                    _(
                        "Group '%(group)s' would have %(count)s participants — "
                        "above the legal limit of %(limit)s. "
                        "Art. 92c ust. 2 pkt 1 ustawy o systemie oświaty: "
                        "max 20 participants per wychowawca group, max 15 when "
                        "the group includes a child under 10 years old.",
                        group=group.name,
                        count=count,
                        limit=limit,
                    )
                )
            if group.disabled_count > GROUP_LIMIT_DISABLED:
                raise ValidationError(
                    _(
                        "Group '%(group)s' would have %(count)s participants with "
                        "special/disability needs — at most %(limit)s are allowed "
                        "per wychowawca group (§2, art. 92c).",
                        group=group.name,
                        count=group.disabled_count,
                        limit=GROUP_LIMIT_DISABLED,
                    )
                )
            wrong = group.participant_ids.filtered(
                lambda p, ev=group.event_id: (
                    not any(
                        reg.event_id == ev and reg.state != "cancel" for reg in p.registration_ids
                    )
                )
            )
            if wrong:
                raise ValidationError(
                    _(
                        "Participants %(children)s are not registered to camp shift "
                        "'%(event)s' — a child can only be assigned to a wychowawca "
                        "group of their own shift.",
                        children=", ".join(wrong.mapped("display_name")),
                        event=group.event_id.display_name,
                    )
                )

    # ------------------------------------------------------------------
    # Auto-split (§2 — авто-розподіл за віком)
    # ------------------------------------------------------------------

    @api.model
    def action_auto_split(self, event):
        """Distribute unassigned children of *event* into age-based groups.

        Rules (sprint TZ §2):
          * children already assigned to a group are NOT touched;
          * under-10 children (age on shift start date) go to separate groups
            with the 15-participant limit; the rest use the 20 limit;
          * new groups are created as needed; existing groups are never
            topped up (adding an under-10 child to a mixed group could
            silently flip its legal limit from 20 to 15);
          * children are spread EVENLY across the minimal number of groups
            (e.g. 17 young children -> 9 + 8, not 15 + 2): pedagogically
            balanced groups and headroom for late manual moves.

        :param event: event.event record or id of the camp shift
        :return: camp.group recordset of the newly created groups
        """
        if isinstance(event, int):
            event = self.env["event.event"].browse(event)
        event.ensure_one()

        registrations = self.env["event.registration"].search(
            [
                ("event_id", "=", event.id),
                ("state", "!=", "cancel"),
                ("participant_id", "!=", False),
            ]
        )
        unassigned = registrations.participant_id.filtered(
            lambda p: not p.group_id and p.birth_date
        )
        if not unassigned:
            return self.browse()

        start = event.date_begin.date() if event.date_begin else fields.Date.context_today(self)
        young = unassigned.filtered(
            lambda p: relativedelta(start, p.birth_date).years < UNDER_10_AGE
        )
        older = unassigned - young

        created = self.browse()
        next_no = (
            self.search_count([("event_id", "=", event.id), ("active", "in", [True, False])]) + 1
        )
        for bucket, limit, suffix in (
            (young, GROUP_LIMIT_UNDER_10, _(" (under 10)")),
            (older, GROUP_LIMIT_DEFAULT, ""),
        ):
            # Keep close ages together: sort by birth date before chunking.
            remaining = bucket.sorted("birth_date")
            for size in self._balanced_sizes(len(remaining), limit):
                chunk = remaining[:size]
                remaining = remaining[size:]
                group = self.create(
                    {
                        "name": _("Group %(no)s%(suffix)s", no=next_no, suffix=suffix),
                        "event_id": event.id,
                        "sequence": 10 * next_no,
                    }
                )
                chunk.write({"group_id": group.id})
                created |= group
                next_no += 1
        return created

    @api.model
    def _balanced_sizes(self, total, limit):
        """Split *total* children into even chunks of at most *limit*.

        Uses the minimal number of groups, then levels the sizes:
        17 with limit 15 -> [9, 8]; 35 with limit 20 -> [18, 17].
        """
        if total <= 0:
            return []
        groups = math.ceil(total / limit)
        base, extra = divmod(total, groups)
        return [base + 1] * extra + [base] * (groups - extra)

    def action_auto_split_event(self):
        """Form button — auto-split the remaining unassigned children of this
        group's shift, then show all groups of the shift."""
        self.ensure_one()
        self.action_auto_split(self.event_id)
        return {
            "type": "ir.actions.act_window",
            "name": _("Groups — %(event)s", event=self.event_id.display_name),
            "res_model": "camp.group",
            "view_mode": "tree,form,kanban",
            "domain": [("event_id", "=", self.event_id.id)],
            "context": {"default_event_id": self.event_id.id},
        }


class CampParticipant(models.Model):
    """Adds the wychowawca-group link to the participant (§2 vertical slice)."""

    _inherit = "camp.participant"

    group_id = fields.Many2one(
        "camp.group",
        string=_("Grupa wychowawcza"),
        index=True,
        tracking=True,
        ondelete="set null",
        help=_(
            "Wychowawca group (art. 92c) the child belongs to within their "
            "camp shift. Drives the wychowawca record rule: counselors see "
            "only children of their own groups."
        ),
    )
    # Stored related — дозволяє group-by по заїзду в search-в'юсі учасників
    # (registration_ids = One2many, computed current_registration_id = store=False
    #  → жодне з них не лягає у group_by). Джерело правди = group_id.event_id;
    # дитина без групи → порожній заїзд (видно в "Brak grupy/turnusu").
    group_event_id = fields.Many2one(
        "event.event",
        string=_("Turnus (grupa)"),
        related="group_id.event_id",
        store=True,
        index=True,
        help=_(
            "Camp shift the child's wychowawca group belongs to — projection of "
            "group_id.event_id so participants can be grouped by shift in the list."
        ),
    )
    has_disability = fields.Boolean(
        string=_("Niepełnosprawność / przewlekła choroba (§2)"),
        tracking=True,
        help=_(
            "Counted against the §2 art. 92c limit: max 2 such participants "
            "per wychowawca group. Set by the organizer/kierownik based on the "
            "qualification card — NOT derived from free-text notes (INC "
            "11.06: old checkout notes like dietary quirks falsely tripped "
            "the limit)."
        ),
    )

    @api.constrains("group_id", "birth_date", "has_disability")
    def _check_group_composition(self):
        # Writing group_id on the participant does not fire camp.group's own
        # constrains — re-validate the affected groups here.
        self.group_id._validate_composition()
