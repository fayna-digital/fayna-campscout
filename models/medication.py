# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""camp.medication.* — Rejestr leków: przyjęcie → grafik → wydanie → pominięcie.

Облік медичних препаратів у таборі: батько здає ліки медику (з живим підписом
згоди за патерном camp.escort — Binary PNG + signed_date/ip/by + RODO log),
система генерує грудкований графік видачі (camp.medication.schedule), медик
відмічає «Wydano»/«Pominięto» з планшета, cron ловить прострочені pending →
missed → mail.activity керівнику; для критичних ліків (is_critical, кейс
Tsybulko — психіатричні препарати) додатково SMS CRITICAL через
fayna.sms.dispatcher.

Models:
  - camp.medication.registry  Przyjęcie leku od rodzica — one per (child, drug,
                              course). Structured dose scheme (frequency ×
                              duration × times), NOT medical dosing in mg/kg.
  - camp.medication.schedule  One row per planned dose. pending → issued|missed.

RODO art. 9: medication_name / dosage_* / status / notes are special-category
health data — field-level groups= (same gate as camp.participant art.9 fields,
see art9_security.py + test_art9_access.py) on top of model ACL (medical
officer + kierownik only) and event-scoped record rules.

TZ: DevJournal/projects/campscout/learning-corpus-2026/tz-drafts/
TZ-DRAFT-tema-2-rejestr-likiv.md (гейт Fable 2026-08-03 — canvas-підпис
замість Odoo Sign, handed_by = res.partner, SMS CRITICAL для is_critical).
"""

import logging
from datetime import datetime, time, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Same field-level gate as the 21 art.9 fields on camp.participant (§6l-final):
# medical officer / kierownik / wychowawca / sales via group_medical_access
# implied chain + portal parent (scoped to own child by model ACL — portal has
# NO access rows on these models, so the gate matters for backend roles only).
_ART9_GROUPS = "fayna_camp_portal.group_medical_access,base.group_portal"

# Pending dose is considered missed this long after its scheduled time.
# Grace absorbs "handed out 20 minutes late during supper" — real camp life.
MISSED_GRACE_HOURS = 1

# Kierownik has this long to confirm (mark done) the missed-dose activity
# before a repeat alert with raised urgency is created (T4-K).
ESCALATION_HOURS = 24

# When dosage_times is empty: first/last dose anchors for the generated grid
# (children's camp day — no night doses without an explicit time list).
_FIRST_DOSE_HOUR = 8
_LAST_DOSE_HOUR = 20


# ===========================================================================
# camp.medication.registry — przyjęcie leku od rodzica
# ===========================================================================


class CampMedicationRegistry(models.Model):
    """Przyjęcie leku — one record per (child, medication, course).

    Workflow: draft → active (grafik generated) → closed. Parent consent
    signature (canvas pattern, camp.escort) is required BEFORE activation —
    RODO art. 9(2)(a) legal basis for processing the child's health data.
    Dose-scheme change while active regenerates pending schedule rows only;
    issued/missed rows are historical evidence and stay untouched.
    """

    _name = "camp.medication.registry"
    _description = "Rejestr leków — przyjęcie od rodzica (RODO art. 9)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "received_date desc, id desc"
    _rec_name = "name"

    # NB: name deliberately contains NO medication name — it shows up in
    # breadcrumbs, activities and logs read by roles without art.9 fields.
    name = fields.Char(
        compute="_compute_name",
        store=True,
        compute_sudo=True,
        string=_("Reference"),
    )

    # ------------------------------------------------------------------
    # Linkage (T5-K)
    # ------------------------------------------------------------------

    participant_id = fields.Many2one(
        "camp.participant",
        string=_("Child (participant)"),
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    event_id = fields.Many2one(
        "event.event",
        string=_("Turnus (camp shift)"),
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
        help=_(
            "Camp shift during which the medication is administered. "
            "Drives record-rule scoping: medic sees own camps only."
        ),
    )
    incident_card_id = fields.Many2one(
        "camp.incident.card",
        string=_("Karta Wypadku (if any)"),
        index=True,
        ondelete="set null",
        tracking=True,
        help=_(
            "Related accident card — e.g. allergy medication after an insect "
            "bite, or the investigation card of a missed-course incident."
        ),
    )
    dziennik_id = fields.Many2one(
        "fayna.camp.dziennik",
        string=_("Dziennik zajęć"),
        index=True,
        ondelete="set null",
        help=_("Group dziennik of the child — reporting linkage (Załącznik 5)."),
    )

    # ------------------------------------------------------------------
    # Medication + structured dose scheme (RODO art. 9 — field-gated)
    # ------------------------------------------------------------------

    medication_name = fields.Char(
        string=_("Medication"),
        required=True,
        tracking=True,
        groups=_ART9_GROUPS,
        help=_("RODO art. 9 — name of the preparation as handed by the parent."),
    )
    quantity = fields.Float(
        string=_("Quantity received"),
        help=_("How much was physically handed over (count of units)."),
    )
    unit = fields.Selection(
        [("tab", "tabl."), ("ml", "ml"), ("mg", "mg")],
        string=_("Unit"),
        default="tab",
    )
    dosage_frequency = fields.Integer(
        string=_("Doses per day"),
        default=1,
        required=True,
        tracking=True,
        groups=_ART9_GROUPS,
        help=_("RODO art. 9 — how many times a day, per the doctor's scheme."),
    )
    dosage_duration = fields.Integer(
        string=_("Course duration (days)"),
        default=1,
        required=True,
        tracking=True,
        groups=_ART9_GROUPS,
        help=_("RODO art. 9 — course length in days, counted from reception."),
    )
    dosage_interval = fields.Integer(
        string=_("Interval between doses (hours)"),
        tracking=True,
        groups=_ART9_GROUPS,
        help=_(
            "RODO art. 9 — optional. Used to spread doses when no explicit "
            "times are given (first dose at 08:00)."
        ),
    )
    dosage_times = fields.Char(
        string=_("Dose times"),
        tracking=True,
        groups=_ART9_GROUPS,
        help=_(
            'RODO art. 9 — explicit times, comma-separated, e.g. "08:00, 20:00". '
            "Count must match doses per day. Wins over the interval."
        ),
    )
    is_critical = fields.Boolean(
        string=_("Critical medication"),
        tracking=True,
        help=_(
            "Life-critical course (psychiatric, cardiac, insulin…). A missed "
            "dose triggers SMS CRITICAL to the kierownik via fayna.sms."
            "dispatcher — mail.activity alone is not enough (kejs Tsybulko)."
        ),
    )

    # ------------------------------------------------------------------
    # Reception
    # ------------------------------------------------------------------

    received_date = fields.Datetime(
        string=_("Received on"),
        default=fields.Datetime.now,
        required=True,
        tracking=True,
    )
    received_by = fields.Many2one(
        "camp.staff",
        string=_("Received by (staff)"),
        tracking=True,
        help=_("Medical officer who physically accepted the medication."),
    )
    handed_by = fields.Many2one(
        "res.partner",
        string=_("Handed by (parent)"),
        tracking=True,
        help=_("Parent / legal guardian who handed the medication over."),
    )

    # ── Живий підпис батьків (патерн camp.escort / qualification_signature) ──
    parent_signature = fields.Binary(string=_("Parent signature"), attachment=True)
    signed_date = fields.Datetime(string=_("Signed on"), readonly=True)
    signed_ip = fields.Char(string=_("Signature IP"), readonly=True)
    signed_by = fields.Many2one("res.users", string=_("Signed by"), readonly=True)
    rodo_consent_id = fields.Many2one(
        "fayna.rodo.consent.log", string=_("RODO consent log"), readonly=True
    )

    state = fields.Selection(
        [("draft", "Draft"), ("active", "Active"), ("closed", "Closed")],
        string=_("Status"),
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )

    schedule_ids = fields.One2many(
        "camp.medication.schedule",
        "registry_id",
        string=_("Issue schedule"),
    )

    @api.depends("participant_id.display_name", "received_date")
    def _compute_name(self):
        for rec in self:
            who = rec.participant_id.display_name or _("Medication")
            day = (
                fields.Date.to_string(rec.received_date.date())
                if rec.received_date
                else ""
            )
            rec.name = "{} — leki {}".format(who, day).strip()

    @api.onchange("participant_id")
    def _onchange_participant_id(self):
        """Propose the child's latest camp shift so the medic types less."""
        if self.participant_id and not self.event_id:
            registration = self.participant_id.registration_ids[:1]
            if registration:
                self.event_id = registration.event_id

    # ------------------------------------------------------------------
    # Constraints — scheme must be generatable (critique PR-6 #2)
    # ------------------------------------------------------------------

    @api.constrains("dosage_frequency", "dosage_duration", "dosage_interval", "dosage_times")
    def _check_dose_scheme(self):
        for rec in self:
            if rec.dosage_frequency < 1:
                raise ValidationError(_("Doses per day must be at least 1."))
            if rec.dosage_duration < 1:
                raise ValidationError(_("Course duration must be at least 1 day."))
            if rec.dosage_interval and not 0 < rec.dosage_interval <= 24:
                raise ValidationError(_("Dose interval must be between 1 and 24 hours."))
            times = rec._parse_dose_times()
            if rec.dosage_times and len(times) != rec.dosage_frequency:
                raise ValidationError(
                    _(
                        "Dose times (%(times)s) do not match doses per day (%(freq)s).",
                        times=rec.dosage_times,
                        freq=rec.dosage_frequency,
                    )
                )

    def _parse_dose_times(self):
        """Parse dosage_times ('08:00, 20:00') → sorted list of datetime.time.

        Bad tokens raise ValidationError so the constraint reports them to the
        medic instead of silently generating a wrong grid.
        """
        self.ensure_one()
        if not self.dosage_times:
            return []
        parsed = []
        for token in self.dosage_times.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                hour, minute = token.split(":")
                parsed.append(time(int(hour), int(minute)))
            except ValueError as exc:
                raise ValidationError(
                    _('Invalid dose time "%(token)s" — expected HH:MM.', token=token)
                ) from exc
        return sorted(parsed)

    # ------------------------------------------------------------------
    # Signature — canvas pattern (camp.escort.action_sign)
    # ------------------------------------------------------------------

    def action_sign(self, ip_address=None, signature=None, signed_by_id=None):
        """Атомарно: фіксує підпис згоди + лінкує RODO consent (патерн escort)."""
        self.ensure_one()
        if self.signed_date:
            raise UserError(_("Consent is already signed."))
        if not signature and not self.parent_signature:
            raise ValidationError(_("Parent signature is required."))

        consent = (
            self.env["fayna.rodo.consent.log"]
            .sudo()
            .record_consent(
                purpose="transactional",
                channel="website",
                partner_id=self.handed_by.id
                or self.participant_id.parent_partner_id.id
                or self.participant_id.partner_id.id,
                exact_response="medication_consent_signed",
                source="website_form",
                legal_basis="consent",
                evidence_model="camp.medication.registry",
                evidence_id=self.id,
            )
        )
        vals = {
            "signed_date": fields.Datetime.now(),
            "signed_ip": ip_address or "",
            "signed_by": signed_by_id or self.env.user.id,
            "rodo_consent_id": consent.id,
        }
        if signature:
            # base64 PNG без префікса data:image/png;base64, — Odoo Binary raw.
            vals["parent_signature"] = signature
        self.write(vals)
        self._log_medical_access(reason="consent signed")
        _logger.info(
            "fayna_camp_portal.medication.sign: registry=%s participant=%s ip=%s consent=%s",
            self.id,
            self.participant_id.id,
            ip_address,
            consent.id,
        )
        return True

    # ------------------------------------------------------------------
    # State machine + schedule generation (T2-K)
    # ------------------------------------------------------------------

    def action_activate(self):
        """draft → active: parent consent gate + full grid generation."""
        for rec in self:
            if rec.state != "draft":
                continue
            if not rec.rodo_consent_id:
                # Art. 9(2)(a): no signed parent consent → no processing.
                raise UserError(
                    _("Sign the parent consent before activating the course.")
                )
            rec.state = "active"
            self.env["camp.medication.schedule"].create(rec._schedule_vals())
            rec._log_medical_access(reason="course activated")
        return True

    def action_close(self):
        for rec in self:
            if rec.state != "active":
                continue
            rec.state = "closed"
        return True

    def _dose_times_of_day(self):
        """Resolve the daily dose times from the structured scheme.

        Priority: explicit dosage_times > dosage_interval (from 8:00) >
        even spread across the camp day (8:00–20:00). Always returns exactly
        dosage_frequency entries — guaranteed by _check_dose_scheme.
        """
        self.ensure_one()
        times = self._parse_dose_times()
        if times:
            return times
        if self.dosage_frequency == 1:
            return [time(_FIRST_DOSE_HOUR, 0)]
        if self.dosage_interval:
            step = self.dosage_interval
        else:
            step = max(
                1, (_LAST_DOSE_HOUR - _FIRST_DOSE_HOUR) // (self.dosage_frequency - 1)
            )
        return [
            time(min(_FIRST_DOSE_HOUR + i * step, 23), 0)
            for i in range(self.dosage_frequency)
        ]

    def _schedule_vals(self):
        """Full course grid: dosage_duration days × dosage_frequency doses."""
        self.ensure_one()
        start_day = self.received_date.date()
        vals = []
        for day_no in range(self.dosage_duration):
            day = start_day + timedelta(days=day_no)
            for dose_time in self._dose_times_of_day():
                vals.append(
                    {
                        "registry_id": self.id,
                        "scheduled_time": datetime.combine(day, dose_time),
                    }
                )
        return vals

    def _regenerate_pending(self):
        """Scheme changed: rebuild pending rows, keep issued/missed history.

        Handled (issued/missed) rows are legal evidence — untouched. New grid
        is generated for the whole course, then slots at-or-before the last
        handled slot are dropped so history is not duplicated (T2-K test:
        change 2→3×/day keeps the issued rows and re-plans the rest).
        """
        for rec in self:
            pending = rec.schedule_ids.filtered(lambda s: s.status == "pending")
            handled = rec.schedule_ids - pending
            pending.unlink()
            cutoff = max(handled.mapped("scheduled_time"), default=False)
            vals = [
                v
                for v in rec._schedule_vals()
                if not cutoff or v["scheduled_time"] > cutoff
            ]
            self.env["camp.medication.schedule"].create(vals)
            _logger.info(
                "fayna_camp_portal.medication.regen: registry=%s pending=%s handled=%s",
                rec.id,
                len(vals),
                len(handled),
            )

    _SCHEME_FIELDS = frozenset(
        {
            "dosage_frequency",
            "dosage_duration",
            "dosage_interval",
            "dosage_times",
            "received_date",
        }
    )

    def write(self, vals):
        # Signed consent PNG is legal evidence — no silent replacement.
        if "parent_signature" in vals and not (
            self.env.su or self.env.user.has_group("base.group_system")
        ):
            for rec in self:
                if rec.signed_date:
                    raise UserError(
                        _("Consent %(name)s is signed — signature cannot be replaced.")
                        % {"name": rec.display_name}
                    )
        res = super().write(vals)
        if self._SCHEME_FIELDS & set(vals.keys()):
            self.filtered(lambda r: r.state == "active")._regenerate_pending()
        return res

    # ------------------------------------------------------------------
    # RODO art. 30 — access trail (camp.admin.access.log, T6-K)
    # ------------------------------------------------------------------

    def _log_medical_access(self, reason=""):
        """Append an immutable access-log row for each significant touch.

        NB: read()-override logging was rejected — same ≥3-stop as in
        art9_security.py (ORM fetch path is not reliably interceptable and
        would log every list rendering). We log the meaningful processing
        events instead: sign / activate / issue / miss.
        """
        log_model = self.env["camp.admin.access.log"].sudo()
        for rec in self:
            log_model.create(
                {
                    "user_id": self.env.user.id,
                    "impersonated_role": "medication",
                    "medication_registry_id": rec.id,
                    "reason": reason,
                }
            )


# ===========================================================================
# camp.medication.schedule — one row per planned dose
# ===========================================================================


class CampMedicationSchedule(models.Model):
    """Planned dose. pending → issued (medic tapped 'Wydano') | missed.

    Missed detection is cron-driven (_cron_mark_missed_and_alert) with a
    manual 'Pominięto' button for the medic. Alerts land on the REGISTRY
    (mail.activity for the kierownik) so 20 missed doses of one course make
    one thread, not 20.
    """

    _name = "camp.medication.schedule"
    _description = "Grafik wydań leku (RODO art. 9)"
    _inherit = ["mail.thread"]
    _order = "scheduled_time, id"

    registry_id = fields.Many2one(
        "camp.medication.registry",
        string=_("Medication registry"),
        required=True,
        index=True,
        ondelete="cascade",
    )
    participant_id = fields.Many2one(
        related="registry_id.participant_id",
        store=True,
        index=True,
        string=_("Child (participant)"),
    )
    event_id = fields.Many2one(
        related="registry_id.event_id",
        store=True,
        index=True,
        string=_("Turnus (camp shift)"),
    )
    is_critical = fields.Boolean(
        related="registry_id.is_critical",
        store=True,
        string=_("Critical medication"),
    )
    scheduled_time = fields.Datetime(
        string=_("Scheduled at"),
        required=True,
        index=True,
    )
    issued_time = fields.Datetime(string=_("Issued at"), readonly=True)
    issued_by = fields.Many2one(
        "camp.staff",
        string=_("Issued by (staff)"),
        readonly=True,
    )
    status = fields.Selection(
        [("pending", "Pending"), ("issued", "Issued"), ("missed", "Missed")],
        string=_("Status"),
        default="pending",
        required=True,
        index=True,
        tracking=True,
        groups=_ART9_GROUPS,
        help=_("RODO art. 9 — dose status is health data (critique PR-6 #5)."),
    )
    notes = fields.Text(
        string=_("Notes"),
        groups=_ART9_GROUPS,
        help=_("RODO art. 9 — e.g. child refused, vomited, dose halved."),
    )
    alerted_at = fields.Datetime(
        string=_("Kierownik alerted at"),
        readonly=True,
        help=_("When the missed-dose activity for the kierownik was created."),
    )
    escalated_at = fields.Datetime(
        string=_("Escalated at"),
        readonly=True,
        help=_("When the repeat (raised-urgency) alert was created — T4-K 24h."),
    )

    # ------------------------------------------------------------------
    # Medic touch actions — big kanban buttons (kiosk-style, tablet)
    # ------------------------------------------------------------------

    def _current_staff(self):
        """camp.staff record of the current user on this dose's shift."""
        self.ensure_one()
        return self.env["camp.staff"].search(
            [
                ("event_id", "=", self.registry_id.event_id.id),
                ("user_id", "=", self.env.user.id),
            ],
            limit=1,
        )

    def action_issue(self):
        """Wydano — T3-K: date/time + who issued, tracked via chatter."""
        for rec in self:
            if rec.status != "pending":
                raise UserError(_("Only a pending dose can be marked as issued."))
            rec.write(
                {
                    "status": "issued",
                    "issued_time": fields.Datetime.now(),
                    "issued_by": rec._current_staff().id,
                }
            )
            rec.registry_id._log_medical_access(reason="dose issued")
        return True

    def action_miss(self):
        """Pominięto — manual miss by the medic, alerts immediately."""
        for rec in self:
            if rec.status != "pending":
                raise UserError(_("Only a pending dose can be marked as missed."))
            rec.status = "missed"
            rec.registry_id._log_medical_access(reason="dose missed (manual)")
        self._alert_missed()
        return True

    def unlink(self):
        # Issued/missed rows are the evidence trail (kejs Tsybulko) —
        # only regeneration of PENDING rows may delete. System can clean up.
        if not (self.env.su or self.env.user.has_group("base.group_system")):
            if any(rec.status != "pending" for rec in self):
                raise UserError(
                    _("Issued/missed doses are evidence and cannot be deleted.")
                )
        return super().unlink()

    # ------------------------------------------------------------------
    # Alerts (T4-K) — activity for kierownik + SMS CRITICAL for is_critical
    # ------------------------------------------------------------------

    def _alert_missed(self):
        """One activity + (if critical) one SMS per registry per call.

        Grouped by registry so a 10-day-unissued course produces one alert
        thread with all missed times listed — not an activity per dose.
        """
        now = fields.Datetime.now()
        for registry in self.mapped("registry_id"):
            doses = self.filtered(lambda s, r=registry: s.registry_id == r)
            kierownik = registry.event_id.user_id
            times = ", ".join(
                fields.Datetime.to_string(d) for d in doses.mapped("scheduled_time")
            )
            if kierownik:
                registry.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=kierownik.id,
                    summary=_("Pominięto wydanie leku — %s") % registry.name,
                    note=_(
                        "Child: %(child)s<br/>Medication: %(med)s<br/>"
                        "Missed dose(s): %(times)s<br/>"
                        "Confirm the miss and record the reason.",
                        child=registry.participant_id.display_name,
                        med=registry.sudo().medication_name,
                        times=times,
                    ),
                )
            doses.write({"alerted_at": now})
            if registry.is_critical:
                registry._send_critical_sms(times)

    @api.model
    def _cron_mark_missed_and_alert(self):
        """Hourly cron: overdue pending → missed + alert; 24h escalation.

        Runs as base.user_root (data/cron.xml) → sudo-safe over field groups.
        """
        now = fields.Datetime.now()
        cutoff = now - timedelta(hours=MISSED_GRACE_HOURS)

        # 1. Overdue pending doses of active courses → missed + alert.
        overdue = self.search(
            [
                ("status", "=", "pending"),
                ("scheduled_time", "<", cutoff),
                ("registry_id.state", "=", "active"),
            ]
        )
        if overdue:
            overdue.write({"status": "missed"})
            overdue._alert_missed()

        # 2. Missed doses alerted >24h ago and still unconfirmed → repeat
        #    alert with raised urgency (deadline today, ESKALACJA prefix).
        stale = self.search(
            [
                ("status", "=", "missed"),
                ("alerted_at", "!=", False),
                ("alerted_at", "<", now - timedelta(hours=ESCALATION_HOURS)),
                ("escalated_at", "=", False),
                ("registry_id.state", "=", "active"),
            ]
        )
        for registry in stale.mapped("registry_id"):
            # Confirmed = kierownik marked the alert activity as done
            # (it disappears from activity_ids). Open alert left → escalate.
            open_alerts = registry.activity_ids.filtered(
                lambda a: (a.summary or "").startswith(_("Pominięto wydanie leku"))
            )
            doses = stale.filtered(lambda s, r=registry: s.registry_id == r)
            if not open_alerts:
                # Kierownik confirmed in time — close the escalation window.
                doses.write({"escalated_at": now})
                continue
            kierownik = registry.event_id.user_id
            if kierownik:
                registry.activity_schedule(
                    "mail.mail_activity_data_todo",
                    date_deadline=fields.Date.context_today(self),
                    user_id=kierownik.id,
                    summary=_("ESKALACJA: pominięto wydanie leku — %s") % registry.name,
                    note=_(
                        "Missed dose unconfirmed for over 24h. Child: %(child)s. "
                        "Immediate follow-up required.",
                        child=registry.participant_id.display_name,
                    ),
                )
            doses.write({"escalated_at": now})
        return True


class CampMedicationRegistryEscalation(models.Model):
    """SMS CRITICAL escalation on the registry — dispatcher reuse (гейт #3).

    Kept as an extension class next to the schedule that triggers it, mirrors
    the incident_kamilka.py overlay style: alerting concern separated from the
    base reception/scheme logic above.
    """

    _inherit = "camp.medication.registry"

    def _send_critical_sms(self, times_text=""):
        """Missed CRITICAL dose → SMS to kierownik via fayna.sms.dispatcher.

        Body deliberately has NO medication name — SMS transits carrier
        infrastructure, art. 9 data stays in the system (same rule as the
        hashed phone numbers in sms.py logging).
        """
        for rec in self:
            kierownik = rec.event_id.user_id
            partner = kierownik.partner_id if kierownik else None
            phone = partner and (partner.mobile or partner.phone)
            if not phone:
                _logger.warning(
                    "fayna_camp_portal.medication.sms: registry=%s critical miss "
                    "but kierownik has no phone — SMS skipped",
                    rec.id,
                )
                continue
            body = _(
                "CRITICAL CampScout: pominięto wydanie leku — %(child)s (%(times)s). "
                "Sprawdź system i potwierdź.",
                child=rec.participant_id.display_name,
                times=times_text or fields.Datetime.to_string(fields.Datetime.now()),
            )
            result = self.env["fayna.sms.dispatcher"].send(
                phone=phone, body=body, partner_id=partner.id
            )
            _logger.info(
                "fayna_camp_portal.medication.sms: registry=%s critical miss → "
                "kierownik=%s success=%s provider=%s",
                rec.id,
                kierownik.id,
                result.get("success"),
                result.get("provider"),
            )


# ===========================================================================
# camp.participant — medication registry linkage (T5-K)
# ===========================================================================


class CampParticipantMedication(models.Model):
    _inherit = "camp.participant"

    medication_registry_ids = fields.One2many(
        "camp.medication.registry",
        "participant_id",
        string=_("Medication registry"),
        groups=_ART9_GROUPS,
        help=_("RODO art. 9 — medication courses recorded for this child."),
    )


# ===========================================================================
# camp.admin.access.log — medication access trail (T6-K, RODO art. 30)
# ===========================================================================


class CampAdminAccessLogMedication(models.Model):
    _inherit = "camp.admin.access.log"

    impersonated_role = fields.Selection(
        selection_add=[("medication", "Medication data access")],
        ondelete={"medication": "cascade"},
    )
    medication_registry_id = fields.Many2one(
        "camp.medication.registry",
        readonly=True,
        ondelete="set null",
        index=True,
        string=_("Medication registry"),
        help=_("Registry record whose art. 9 data was processed."),
    )
