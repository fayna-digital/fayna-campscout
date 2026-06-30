# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — Teczka KO (gotowość do kontroli Kuratorium Oświaty)
# TZ_SPRINT_2026-06-10 §4: kierownik dashboard — readiness checklist per
# arkusz kontroli (doc-kku-arkusz-ko, protokol-kontroli-2026):
#   karty / kadra+RSPTS / regulaminy / dziennik / rejestr wypadków / program.
# DESIGN: one teczka per event (SQL unique), EVERYTHING computed live —
# nothing is stored manually, so the checklist can never go stale.
# camp.incident.register is built by a parallel agent — looked up via
# self.env.get(...) and degraded gracefully (False) until it lands.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.pdf import merge_pdf

_logger = logging.getLogger(__name__)

# States in which a staff member counts as "kadra na turnusie" for KO.
_STAFF_ACTIVE_STATES = ("confirmed", "active")

# Kuratorium notification states that satisfy the "zgłoszenie złożone" item:
# the camp is legally filed once submitted (and stays filed once registered).
_KURATORIUM_FILED_STATES = ("submitted", "registered")

# ir.config_parameter holding the default delegatura (Kuratorium Oświaty) e-mail.
# Single organizer → single delegatura by region (our delegatura = Kalisz).
_PARAM_DELEGATURA_EMAIL = "fayna_camp_portal.kuratorium_delegatura_email"


class CampTeczkaKO(models.Model):
    _name = "camp.teczka.ko"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Teczka KO — gotowość do kontroli Kuratorium Oświaty"
    _order = "event_id"
    _rec_name = "name"

    _sql_constraints = [
        (
            "event_unique",
            "UNIQUE(event_id)",
            "Each camp shift (event) has exactly one Teczka KO.",
        ),
    ]

    event_id = fields.Many2one(
        "event.event",
        required=True,
        index=True,
        ondelete="cascade",
        string=_("Camp shift (event)"),
        help=_("The shift this readiness folder belongs to (one teczka per event)."),
    )

    name = fields.Char(
        compute="_compute_name",
        string=_("Name"),
        help=_("Auto: 'Teczka KO — {event}'."),
    )

    @api.depends("event_id.name")
    def _compute_name(self):
        for teczka in self:
            teczka.name = _("Teczka KO — %(event)s", event=teczka.event_id.name or "?")

    # ------------------------------------------------------------------
    # 1. Karty kwalifikacyjne — % signed parent qualification cards
    # ------------------------------------------------------------------

    karty_total = fields.Integer(
        compute="_compute_karty",
        string=_("Karty — uczestnicy"),
        help=_("Non-cancelled registrations of this shift."),
    )
    karty_signed = fields.Integer(
        compute="_compute_karty",
        string=_("Karty — podpisane"),
        help=_("Registrations whose participant has a signed qualification card."),
    )
    karty_percent = fields.Float(
        compute="_compute_karty",
        string=_("Karty — % podpisanych"),
        help=_("Percentage of signed qualification cards (0-100)."),
    )
    karty_ready = fields.Boolean(
        compute="_compute_karty",
        string=_("Karty ✓"),
        help=_("True when every registration has a signed qualification card."),
    )

    def _compute_karty(self):
        Registration = self.env["event.registration"]
        for teczka in self:
            regs = Registration.search(
                [
                    ("event_id", "=", teczka.event_id.id),
                    ("state", "!=", "cancel"),
                ]
            )
            total = len(regs)
            # Orphan registrations (no participant yet) count as unsigned —
            # KO inspector needs a card for every child on site.
            signed = len(
                regs.filtered(lambda r: r.participant_id and r.participant_id.qualification_signed)
            )
            teczka.karty_total = total
            teczka.karty_signed = signed
            teczka.karty_percent = (signed * 100.0 / total) if total else 0.0
            teczka.karty_ready = bool(total) and signed == total

    # ------------------------------------------------------------------
    # 2. Kadra — KRK/RSPTS/course verified for all confirmed/active staff
    # ------------------------------------------------------------------

    kadra_total = fields.Integer(
        compute="_compute_kadra",
        string=_("Kadra — liczba"),
        help=_("Confirmed/active staff members of this shift."),
    )
    kadra_eligible = fields.Integer(
        compute="_compute_kadra",
        string=_("Kadra — zweryfikowana"),
        help=_("Staff with valid, admin-accepted KRK + RSPTS + course certificate."),
    )
    kadra_ready = fields.Boolean(
        compute="_compute_kadra",
        string=_("Kadra ✓"),
        help=_("True when every confirmed/active staff member is eligible (Ustawa Kamilka §13)."),
    )

    def _compute_kadra(self):
        for teczka in self:
            staff = teczka.event_id.staff_ids.filtered(lambda s: s.state in _STAFF_ACTIVE_STATES)
            eligible = staff.filtered("is_eligible_for_camp")
            teczka.kadra_total = len(staff)
            teczka.kadra_eligible = len(eligible)
            teczka.kadra_ready = bool(staff) and len(eligible) == len(staff)

    # ------------------------------------------------------------------
    # 3. Regulaminy — published + signed by the whole kadra of THIS event
    # ------------------------------------------------------------------

    regulamin_total = fields.Integer(
        compute="_compute_regulaminy",
        string=_("Regulaminy — opublikowane"),
        help=_("Published regulaminy applying to this shift (event-bound + organizer templates)."),
    )
    regulamin_unsigned = fields.Integer(
        compute="_compute_regulaminy",
        string=_("Regulaminy — z brakami podpisów"),
        help=_("Published regulaminy not yet signed by every staff member of this shift."),
    )
    regulaminy_ready = fields.Boolean(
        compute="_compute_regulaminy",
        string=_("Regulaminy ✓"),
        help=_("True when at least one regulamin is published and all are signed by the kadra."),
    )

    def _compute_regulaminy(self):
        Regulamin = self.env["camp.regulamin"]
        for teczka in self:
            event = teczka.event_id
            regulaminy = Regulamin.search(
                [
                    ("state", "=", "published"),
                    "|",
                    ("event_id", "=", event.id),
                    ("event_id", "=", False),
                ]
            )
            staff = event.staff_ids.filtered(lambda s: s.state in _STAFF_ACTIVE_STATES)
            unsigned = 0
            for regulamin in regulaminy:
                signed_staff = regulamin.ack_ids.filtered("signed").mapped("staff_id")
                if staff - signed_staff:
                    unsigned += 1
            teczka.regulamin_total = len(regulaminy)
            teczka.regulamin_unsigned = unsigned
            teczka.regulaminy_ready = bool(regulaminy) and bool(staff) and unsigned == 0

    # ------------------------------------------------------------------
    # 4. Dziennik zajęć (Załącznik 5) — at least one per event
    # ------------------------------------------------------------------

    dziennik_count = fields.Integer(
        compute="_compute_dziennik",
        string=_("Dzienniki zajęć"),
        help=_("fayna.camp.dziennik records of this shift."),
    )
    dziennik_ready = fields.Boolean(
        compute="_compute_dziennik",
        string=_("Dziennik ✓"),
        help=_("True when at least one dziennik zajęć exists for this shift."),
    )

    def _compute_dziennik(self):
        Dziennik = self.env["fayna.camp.dziennik"]
        for teczka in self:
            count = Dziennik.search_count([("event_id", "=", teczka.event_id.id)])
            teczka.dziennik_count = count
            teczka.dziennik_ready = count > 0

    # ------------------------------------------------------------------
    # 5. Rejestr wypadków — model built by a PARALLEL agent.
    #    Looked up via env.get(); gracefully False until it exists.
    # ------------------------------------------------------------------

    wypadki_available = fields.Boolean(
        compute="_compute_wypadki",
        string=_("Rejestr wypadków — moduł dostępny"),
        help=_("True when the camp.incident.register model is installed in the registry."),
    )
    wypadki_count = fields.Integer(
        compute="_compute_wypadki",
        string=_("Rejestry wypadków"),
        help=_("camp.incident.register records of this shift (0 if the model is absent)."),
    )
    wypadki_ready = fields.Boolean(
        compute="_compute_wypadki",
        string=_("Rejestr wypadków ✓"),
        help=_(
            "True when a rejestr wypadków exists for this shift. False while the model is absent."
        ),
    )

    def _compute_wypadki(self):
        # camp.incident.register is being built in parallel (sprint §4 note).
        # env.get() returns None when the model is not in the registry yet —
        # NO hard dependency, integration happens after both land.
        IncidentRegister = self.env.get("camp.incident.register")
        has_event_field = IncidentRegister is not None and "event_id" in IncidentRegister._fields
        for teczka in self:
            if not has_event_field:
                teczka.wypadki_available = False
                teczka.wypadki_count = 0
                teczka.wypadki_ready = False
                continue
            count = IncidentRegister.search_count([("event_id", "=", teczka.event_id.id)])
            teczka.wypadki_available = True
            teczka.wypadki_count = count
            teczka.wypadki_ready = count > 0

    # ------------------------------------------------------------------
    # 6. Program wypoczynku (Załącznik 9) — exists for the event
    # ------------------------------------------------------------------

    program_count = fields.Integer(
        compute="_compute_program",
        string=_("Programy wypoczynku"),
        help=_("camp.program.wypoczynku records of this shift."),
    )
    program_ready = fields.Boolean(
        compute="_compute_program",
        string=_("Program ✓"),
        help=_("True when at least one Program Wypoczynku exists for this shift."),
    )

    def _compute_program(self):
        Program = self.env["camp.program.wypoczynku"]
        for teczka in self:
            count = Program.search_count([("event_id", "=", teczka.event_id.id)])
            teczka.program_count = count
            teczka.program_ready = count > 0

    # ------------------------------------------------------------------
    # 7. Zgłoszenie wypoczynku do Kuratorium (Załącznik 1) — filed?
    #    REUSE camp.kuratorium.notification (no new model). Green once a
    #    notification of this event reached submitted/registered.
    # ------------------------------------------------------------------

    zgloszenie_count = fields.Integer(
        compute="_compute_zgloszenie",
        string=_("Zgłoszenia do Kuratorium"),
        help=_("Active (non-cancelled) Kuratorium notifications of this shift."),
    )
    zgloszenie_filed = fields.Integer(
        compute="_compute_zgloszenie",
        string=_("Zgłoszenia złożone"),
        help=_("Notifications already submitted to / registered by Kuratorium Oświaty."),
    )
    zgloszenie_ready = fields.Boolean(
        compute="_compute_zgloszenie",
        string=_("Zgłoszenie ✓"),
        help=_("True when at least one notification of this shift is submitted or registered."),
    )

    def _compute_zgloszenie(self):
        Notification = self.env["camp.kuratorium.notification"]
        for teczka in self:
            notifications = Notification.search(
                [
                    ("event_id", "=", teczka.event_id.id),
                    ("state", "!=", "cancelled"),
                ]
            )
            filed = notifications.filtered(lambda n: n.state in _KURATORIUM_FILED_STATES)
            teczka.zgloszenie_count = len(notifications)
            teczka.zgloszenie_filed = len(filed)
            teczka.zgloszenie_ready = bool(filed)

    # ------------------------------------------------------------------
    # Delegatura (Kuratorium Oświaty) e-mail — recipient of the dossier.
    # Sourced from the filed notification, else the module-level default
    # (our delegatura = Kalisz). Editable by organizator on the teczka.
    # ------------------------------------------------------------------

    delegatura_email = fields.Char(
        compute="_compute_delegatura_email",
        store=True,
        readonly=False,
        string=_("E-mail delegatury KO"),
        help=_(
            "Oficjalny adres delegatury Kuratorium Oświaty — odbiorca teczki. "
            "Domyślnie z parametru systemu; można nadpisać dla tego turnusu."
        ),
    )

    @api.depends("event_id")
    def _compute_delegatura_email(self):
        default_email = (
            self.env["ir.config_parameter"].sudo().get_param(_PARAM_DELEGATURA_EMAIL, "")
        )
        for teczka in self:
            # Do not clobber a value an organizator typed by hand.
            if teczka.delegatura_email:
                continue
            teczka.delegatura_email = default_email or False

    # ------------------------------------------------------------------
    # Overall readiness
    # ------------------------------------------------------------------

    overall_ready = fields.Boolean(
        compute="_compute_overall_ready",
        string=_("Gotowość do kontroli KO"),
        help=_("True when every checklist item above is green."),
    )

    @api.depends("event_id")
    def _compute_overall_ready(self):
        for teczka in self:
            teczka.overall_ready = all(
                (
                    teczka.karty_ready,
                    teczka.kadra_ready,
                    teczka.regulaminy_ready,
                    teczka.dziennik_ready,
                    teczka.wypadki_ready,
                    teczka.program_ready,
                    teczka.zgloszenie_ready,
                )
            )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_print_checklist(self):
        """1-page PDF 'Gotowość do kontroli KO' (✅/❌ per checklist item)."""
        self.ensure_one()
        return self.env.ref("fayna_camp_portal.action_report_teczka_ko_checklist").report_action(
            self
        )

    def _collect_pack_sections(self):
        """Render every available KO sub-report to PDF bytes for this shift.

        Read-only: each section is rendered freshly via QWeb-PDF (no stored
        copy, no business-record write). Sections with zero target records are
        skipped silently so the merge never fails on an empty turnus. The
        readiness checklist (self) is ALWAYS page 1, so the pack is never empty.

        Returns the ordered list of non-empty PDF byte strings.

        Verified relations (file:line):
          * karty kwalifikacyjne → camp.participant reached via this event's
            non-cancelled event.registration.participant_id (_compute_karty,
            teczka_ko.py:91-104; participant_id field participant.py:2269).
          * dziennik zajęć → fayna.camp.dziennik.event_id (operations.py:2923,
            mirrors _compute_dziennik teczka_ko.py:195-200).
          * rejestr wypadków → camp.incident.register.event_id
            (incident_card.py:504, mirrors _compute_wypadki teczka_ko.py:225-240;
            model looked up via env.get(), absent gracefully).
          * ewidencja budżetu → camp.budget.event_id (budget.py:100).

        Skipped (no report_name / no template exists in reports/): Program
        Wypoczynku (camp.program.wypoczynku) and regulaminy + acknowledgment
        sheets (camp.regulamin) — there is no qweb-pdf report for those models
        yet, so they cannot be rendered here.
        """
        self.ensure_one()
        event = self.event_id
        Report = self.env["ir.actions.report"].sudo()
        sections = []

        def _add(report_ref, res_ids):
            """Render one report over res_ids; skip silently if empty/missing."""
            if not res_ids:
                return
            try:
                pdf_content, _fmt = Report._render_qweb_pdf(report_ref, res_ids)
            except Exception:  # noqa: BLE001 — never let one section break the pack
                _logger.exception("Teczka KO pack: skipping report %s", report_ref)
                return
            if pdf_content:
                sections.append(pdf_content)

        # 1. Readiness checklist (self) — always page 1.
        _add("fayna_camp_portal.action_report_teczka_ko_checklist", self.ids)

        # 2. Karty kwalifikacyjne — one per participant of a non-cancelled
        #    registration of this shift (same source as _compute_karty).
        registrations = self.env["event.registration"].search(
            [("event_id", "=", event.id), ("state", "!=", "cancel")]
        )
        participant_ids = registrations.mapped("participant_id").ids
        _add("fayna_camp_portal.action_report_karta_kwalifikacyjna", participant_ids)

        # 3. Dziennik zajęć (Załącznik 5) — fayna.camp.dziennik of this shift.
        dziennik_ids = self.env["fayna.camp.dziennik"].search([("event_id", "=", event.id)]).ids
        _add("fayna_camp_portal.action_report_dziennik", dziennik_ids)

        # 4. Rejestr wypadków — camp.incident.register, built by a parallel
        #    agent; absent gracefully via env.get() (mirrors _compute_wypadki).
        IncidentRegister = self.env.get("camp.incident.register")
        if IncidentRegister is not None and "event_id" in IncidentRegister._fields:
            register_ids = IncidentRegister.search([("event_id", "=", event.id)]).ids
            _add("fayna_camp_portal.action_report_incident_register", register_ids)

        # 5. Ewidencja dla księgowej — camp.budget of this shift.
        budget_ids = self.env["camp.budget"].search([("event_id", "=", event.id)]).ids
        _add("fayna_camp_portal.action_report_camp_budget_evidence", budget_ids)

        return sections

    def action_export_pdf_pack(self):
        """Export the FULL KO documentation pack as one merged PDF (download).

        Assembles, in order: (1) readiness checklist [always], (2) karty
        kwalifikacyjne for every participant of this shift, (3) dzienniki zajęć
        (Załącznik 5), (4) rejestr wypadków (when the camp.incident.register
        model is installed), (5) ewidencja dla księgowej (camp.budget). Each
        section is rendered to PDF bytes and merged with the canonical Odoo 17
        helper ``odoo.tools.pdf.merge_pdf``. Empty sections are skipped silently.

        Still SKIPPED (no qweb-pdf report exists for these models): Program
        Wypoczynku (Załącznik 9, camp.program.wypoczynku) and regulaminy +
        acknowledgment sheets (camp.regulamin). They appear only as checklist
        items until a report template lands for them.

        Read-only render+merge: stores the result as an ir.attachment on this
        teczka and returns an act_url download — no business record is written.
        """
        self.ensure_one()
        sections = self._collect_pack_sections()
        if not sections:
            # Should never happen (checklist is always page 1), but never crash.
            raise UserError(_("Nie udało się wygenerować żadnej strony teczki KO."))

        merged_pdf = merge_pdf(sections)
        filename = "Teczka_KO_pakiet_{}.pdf".format((self.event_id.name or "").replace(" ", "_"))
        attachment = (
            self.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": filename,
                    "type": "binary",
                    "raw": merged_pdf,
                    "mimetype": "application/pdf",
                    "res_model": self._name,
                    "res_id": self.id,
                }
            )
        )
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    def action_check_regulamin_acks(self):
        """Manual trigger of the unsigned-regulamin warning (activity/log)."""
        for teczka in self:
            self.env["camp.regulamin"].check_acks_for_event(teczka.event_id)
        return True

    # ------------------------------------------------------------------
    # Wyślij teczkę do Kuratorium (e-mail dossier to the delegatura)
    # ------------------------------------------------------------------

    def _missing_checklist_items(self):
        """Return Polish labels of every checklist item that is NOT ready.

        Used to warn the kierownik before they file an incomplete dossier
        and to record the gap in the chatter audit trail.
        """
        self.ensure_one()
        items = (
            (self.karty_ready, _("Karty kwalifikacyjne — podpisy rodziców")),
            (self.kadra_ready, _("Kadra — KRK / RSPTS / kursy zweryfikowane")),
            (self.regulaminy_ready, _("Regulaminy — podpisy całej kadry")),
            (self.dziennik_ready, _("Dziennik zajęć (Załącznik 5)")),
            (self.wypadki_ready, _("Rejestr wypadków")),
            (self.program_ready, _("Program wypoczynku (Załącznik 9)")),
            (self.zgloszenie_ready, _("Zgłoszenie wypoczynku do Kuratorium (Załącznik 1)")),
        )
        return [label for ready, label in items if not ready]

    def action_send_teczka_to_kuratorium(self):
        """Wyślij teczkę (PDF) na oficjalny e-mail delegatury Kuratorium Oświaty.

        Renders the readiness checklist as a QWeb-PDF, attaches it, and e-mails
        it to ``delegatura_email``. Logs who/when/where to the chatter for the
        Kuratorium audit trail. Refuses to send if there are open checklist
        items unless the caller explicitly overrides via
        ``force_send_incomplete`` in the context.

        RODO art.9: the teczka may reference children's data, so the recipient
        MUST be the official delegatura address (not a free-typed personal
        e-mail by accident) and access stays gated by the model's record rules.
        """
        self.ensure_one()
        email_to = (self.delegatura_email or "").strip()
        if not email_to:
            raise UserError(
                _(
                    "Brak adresu e-mail delegatury Kuratorium Oświaty. "
                    "Uzupełnij pole „E-mail delegatury KO” lub parametr systemu."
                )
            )

        missing = self._missing_checklist_items()
        if missing and not self.env.context.get("force_send_incomplete"):
            raise UserError(
                _(
                    "Teczka ma niekompletne pozycje:\n• %(items)s\n\n"
                    "Uzupełnij braki przed wysłaniem do Kuratorium albo wyślij "
                    "świadomie mimo braków.",
                    items="\n• ".join(missing),
                )
            )

        # Render the readiness checklist PDF freshly (no stored copy).
        report = self.env.ref("fayna_camp_portal.action_report_teczka_ko_checklist")
        pdf_content, _ext = report.sudo()._render_qweb_pdf(
            "fayna_camp_portal.action_report_teczka_ko_checklist",
            res_ids=self.ids,
        )
        filename = "Teczka_KO_{}.pdf".format((self.event_id.name or "").replace(" ", "_"))
        attachment = (
            self.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": filename,
                    "type": "binary",
                    "raw": pdf_content,
                    "mimetype": "application/pdf",
                    "res_model": self._name,
                    "res_id": self.id,
                }
            )
        )

        company = self.event_id.company_id or self.env.company
        email_from = company.email or self.env.user.email_formatted or "noreply@campscout.eu"
        body_html = _(
            "<p>Szanowni Państwo,</p>"
            "<p>w załączeniu przesyłamy teczkę kontrolną wypoczynku "
            "<strong>%(event)s</strong> (organizator: %(org)s).</p>"
            "<p>Status gotowości: <strong>%(status)s</strong>.</p>"
            "<p>Z poważaniem,<br/>%(sender)s</p>",
            event=self.event_id.name or "—",
            org=company.name or "—",
            status=_("KOMPLETNA") if self.overall_ready else _("Z BRAKAMI"),
            sender=self.env.user.name or "CampScout",
        )

        mail = (
            self.env["mail.mail"]
            .sudo()
            .create(
                {
                    "subject": _("Teczka kontrolna wypoczynku — %s", self.event_id.name or ""),
                    "body_html": body_html,
                    "email_from": email_from,
                    "email_to": email_to,
                    "attachment_ids": [(4, attachment.id)],
                }
            )
        )
        mail.send()

        # Audit trail in the chatter — who / when / to (Kuratorium audit).
        log = _(
            "📨 Teczka wysłana do Kuratorium Oświaty.<br/>"
            "Odbiorca: <strong>%(to)s</strong><br/>"
            "Wysłał(a): %(user)s<br/>"
            "Data: %(when)s",
            to=email_to,
            user=self.env.user.name,
            when=fields.Datetime.to_string(fields.Datetime.now()),
        )
        if missing:
            log += _("<br/>⚠️ Wysłano mimo braków: %s") % ", ".join(missing)
        # sudo: the kierownik has read-only access on the teczka (record rule);
        # the audit note must still be written regardless of write rights.
        self.sudo().message_post(body=log)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Teczka wysłana"),
                "message": _("Teczka została wysłana na adres %s.") % email_to,
                "type": "success",
                "sticky": False,
            },
        }
