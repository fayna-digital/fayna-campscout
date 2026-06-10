# Fayna CampScout — Regulaminy wypoczynku + acknowledgment kadry
# TZ_SPRINT_2026-06-10 §4 "Regulaminy + Teczka KO":
#   - camp.regulamin       — regulamin kolonii/obozu, kąpieli, wycieczek, ppoż.,
#                            zakres czynności wychowawcy (wzory z RAG).
#                            event_id empty = organizer-wide template (all camps).
#   - camp.regulamin.ack   — staff × regulamin acknowledgment (data + podpis + IP).
#                            Only the staff member's own user may sign; frozen
#                            after signing (legal evidence, same pattern as
#                            camp.participant.qualification_signed).
#   - camp.staff (inherit) — unsigned_regulamin_count for the kierownik
#                            "kto nie podpisał" dashboard.
# Unsigned regulaminy do NOT block the shift start (no ValidationError — PL law
# does not forbid it); kierownik gets an activity/log warning instead
# (check_acks_for_event), and Teczka KO shows ❌.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# camp.regulamin — the document itself
# ---------------------------------------------------------------------------


class CampRegulamin(models.Model):
    _name = "camp.regulamin"
    _description = "Regulamin wypoczynku (dokument wydany przez kierownika)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "event_id, regulamin_type, name"

    name = fields.Char(
        required=True,
        tracking=True,
        string=_("Title"),
        help=_("Document title, e.g. 'Regulamin kąpieli — Obóz NWŚ turnus 2'."),
    )

    regulamin_type = fields.Selection(
        [
            ("kolonii_obozu", "Regulamin kolonii / obozu"),
            ("kapieli", "Regulamin kąpieli"),
            ("wycieczek", "Regulamin wycieczek"),
            ("ppoz", "Instrukcja ppoż."),
            ("zakres_czynnosci_wychowawcy", "Zakres czynności wychowawcy"),
            ("inne", "Inne"),
        ],
        required=True,
        default="kolonii_obozu",
        index=True,
        tracking=True,
        string=_("Type"),
        help=_("Document type per arkusz kontroli KO (doc-kku-arkusz-ko)."),
    )

    event_id = fields.Many2one(
        "event.event",
        index=True,
        ondelete="cascade",
        tracking=True,
        string=_("Camp shift (event)"),
        help=_(
            "Shift this regulamin applies to. Leave EMPTY for an "
            "organizer-wide template that applies to all camps."
        ),
    )

    content = fields.Html(
        string=_("Content"),
        help=_("Full text of the regulamin (wzory: RAG regulamin-obozu-kolonii etc.)."),
    )

    attachment_ids = fields.Many2many(
        "ir.attachment",
        "camp_regulamin_attachment_rel",
        "regulamin_id",
        "attachment_id",
        string=_("Attachments"),
        help=_("Scanned/signed PDF versions of the document."),
    )

    issued_by_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        index=True,
        tracking=True,
        string=_("Issued by (kierownik)"),
        help=_("User who issued this regulamin — normally the kierownik wypoczynku."),
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("published", "Published"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
        string=_("Status"),
        help=_("Only published regulaminy require staff acknowledgment and count for Teczka KO."),
    )

    date_published = fields.Datetime(
        readonly=True,
        string=_("Published on"),
        help=_("Timestamp of publication (set automatically by Publish)."),
    )

    # --- acknowledgments ----------------------------------------------------

    ack_ids = fields.One2many(
        "camp.regulamin.ack",
        "regulamin_id",
        string=_("Acknowledgments"),
        help=_("Per-staff acknowledgment records (kto podpisał / kto nie)."),
    )

    signed_count = fields.Integer(
        compute="_compute_ack_stats",
        string=_("Signed"),
        help=_("Number of staff members who already signed."),
    )
    total_count = fields.Integer(
        compute="_compute_ack_stats",
        string=_("Total acks"),
        help=_("Total acknowledgment records generated for this regulamin."),
    )
    all_signed = fields.Boolean(
        compute="_compute_ack_stats",
        store=True,  # stored: фільтр у search view вимагає searchable (INC staging 10.06)
        string=_("All signed"),
        help=_("True when every generated acknowledgment is signed (and at least one exists)."),
    )

    @api.depends("ack_ids.signed")
    def _compute_ack_stats(self):
        for regulamin in self:
            total = len(regulamin.ack_ids)
            signed = len(regulamin.ack_ids.filtered("signed"))
            regulamin.total_count = total
            regulamin.signed_count = signed
            regulamin.all_signed = bool(total) and signed == total

    # --- lifecycle ----------------------------------------------------------

    def action_publish(self):
        for regulamin in self:
            if regulamin.state != "draft":
                raise UserError(_("Only draft regulaminy can be published."))
        self.write({"state": "published", "date_published": fields.Datetime.now()})
        return True

    def action_archive_regulamin(self):
        self.write({"state": "archived"})
        return True

    # --- ack generation -----------------------------------------------------

    def action_generate_acks(self, event=None):
        """Create one acknowledgment per staff member of the event.

        ``event`` is required for organizer-wide templates (event_id empty);
        for event-bound regulaminy it defaults to the own event. Existing
        (regulamin, staff) pairs are skipped — safe to re-run after adding
        staff. Finished staff are excluded.
        """
        ack_model = self.env["camp.regulamin.ack"]
        created = ack_model.browse()
        for regulamin in self:
            target_event = event or regulamin.event_id
            if not target_event:
                raise UserError(
                    _(
                        "Regulamin '%(name)s' is an organizer-wide template — "
                        "pass the camp shift (event) explicitly to generate "
                        "acknowledgments.",
                        name=regulamin.name,
                    )
                )
            staff = self.env["camp.staff"].search(
                [
                    ("event_id", "=", target_event.id),
                    ("state", "!=", "finished"),
                ]
            )
            existing_staff = regulamin.ack_ids.mapped("staff_id")
            for member in staff - existing_staff:
                created |= ack_model.create(
                    {
                        "regulamin_id": regulamin.id,
                        "staff_id": member.id,
                    }
                )
        if created:
            _logger.info(
                "[camp_regulamin] Generated %d acknowledgment(s) for %d regulamin(y)",
                len(created),
                len(self),
            )
        return created

    # --- shift-start warning (NO hard block — decision TZ §4) ---------------

    @api.model
    def check_acks_for_event(self, event):
        """Return staff of ``event`` who have NOT signed every published
        regulamin applying to that event (event-bound + organizer templates).

        Deliberately NOT a ValidationError — PL law does not forbid starting
        the shift with unsigned regulaminy. Instead: a log warning + a TODO
        activity for the issuer on each affected regulamin. Teczka KO uses the
        same data to show ❌.
        """
        regulaminy = self.search(
            [
                ("state", "=", "published"),
                "|",
                ("event_id", "=", event.id),
                ("event_id", "=", False),
            ]
        )
        staff = event.staff_ids.filtered(lambda s: s.state != "finished")
        unsigned = self.env["camp.staff"].browse()
        for regulamin in regulaminy:
            signed_staff = regulamin.ack_ids.filtered("signed").mapped("staff_id")
            missing = staff - signed_staff
            if not missing:
                continue
            unsigned |= missing
            summary = _(
                "Regulamin nie podpisany przez: %(names)s (event: %(event)s)",
                names=", ".join(missing.mapped("name")),
                event=event.name,
            )
            _logger.warning(
                "[camp_regulamin] '%s': %d staff member(s) of '%s' have not signed",
                regulamin.name,
                len(missing),
                event.name,
            )
            # Avoid activity spam on repeated checks (cron / teczka refresh).
            if not regulamin.activity_ids.filtered(lambda a, s=summary: a.summary == s):
                regulamin.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary=summary,
                    user_id=(regulamin.issued_by_id or self.env.user).id,
                )
        return unsigned


# ---------------------------------------------------------------------------
# camp.regulamin.ack — staff acknowledgment (signature)
# ---------------------------------------------------------------------------


class CampRegulaminAck(models.Model):
    _name = "camp.regulamin.ack"
    _description = "Potwierdzenie zapoznania się z regulaminem (kadra)"
    _order = "regulamin_id, staff_id"
    _rec_name = "display_name"

    _sql_constraints = [
        (
            "regulamin_staff_unique",
            "UNIQUE(regulamin_id, staff_id)",
            "This staff member already has an acknowledgment for this regulamin.",
        ),
    ]

    regulamin_id = fields.Many2one(
        "camp.regulamin",
        required=True,
        index=True,
        ondelete="cascade",
        string=_("Regulamin"),
        help=_("The regulamin being acknowledged."),
    )
    staff_id = fields.Many2one(
        "camp.staff",
        required=True,
        index=True,
        ondelete="cascade",
        string=_("Staff member"),
        help=_("The staff member who must read and sign."),
    )
    event_id = fields.Many2one(
        related="staff_id.event_id",
        store=True,
        index=True,
        string=_("Camp shift (event)"),
        help=_("Shift of the staff member — used for record-rule scoping."),
    )
    user_id = fields.Many2one(
        related="staff_id.user_id",
        store=True,
        index=True,
        string=_("Staff user"),
        help=_("Login account of the staff member — the ONLY user allowed to sign."),
    )

    display_name = fields.Char(
        compute="_compute_display_name",
        string=_("Display name"),
    )

    # --- signature (immutable after signed, participant.py pattern) ---------

    signed = fields.Boolean(
        string=_("Signed"),
        help=_(
            "True after the staff member confirms they read the regulamin. "
            "The record is frozen afterwards (legal evidence)."
        ),
    )
    signed_date = fields.Datetime(
        readonly=True,
        string=_("Signed at"),
        help=_("Timestamp of signing — set automatically by action_sign()."),
    )
    signed_ip = fields.Char(
        readonly=True,
        string=_("Signed from IP"),
        help=_("IP address of the signer's browser at the moment of signing — legal evidence."),
    )

    can_sign = fields.Boolean(
        compute="_compute_can_sign",
        string=_("Can sign"),
        help=_(
            "True when the current user is the staff member's own user and the ack is unsigned."
        ),
    )

    @api.depends("regulamin_id.name", "staff_id.name")
    def _compute_display_name(self):
        for ack in self:
            ack.display_name = (
                f"{ack.regulamin_id.name or '?'} — {ack.staff_id.name or '?'}"
            )

    @api.depends("signed", "user_id")
    def _compute_can_sign(self):
        # Per-user value — non-stored on purpose (drives the Sign button).
        for ack in self:
            ack.can_sign = not ack.signed and bool(ack.user_id) and ack.user_id == self.env.user

    # --- sign gate + freeze ---------------------------------------------------

    def _check_sign_owner(self):
        """Only the staff member's OWN user may sign — nobody else, including
        kierownik/organizator (the acknowledgment is a personal declaration)."""
        for ack in self:
            if not ack.staff_id.user_id or ack.staff_id.user_id != self.env.user:
                raise UserError(
                    _(
                        "Only %(staff)s can sign this acknowledgment with their "
                        "own login. You are logged in as %(user)s.",
                        staff=ack.staff_id.name,
                        user=self.env.user.name,
                    )
                )

    def action_sign(self, ip_address=None):
        """Sign the acknowledgment as the staff member's own user."""
        self.ensure_one()
        if self.signed:
            raise UserError(_("This acknowledgment is already signed."))
        self._check_sign_owner()
        if not ip_address:
            # Best-effort IP when called from a controller/button.
            try:
                from odoo.http import request

                ip_address = request.httprequest.remote_addr if request else ""
            except RuntimeError:
                ip_address = ""
        self.write(
            {
                "signed": True,
                "signed_date": fields.Datetime.now(),
                "signed_ip": ip_address or "",
            }
        )
        # Chatter-нотатка — допоміжна; ПІДПИС (вище) — юридична дія і вже
        # відбувся. message_post падає UserError, якщо у користувача-підписанта
        # немає email (mail author) — реальний кейс для кадри (INC staging
        # 10.06, тест test_double_sign_raises). Не валимо підпис через chatter.
        try:
            self.regulamin_id.message_post(
                body=_(
                    "%(staff)s podpisał(a) zapoznanie się z regulaminem.",
                    staff=self.staff_id.name,
                ),
                author_id=self.env.user.partner_id.id,
            )
        except Exception:  # noqa: BLE001 — chatter must never block signing
            _logger.warning(
                "[camp_regulamin] chatter note skipped for ack %s (no usable author email)",
                self.id,
            )
        return True

    def write(self, vals):
        # Admin/system override — explicit emergency cases only
        # (same convention as camp.participant immutability).
        if self.env.su or self.env.user.has_group("base.group_system"):
            return super().write(vals)

        sign_fields = {"signed", "signed_date", "signed_ip"}
        if sign_fields & set(vals.keys()):
            # The signature may only ever be written by the owner
            # (action_sign goes through here too — double gate).
            self._check_sign_owner()

        # Frozen after signing: NO field may change on a signed ack.
        for ack in self:
            if ack.signed:
                raise UserError(
                    _(
                        "Acknowledgment '%(name)s' is signed and frozen — it "
                        "cannot be modified (legal evidence). Archive the "
                        "regulamin and issue a new version instead.",
                        name=ack.display_name,
                    )
                )
        return super().write(vals)


# ---------------------------------------------------------------------------
# camp.staff — "kto nie podpisał" dashboard counter
# ---------------------------------------------------------------------------


class CampStaff(models.Model):
    _inherit = "camp.staff"

    regulamin_ack_ids = fields.One2many(
        "camp.regulamin.ack",
        "staff_id",
        string=_("Regulamin acknowledgments"),
        help=_("All regulamin acknowledgments assigned to this staff member."),
    )

    unsigned_regulamin_count = fields.Integer(
        compute="_compute_unsigned_regulamin_count",
        string=_("Unsigned regulaminy"),
        help=_(
            "Number of PUBLISHED regulaminy this staff member has not signed "
            "yet — kierownik dashboard 'kto nie podpisał'."
        ),
    )

    @api.depends("regulamin_ack_ids.signed", "regulamin_ack_ids.regulamin_id.state")
    def _compute_unsigned_regulamin_count(self):
        for staff in self:
            staff.unsigned_regulamin_count = len(
                staff.regulamin_ack_ids.filtered(
                    lambda a: not a.signed and a.regulamin_id.state == "published"
                )
            )
