# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
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

    # ------------------------------------------------------------------
    # D1 — round-robin assignment of wychowawcy to groups
    # ------------------------------------------------------------------

    @api.model
    def action_assign_wychowawcy(self, event):
        """Assign confirmed/active counselors to shift groups via round-robin.

        Idempotent: clears wychowawca_ids on all event groups before
        reassigning. Does NOT touch group_id on participants.

        :param event: event.event record or id of the camp shift.
        :return: number of assignments made (int).
        """
        if isinstance(event, int):
            event = self.env["event.event"].browse(event)
        event.ensure_one()

        # Confirmed/active counselors with a linked system user.
        counselors = (
            self.env["camp.staff"]
            .search(
                [
                    ("event_id", "=", event.id),
                    ("role", "=", "counselor"),
                    ("state", "in", ("confirmed", "active")),
                    ("user_id", "!=", False),
                ]
            )
            .mapped("user_id")
        )
        groups = self.search([("event_id", "=", event.id)], order="sequence, id")

        # Clear existing wychowawca assignments (idempotency).
        groups.write({"wychowawca_ids": [(5,)]})

        if not counselors or not groups:
            return 0

        counselors_list = list(counselors)
        n = len(counselors_list)
        assignments = 0
        for idx, group in enumerate(groups):
            counselor = counselors_list[idx % n]
            group.write({"wychowawca_ids": [(4, counselor.id)]})
            assignments += 1

        _logger.info(
            "[camp_group] D1: assigned %d counselor(s) to %d group(s) in event %s",
            n,
            len(groups),
            event.id,
        )
        return assignments

    def action_assign_wychowawcy_event(self):
        """Form button — assign wychowawcy round-robin for this group's shift."""
        self.ensure_one()
        self.action_assign_wychowawcy(self.event_id)
        return {
            "type": "ir.actions.act_window",
            "name": _("Groups — %(event)s", event=self.event_id.display_name),
            "res_model": "camp.group",
            "view_mode": "tree,form,kanban",
            "domain": [("event_id", "=", self.event_id.id)],
            "context": {"default_event_id": self.event_id.id},
        }

    # ------------------------------------------------------------------
    # D3 — combined «Сформувати групи + розкидати виховників» glue button
    # ------------------------------------------------------------------

    def action_form_groups_and_assign_wychowawcy(self):
        """D3 glue: run age-based auto-split then assign wychowawcy round-robin."""
        self.ensure_one()
        self.action_auto_split(self.event_id)
        self.action_assign_wychowawcy(self.event_id)
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
    # Stored — дозволяє group-by по заїзду в search-в'юсі учасників.
    # registration_ids = One2many, а current_registration_id = store=False →
    # обидва не лягають у group_by. Джерело правди = РЕЄСТРАЦІЯ (групи group_id
    # ще не призначені → беремо турнус із поточної реєстрації дитини).
    group_event_id = fields.Many2one(
        "event.event",
        string=_("Turnus"),
        store=True,
        index=True,
        compute="_compute_group_event_id",
        help=_(
            "Camp shift from the participant's current registration — lets "
            "participants be grouped by shift in the list."
        ),
    )

    @api.depends("current_registration_id.event_id", "registration_ids.event_id")
    def _compute_group_event_id(self):
        for rec in self:
            reg = rec.current_registration_id or rec.registration_ids[:1]
            rec.group_event_id = reg.event_id if reg else False
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

    # D2 — reserve list (no compatible group with a free slot)
    is_reserve = fields.Boolean(
        string=_("Reserve list"),
        default=False,
        tracking=True,
        index=True,
        help=_(
            "D2: set to True when the child was registered but no compatible "
            "wychowawca group had a free slot (camp is full). The child stays "
            "on the reserve list until a cancellation frees a spot; the system "
            "promotes the earliest-registered reserve child automatically."
        ),
    )

    @api.constrains("group_id", "birth_date", "has_disability")
    def _check_group_composition(self):
        # Writing group_id on the participant does not fire camp.group's own
        # constrains — re-validate the affected groups here.
        self.group_id._validate_composition()


class EventEventCampGroup(models.Model):
    """D2 — auto-assign participant to a wychowawca group on registration.

    Extends event.event with the logic that places a newly-registered child
    into the least-occupied compatible wychowawca group, or marks the child
    as reserve when the camp is full (ADR §D2, rішення A).
    """

    _inherit = "event.event"

    def _auto_assign_participant_to_group(self, registration):
        """Assign *registration.participant_id* to a compatible wychowawca group.

        Compatibility rules (art. 92c, ADR §D2):
          * child under 10 → groups where has_under_10=True OR empty groups
            (capacity limit 15). NEVER assigned to a full-sized (20-slot) group
            that already has ≥10-year-olds.
          * child ≥ 10 → groups where has_under_10=False, capacity limit 20.
          * «compatible» = fits legal limit + disabled limit still OK.
          * Among compatible groups → least occupied (minimum participant_count).
          * If no slot available → is_reserve=True, group_id stays empty, log.

        :param registration: event.registration record.
        """
        self.ensure_one()
        participant = registration.participant_id
        if not participant:
            return
        # Already in a group or no birth_date → skip.
        if participant.group_id or not participant.birth_date:
            return

        start = self.date_begin.date() if self.date_begin else fields.Date.context_today(self)
        age = relativedelta(start, participant.birth_date).years
        is_young = age < UNDER_10_AGE

        groups = self.env["camp.group"].search(
            [("event_id", "=", self.id)],
            order="participant_count asc, sequence asc, id asc",
        )

        best_group = None
        for group in groups:
            count = group.participant_count
            limit = group.capacity_limit  # 15 if has_under_10 else 20
            if count >= limit:
                continue  # full
            # art.92c hard rule: <10 child NEVER into a ≥20-slot group with older kids.
            if is_young and not group.has_under_10 and count > 0:
                # Group has ≥10-year-olds (not has_under_10, non-empty) → skip.
                continue
            # Disability limit check (best-effort; hard constraint re-validates on write).
            if participant.has_disability and group.disabled_count >= GROUP_LIMIT_DISABLED:
                continue
            best_group = group
            break  # groups already sorted by participant_count asc → first fit = least occupied

        if best_group:
            participant.write({"group_id": best_group.id, "is_reserve": False})
            _logger.info(
                "[camp_group] D2: participant %s → group %s (event %s)",
                participant.id,
                best_group.id,
                self.id,
            )
        else:
            participant.write({"is_reserve": True})
            _logger.info(
                "[camp_group] D2: participant %s → reserve list (event %s full)",
                participant.id,
                self.id,
            )

    def _promote_from_reserve(self):
        """Promote the earliest-registered reserve child when a slot opens.

        Called after a registration cancellation or unlink frees capacity.
        Finds the oldest-registered (earliest create_date) reserve participant
        for THIS event that can fit into a now-available compatible group.
        """
        self.ensure_one()
        start = self.date_begin.date() if self.date_begin else fields.Date.context_today(self)

        reserve_regs = self.env["event.registration"].search(
            [
                ("event_id", "=", self.id),
                ("state", "!=", "cancel"),
                ("participant_id.is_reserve", "=", True),
            ],
            order="create_date asc",
        )
        for reg in reserve_regs:
            participant = reg.participant_id
            if not participant or not participant.birth_date:
                continue
            age = relativedelta(start, participant.birth_date).years
            is_young = age < UNDER_10_AGE

            groups = self.env["camp.group"].search(
                [("event_id", "=", self.id)],
                order="participant_count asc, sequence asc, id asc",
            )
            for group in groups:
                count = group.participant_count
                limit = group.capacity_limit
                if count >= limit:
                    continue
                if is_young and not group.has_under_10 and count > 0:
                    continue
                if participant.has_disability and group.disabled_count >= GROUP_LIMIT_DISABLED:
                    continue
                participant.write({"group_id": group.id, "is_reserve": False})
                _logger.info(
                    "[camp_group] D2 promote: participant %s reserve→group %s (event %s)",
                    participant.id,
                    group.id,
                    self.id,
                )
                return  # promote one at a time (next cancel will fire again)
