# Copyright 2026 Fayna Digital — Volodymyr Shevchenko
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Emergency domain — consolidated from fayna_camp_emergency.

Models:
  - camp.incident.report   Header — one row per child-incident (7-state workflow)
  - camp.incident.action   Append-only action ledger row (18 action types)
  - CampStaff (_inherit)   Adds user_id FK for incident record-rule scoping
  - EventEvent (_inherit)  Adds staff_ids reverse relation + incident counters

Legal basis:
  * Ustawa o systemie oświaty 1991, art. 92n
  * Rozp. MEN 30.03.2016 r. (Dz.U. 2016 poz. 452) §6 ust. 5
  * Ustawa o Państwowym Ratownictwie Medycznym 2006
  * Ustawa Kamilka 2024 — abuse-suspected overlay
  * BP-006 SLA timings (10s/2min/15min/30min/24h/21d)
"""

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OPEN_STATES = ("draft", "active_response", "under_investigation", "protocol_ready")


# ===========================================================================
# camp.incident.report
# ===========================================================================


class CampIncidentReport(models.Model):
    """Header model — one row per child-incident at a camp.

    Implements master TZ §2.13 + §Z BP-006 SLA logic.

    Workflow states (7):
      draft → active_response → under_investigation → protocol_ready
      → delivered → [disputed] → closed

    Immutability: once delivered/disputed/closed, only `state` and
    `protocol_pdf` may change. Deletion is permanently forbidden.
    """

    _name = "camp.incident.report"
    _description = "Camp incident report — protokół powypadkowy data"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "incident_datetime desc"
    _rec_name = "display_name"

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------

    event_id = fields.Many2one(
        "event.event",
        string=_("Camp shift"),
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
        help=_(
            "Camp event (shift) during which the incident occurred. "
            "Cannot be deleted while incident reports exist (ondelete=restrict)."
        ),
    )
    incident_datetime = fields.Datetime(
        string=_("Czas zdarzenia"),
        required=True,
        tracking=True,
        help=_(
            "When the incident happened (best estimate from witnesses). "
            "May differ from detected_at — SLA timing starts from detected_at."
        ),
    )
    detected_at = fields.Datetime(
        string=_("Czas wykrycia"),
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        help=_(
            "When camp staff first became aware of the incident. "
            "SLA timing (BP-006) starts from this moment, not incident_datetime."
        ),
    )
    location = fields.Char(
        string=_("Miejsce zdarzenia"),
        required=True,
        tracking=True,
        help=_("Where on camp grounds the incident happened."),
    )
    reporter_id = fields.Many2one(
        "res.users",
        string=_("Reporter (system user)"),
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
        help=_("System user who created the incident report."),
    )
    participant_ids = fields.Many2many(
        "camp.participant",
        relation="camp_incident_report_participant_rel",
        column1="report_id",
        column2="participant_id",
        string=_("Poszkodowani uczestnicy"),
        help=_(
            "Children affected. Many2many because mass incidents (food "
            "poisoning, group activity accident) can involve multiple kids."
        ),
    )
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
        compute_sudo=True,
    )

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    severity = fields.Selection(
        [
            ("light", "Lekki (otarcia, lekkie skręcenia)"),
            ("moderate", "Umiarkowany (głębsze rany, zwichnięcia)"),
            ("severe", "Ciężki (złamania, urazy głowy, oparzenia 2°+)"),
            ("fatal", "Śmiertelny"),
            ("mass", "Zbiorowy (≥2 dzieci)"),
            ("food_poisoning", "Zatrucie pokarmowe"),
        ],
        string=_("Severity"),
        required=True,
        tracking=True,
        index=True,
        help=_(
            "Incident severity per MEN classification. Determines which "
            "authorities must be notified and within what time window (BP-006)."
        ),
    )
    injury_type = fields.Selection(
        [
            ("sprain", "Skręcenie / zwichnięcie"),
            ("fracture", "Złamanie"),
            ("cut", "Skaleczenie / rana"),
            ("burn", "Oparzenie"),
            ("head_trauma", "Uraz głowy"),
            ("drowning", "Topnienie / zachłyśnięcie wodą"),
            ("heat_stroke", "Udar cieplny"),
            ("allergy", "Reakcja alergiczna"),
            ("poisoning", "Zatrucie"),
            ("psychological", "Sytuacja psychologiczna"),
            ("violence", "Agresja / przemoc rówieśnicza"),
            ("abuse_suspected", "Podejrzenie przemocy (Ustawa Kamilka)"),
            ("other", "Inne"),
        ],
        string=_("Injury type"),
        required=True,
        tracking=True,
        help=_(
            "Type of injury or incident. 'abuse_suspected' triggers the "
            "Ustawa Kamilka 2024 overlay: RPD must be notified within 24h."
        ),
    )

    description = fields.Text(
        string=_("Opis okoliczności"),
        required=True,
        tracking=True,
        help=_("Factual description of the circumstances. Used verbatim in the Protokół PDF."),
    )
    pre_incident_state = fields.Text(
        string=_("Stan dziecka przed zdarzeniem"),
        help=_(
            "Was the child healthy that day? Any pre-existing conditions? "
            "Relevant context for the dochodzenie powypadkowe."
        ),
    )

    # ------------------------------------------------------------------
    # Workflow state (7 states)
    # ------------------------------------------------------------------

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active_response", "Trwa reagowanie"),
            ("under_investigation", "Postępowanie wyjaśniające"),
            ("protocol_ready", "Protokół sporządzony"),
            ("delivered", "Doręczony osobom uprawnionym"),
            ("disputed", "Zakwestionowany przez rodziców"),
            ("closed", "Zakończony"),
        ],
        string=_("State"),
        default="draft",
        required=True,
        tracking=True,
        index=True,
        help=_(
            "Incident lifecycle state. Records become immutable (frozen) after "
            "reaching 'delivered', 'disputed', or 'closed'."
        ),
    )

    # ------------------------------------------------------------------
    # Action ledger
    # ------------------------------------------------------------------

    action_ids = fields.One2many(
        "camp.incident.action",
        "report_id",
        string=_("Action ledger"),
        help=_("Append-only log of every action taken during incident response."),
    )
    action_count = fields.Integer(
        string=_("# Actions"),
        compute="_compute_action_stats",
        store=True,
        compute_sudo=True,
    )

    # ------------------------------------------------------------------
    # SLA-aware computed flags (per BP-006)
    # ------------------------------------------------------------------

    first_aid_within_2min = fields.Boolean(
        string=_("✓ Pierwsza pomoc ≤ 2 min"),
        compute="_compute_sla",
        store=True,
        compute_sudo=True,
        help=_(
            "True when a 'first_aid' action was logged within 2 minutes of "
            "detected_at. AHA BLS 2025 standard (BP-006)."
        ),
    )
    safety_secured_within_15min = fields.Boolean(
        string=_("✓ Bezpieczeństwo ≤ 15 min"),
        compute="_compute_sla",
        store=True,
        compute_sudo=True,
        help=_(
            "True when first_aid + safe_location (+ paramedic_call for moderate+) "
            "were all logged within 15 minutes. Rozp. MEN §6.5 (BP-006)."
        ),
    )
    parents_notified_within_30min = fields.Boolean(
        string=_("✓ Rodzice ≤ 30 min"),
        compute="_compute_sla",
        store=True,
        compute_sudo=True,
        help=_("True when parent_notified action logged within 30 minutes of detected_at."),
    )
    authorities_notified_within_24h = fields.Boolean(
        string=_("✓ Władze ≤ 24 h"),
        compute="_compute_sla",
        store=True,
        compute_sudo=True,
        help=_(
            "True when all required authority notifications (kurator always; "
            "sanepid for food_poisoning; prokurator for severe/fatal/mass; "
            "RPD for abuse_suspected) were logged within 24h. Art. 92n (BP-006)."
        ),
    )
    sla_breaches = fields.Char(
        string=_("SLA breaches"),
        compute="_compute_sla",
        store=True,
        compute_sudo=True,
        help=_(
            "Comma-separated phase names that missed their SLA target. "
            "Used by admin_dashboard for red-badge alerts."
        ),
    )

    # ------------------------------------------------------------------
    # Submission / archival
    # ------------------------------------------------------------------

    protocol_pdf = fields.Binary(
        string=_("Protokół powypadkowy (PDF)"),
        attachment=True,
        help=_("Signed PDF of the final accident protocol. Attached after action_deliver()."),
    )
    submitted_at = fields.Datetime(
        string=_("Delivered at"),
        readonly=True,
        tracking=True,
        help=_("Timestamp when the protocol was formally delivered to authorised parties."),
    )
    submitted_by_id = fields.Many2one(
        "res.users",
        string=_("Delivered by"),
        readonly=True,
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Ustawa Kamilka 2024 — abuse-suspected overlay (§2.14)
    # ------------------------------------------------------------------

    rpd_notified = fields.Boolean(
        string=_("RPD powiadomiony (Ustawa Kamilka)"),
        compute="_compute_rpd",
        store=True,
        compute_sudo=True,
        tracking=True,
        help=_(
            "Rzecznik Praw Dziecka notified per Ustawa Kamilka 2024. "
            "Computed automatically when an action of type 'rpd_notified' is "
            "logged in the action ledger. Required when injury_type == "
            "'abuse_suspected'."
        ),
    )
    rpd_notification_date = fields.Datetime(
        string=_("Data powiadomienia RPD"),
        compute="_compute_rpd",
        store=True,
        compute_sudo=True,
        tracking=True,
        readonly=True,
        help=_(
            "Datetime when RPD was formally notified (drawn from the "
            "earliest rpd_notified action ledger entry). Set automatically."
        ),
    )

    # ------------------------------------------------------------------
    # Protokół content (filled via generate-protokół wizard)
    # ------------------------------------------------------------------

    wnioski = fields.Text(
        string=_("Wnioski dochodzenia powypadkowego"),
        tracking=True,
        help=_(
            "Kierownik's conclusions of the dochodzenie powypadkowe: "
            "what happened, why, what was done, what to change going forward. "
            "Embedded verbatim in the Protokół PDF Section 6."
        ),
    )
    witness_name = fields.Char(
        string=_("Naoczny świadek — imię i nazwisko"),
        tracking=True,
        help=_("Full name of the primary eyewitness to the incident."),
    )
    witness_statement = fields.Text(
        string=_("Oświadczenie świadka"),
        tracking=True,
        help=_("Verbatim statement from the witness. Embedded in Protokół PDF."),
    )
    witness_signature = fields.Binary(
        string=_("Podpis świadka"),
        attachment=True,
        help=_("Canvas/scanned signature of the witness confirming their statement."),
    )

    # ==================================================================
    # Computes
    # ==================================================================

    @api.depends("event_id.name", "incident_datetime", "severity")
    def _compute_display_name(self):
        for rec in self:
            if rec.incident_datetime and rec.event_id:
                date_str = rec.incident_datetime.strftime("%Y-%m-%d %H:%M")
                rec.display_name = f"{date_str} — {rec.event_id.name} ({rec.severity or '?'})"
            else:
                rec.display_name = _("Draft incident")

    @api.depends("action_ids")
    def _compute_action_stats(self):
        for rec in self:
            rec.action_count = len(rec.action_ids)

    @api.depends(
        "detected_at",
        "severity",
        "action_ids",
        "action_ids.action_type",
        "action_ids.performed_at",
    )
    def _compute_sla(self):
        for rec in self:
            t0 = rec.detected_at
            actions = rec.action_ids
            if not t0:
                rec.first_aid_within_2min = False
                rec.safety_secured_within_15min = False
                rec.parents_notified_within_30min = False
                rec.authorities_notified_within_24h = False
                rec.sla_breaches = ""
                continue

            # First aid within 2 minutes
            first_aid = actions.filtered(
                lambda a, _t0=t0: a.action_type == "first_aid"
                and a.performed_at
                and (a.performed_at - _t0) <= timedelta(minutes=2)
            )
            rec.first_aid_within_2min = bool(first_aid)

            # Safety secured ≤ 15 min: needs first_aid + safe_location +
            # paramedic_call (paramedic only required for moderate+).
            need_paramedic = rec.severity not in ("light",)
            safe_loc = actions.filtered(
                lambda a, _t0=t0: a.action_type == "safe_location"
                and a.performed_at
                and (a.performed_at - _t0) <= timedelta(minutes=15)
            )
            paramedic = actions.filtered(
                lambda a, _t0=t0: a.action_type == "paramedic_call"
                and a.performed_at
                and (a.performed_at - _t0) <= timedelta(minutes=15)
            )
            rec.safety_secured_within_15min = bool(
                first_aid and safe_loc and (paramedic if need_paramedic else True)
            )

            # Parents within 30 min
            parents = actions.filtered(
                lambda a, _t0=t0: a.action_type == "parent_notified"
                and a.performed_at
                and (a.performed_at - _t0) <= timedelta(minutes=30)
            )
            rec.parents_notified_within_30min = bool(parents)

            # Authorities within 24h: kurator always; sanepid only on
            # food_poisoning; prokurator on severe/fatal/mass; rpd on abuse_suspected.
            cutoff = t0 + timedelta(hours=24)

            kurator = actions.filtered(
                lambda a, _c=cutoff: a.action_type == "kurator_notified"
                and a.performed_at
                and a.performed_at <= _c
            )
            sanepid_needed = rec.severity == "food_poisoning"
            prokurator_needed = rec.severity in ("severe", "fatal", "mass")
            rpd_needed = rec.injury_type == "abuse_suspected"

            sanepid = (
                actions.filtered(
                    lambda a, _c=cutoff: a.action_type == "sanepid_notified"
                    and a.performed_at
                    and a.performed_at <= _c
                )
                if sanepid_needed
                else True
            )
            prokurator = (
                actions.filtered(
                    lambda a, _c=cutoff: a.action_type == "prokurator_notified"
                    and a.performed_at
                    and a.performed_at <= _c
                )
                if prokurator_needed
                else True
            )
            rpd = (
                actions.filtered(
                    lambda a, _c=cutoff: a.action_type == "rpd_notified"
                    and a.performed_at
                    and a.performed_at <= _c
                )
                if rpd_needed
                else True
            )

            rec.authorities_notified_within_24h = bool(kurator and sanepid and prokurator and rpd)

            # Build breach list
            breaches = []
            if not rec.first_aid_within_2min:
                breaches.append("first_aid_2min")
            if not rec.safety_secured_within_15min:
                breaches.append("safety_15min")
            if not rec.parents_notified_within_30min:
                breaches.append("parents_30min")
            if not rec.authorities_notified_within_24h:
                breaches.append("authorities_24h")
            rec.sla_breaches = ",".join(breaches)

    @api.depends(
        "action_ids",
        "action_ids.action_type",
        "action_ids.performed_at",
    )
    def _compute_rpd(self):
        """Compute RPD notification status from action ledger.

        When a camp staff member logs an 'rpd_notified' action, this
        computed field flips to True and records the earliest such timestamp.
        Per Ustawa Kamilka 2024 — required for abuse_suspected cases.
        """
        for rec in self:
            rpd_actions = rec.action_ids.filtered(
                lambda a: a.action_type == "rpd_notified" and a.performed_at
            )
            if rpd_actions:
                earliest = min(rpd_actions.mapped("performed_at"))
                rec.rpd_notified = True
                rec.rpd_notification_date = earliest
            else:
                rec.rpd_notified = False
                rec.rpd_notification_date = False

    # ==================================================================
    # Notifications
    # ==================================================================

    def _notify_managers(self, body):
        """Post a chatter message and notify all emergency managers.

        Falls back gracefully if the group does not exist (test isolation).
        """
        group = self.env.ref("fayna_camp_portal.group_emergency_manager", raise_if_not_found=False)
        partner_ids = group.users.mapped("partner_id").ids if group else []
        for rec in self:
            rec.message_post(
                body=body,
                partner_ids=partner_ids,
                message_type="comment",
                subtype_xmlid="mail.mt_comment",
            )

    # ==================================================================
    # Workflow actions
    # ==================================================================

    def action_start_response(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft reports can move to active response."))
            rec.state = "active_response"
        self._notify_managers(_("Incident is now in active response — immediate action required."))

    def action_start_investigation(self):
        for rec in self:
            if rec.state != "active_response":
                raise UserError(_("Active response must complete before investigation begins."))
            rec.state = "under_investigation"

    def action_protocol_ready(self):
        for rec in self:
            if rec.state != "under_investigation":
                raise UserError(_("Investigation must be in progress."))
            if not rec.action_ids:
                raise UserError(_("Action ledger empty — nothing to summarise."))
            rec.state = "protocol_ready"
        self._notify_managers(_("Protocol is ready — please review and deliver to parties."))

    def action_deliver(self):
        for rec in self:
            if rec.state != "protocol_ready":
                raise UserError(_("Protocol must be ready before delivery."))
            rec.write(
                {
                    "state": "delivered",
                    "submitted_at": fields.Datetime.now(),
                    "submitted_by_id": self.env.user.id,
                }
            )
        self._notify_managers(_("Protocol has been delivered to authorised parties."))

    def action_dispute(self):
        for rec in self:
            if rec.state != "delivered":
                raise UserError(_("Disputes only on delivered protocols."))
            rec.state = "disputed"

    def action_close(self):
        for rec in self:
            if rec.state not in ("delivered", "disputed"):
                raise UserError(_("Close from delivered or disputed only."))
            rec.state = "closed"

    # ==================================================================
    # Cron: remind stale incidents
    # ==================================================================

    def action_cron_remind_stale_incidents(self):
        """Daily cron — post chatter reminder on incidents open > 30 days.

        Does NOT automatically close them: legal evidence retention means
        only a human manager can close an incident.
        """
        cutoff = fields.Datetime.now() - timedelta(days=30)
        stale_states = ("draft", "active_response", "under_investigation", "protocol_ready")
        stale = self.search(
            [
                ("state", "in", stale_states),
                ("detected_at", "<=", cutoff),
            ]
        )
        for rec in stale:
            rec._notify_managers(
                _(
                    "Stale incident alert: this report has been open for more "
                    "than 30 days (detected: %(date)s, state: %(state)s). "
                    "Please review and take action or close the report.",
                    date=rec.detected_at,
                    state=rec.state,
                )
            )

    # ==================================================================
    # ORM overrides
    # ==================================================================

    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._notify_managers(
                _(
                    "New incident report created: %(name)s "
                    "(severity: %(severity)s, location: %(location)s). "
                    "Please review and start the response.",
                    name=rec.display_name,
                    severity=rec.severity,
                    location=rec.location,
                )
            )
        return records

    # ==================================================================
    # Immutable ledger — frozen after delivery
    # ==================================================================

    _MUTABLE_AFTER_DELIVERY = {"state", "protocol_pdf"}

    def write(self, vals):
        """Block modifications to frozen records.

        After a protocol reaches 'delivered', 'disputed', or 'closed' state
        only `state` and `protocol_pdf` may change. All other fields are
        frozen as legal evidence (Ustawa o systemie oświaty, art. 92n).
        """
        for rec in self:
            if rec.state in ("delivered", "disputed", "closed"):
                forbidden = set(vals) - self._MUTABLE_AFTER_DELIVERY
                if forbidden:
                    raise UserError(
                        _(
                            "Delivered protocol is frozen — cannot modify %(fields)s",
                            fields=", ".join(sorted(forbidden)),
                        )
                    )
        return super().write(vals)

    def unlink(self):
        """Permanently block deletion of delivered/closed incident reports.

        Legal evidence retention — records must survive 7-year PL law retention
        period (Ustawa o systemie oświaty + RODO art. 17(3)(b)).
        """
        if any(r.state in ("delivered", "disputed", "closed") for r in self):
            raise UserError(
                _(
                    "Delivered/closed incident reports cannot be deleted "
                    "(legal evidence retention)."
                )
            )
        return super().unlink()


# ===========================================================================
# camp.incident.action
# ===========================================================================


class CampIncidentAction(models.Model):
    """Action ledger row — one entry per concrete action taken during incident.

    Captures: action_type, actor, exact timestamp, contact_method, receiver
    identity, signature (canvas), notes.

    Append-only invariant: only `notes`, `signature`, `receiver_response` may
    be updated after creation. Once the parent report reaches 'delivered' /
    'disputed' / 'closed', even those fields are frozen (full audit trail).
    """

    _name = "camp.incident.action"
    _description = "Single action in incident response ledger"
    _inherit = ["mail.thread"]
    _order = "performed_at, id"

    report_id = fields.Many2one(
        "camp.incident.report",
        string=_("Incident report"),
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
        help=_("Parent incident report this action belongs to."),
    )
    state = fields.Selection(
        related="report_id.state",
        store=True,
        string=_("Report state"),
        help=_("Denormalised state from the parent report. Used for immutability guards."),
    )

    action_type = fields.Selection(
        [
            ("first_aid", "Pierwsza pomoc"),
            ("paramedic_call", "Wezwanie pogotowia / 112"),
            ("paramedic_arrived", "Pogotowie na miejscu"),
            ("hospital_transfer", "Przewóz do szpitala"),
            ("safe_location", "Zabezpieczenie miejsca zdarzenia"),
            ("parent_notified", "Powiadomienie rodziców"),
            ("organizer_notified", "Powiadomienie organizatora"),
            ("kierownik_notified", "Powiadomienie kierownika"),
            ("kurator_notified", "Powiadomienie kuratora oświaty"),
            ("sanepid_notified", "Powiadomienie sanepidu"),
            ("prokurator_notified", "Powiadomienie prokuratora"),
            ("insurance_notified", "Powiadomienie ubezpieczyciela"),
            ("rpd_notified", "Powiadomienie RPD (Ustawa Kamilka)"),
            ("evidence_secured", "Zabezpieczenie dowodów / fotografii"),
            ("witness_interview", "Przesłuchanie świadków"),
            ("protocol_drafted", "Sporządzenie protokołu"),
            ("protocol_delivered", "Doręczenie protokołu"),
            ("other", "Inne"),
        ],
        string=_("Action type"),
        required=True,
        tracking=True,
        index=True,
        help=_(
            "18 action types covering the full BP-006 emergency response protocol. "
            "'rpd_notified' triggers the Ustawa Kamilka 2024 computed overlay on the parent report."
        ),
    )

    actor_id = fields.Many2one(
        "res.users",
        string=_("Actor (system user)"),
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True,
        help=_("System user who performed this action. Set on creation, immutable."),
    )
    performed_at = fields.Datetime(
        string=_("Performed at"),
        required=True,
        default=fields.Datetime.now,
        readonly=True,
        tracking=True,
        help=_(
            "Exact moment the action was performed. "
            "Used for SLA computation on the parent incident report. Immutable."
        ),
    )
    notes = fields.Text(
        string=_("Notes"),
        tracking=True,
        help=_("Free-text notes about this specific action. May be updated after creation."),
    )
    signature = fields.Binary(
        string=_("Signature"),
        attachment=True,
        help=_(
            "Optional canvas signature for high-stakes actions "
            "(parent notifications, protocol delivery, etc.)."
        ),
    )
    contact_method = fields.Selection(
        [
            ("phone", "Telefon"),
            ("sms", "SMS"),
            ("email", "Email"),
            ("in_person", "Osobiście"),
            ("written", "Pisemnie"),
        ],
        string=_("Contact method"),
        help=_(
            "How the notification was made. Relevant for parent / authority actions. "
            "Immutable after creation."
        ),
    )
    receiver_name = fields.Char(
        string=_("Adresat (osoba/instytucja)"),
        help=_(
            "Free-text — who received the notification: parent name, kurator "
            "office name, paramedic dispatcher ID, etc."
        ),
    )
    receiver_response = fields.Text(
        string=_("Odpowiedź adresata"),
        help=_(
            "Summary of the receiver's response or confirmation. May be updated after creation."
        ),
    )

    # ------------------------------------------------------------------
    # Append-only invariants
    # ------------------------------------------------------------------

    _MUTABLE_FIELDS = {"signature", "notes", "receiver_response"}

    def write(self, vals):
        """Enforce append-only invariant.

        Only `notes`, `signature`, `receiver_response` may be updated.
        All other fields are immutable after creation to preserve the
        audit trail. Once the parent report is delivered/closed, even
        these three fields are frozen.
        """
        for rec in self:
            forbidden = set(vals) - self._MUTABLE_FIELDS
            if forbidden:
                raise UserError(
                    _(
                        "Incident action is append-only. Cannot modify: %(fields)s",
                        fields=", ".join(sorted(forbidden)),
                    )
                )
            if rec.state in ("delivered", "disputed", "closed"):
                raise UserError(_("Cannot modify actions on a delivered/closed incident report."))
        return super().write(vals)

    def unlink(self):
        if any(rec.state in ("delivered", "disputed", "closed") for rec in self):
            raise UserError(
                _(
                    "Cannot delete actions on a delivered/closed report "
                    "(legal evidence retention)."
                )
            )
        return super().unlink()


# ===========================================================================
# camp.staff (_inherit)  — adds user_id for record-rule scoping
# ===========================================================================


class CampStaff(models.Model):
    """Extend camp.staff with a res.users link.

    `fayna_camp_operations.camp.staff` ships without a `user_id` Many2one to
    res.users. The incident-report record rule needs this link so a responder
    sees only incidents from events where they're on the staff roster.

    If `fayna_camp_dziennik_zajec` is also installed, both modules declare
    the same field via `_inherit` — Odoo merges idempotently, no conflict.
    """

    _inherit = "camp.staff"

    user_id = fields.Many2one(
        "res.users",
        string=_("System user"),
        index=True,
        help=_(
            "Login account this staff member uses. Required for record-rule "
            "scoping in incident reports (responder sees own events only)."
        ),
    )


# ===========================================================================
# event.event (_inherit) — adds staff reverse relation + incident counters
# ===========================================================================


class EventEvent(models.Model):
    """Extend event.event with staff reverse relation and incident counters.

    Adds `staff_ids` so the record-rule domain
    `event_id.staff_ids.user_id == user.id` resolves. `fayna_camp_operations`
    itself doesn't declare the reverse (only camp.staff.event_id forward).

    Incident counter fields allow the admin dashboard and event kanban to
    show red-badge alerts without a separate query.
    """

    _inherit = "event.event"

    staff_ids = fields.One2many(
        "camp.staff",
        "event_id",
        string=_("Camp staff (kadra)"),
    )
    incident_report_ids = fields.One2many(
        "camp.incident.report",
        "event_id",
        string=_("Incident reports"),
    )
    incident_count = fields.Integer(
        string=_("# incidents"),
        compute="_compute_incident_stats",
        store=True,
        compute_sudo=True,
    )
    incident_open_count = fields.Integer(
        string=_("# open incidents"),
        compute="_compute_incident_stats",
        store=True,
        compute_sudo=True,
        help=_("Incidents in states: draft, active_response, under_investigation, protocol_ready."),
    )
    incident_sla_breach_count = fields.Integer(
        string=_("# SLA breaches"),
        compute="_compute_incident_stats",
        store=True,
        compute_sudo=True,
        help=_("Incidents with at least one SLA breach (non-empty sla_breaches field)."),
    )

    @api.depends(
        "incident_report_ids",
        "incident_report_ids.state",
        "incident_report_ids.sla_breaches",
    )
    def _compute_incident_stats(self):
        for event in self:
            reports = event.incident_report_ids
            event.incident_count = len(reports)
            event.incident_open_count = len(reports.filtered(lambda r: r.state in _OPEN_STATES))
            event.incident_sla_breach_count = len(reports.filtered(lambda r: r.sla_breaches))
