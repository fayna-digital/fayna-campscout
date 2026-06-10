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

_logger = logging.getLogger(__name__)

# States in which a staff member counts as "kadra na turnusie" for KO.
_STAFF_ACTIVE_STATES = ("confirmed", "active")


class CampTeczkaKO(models.Model):
    _name = "camp.teczka.ko"
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
            staff = teczka.event_id.staff_ids.filtered(
                lambda s: s.state in _STAFF_ACTIVE_STATES
            )
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
        help=_("True when a rejestr wypadków exists for this shift. False while the model is absent."),
    )

    def _compute_wypadki(self):
        # camp.incident.register is being built in parallel (sprint §4 note).
        # env.get() returns None when the model is not in the registry yet —
        # NO hard dependency, integration happens after both land.
        IncidentRegister = self.env.get("camp.incident.register")
        has_event_field = (
            IncidentRegister is not None and "event_id" in IncidentRegister._fields
        )
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
                )
            )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_print_checklist(self):
        """1-page PDF 'Gotowość do kontroli KO' (✅/❌ per checklist item)."""
        self.ensure_one()
        return self.env.ref(
            "fayna_camp_portal.action_report_teczka_ko_checklist"
        ).report_action(self)

    def action_export_pdf_pack(self):
        """Export the FULL KO documentation pack as one PDF.

        TODO(sprint 2026-06-10 §4, integration phase): assemble the complete
        pack after all sub-reports land — karty kwalifikacyjne PDFs, dzienniki
        zajęć (Załącznik 5), Program Wypoczynku (Załącznik 9), regulaminy +
        acknowledgment sheets, kadra cert scans (KRK/RSPTS), rejestr wypadków.
        Blocked on the parallel camp.incident.register agent; merge strategy
        (PyPDF2 vs single QWeb bundle) to be decided at integration.
        """
        self.ensure_one()
        raise NotImplementedError(
            "Pełny pakiet PDF Teczki KO będzie dostępny po integracji "
            "wszystkich raportów (zob. TODO w action_export_pdf_pack)."
        )

    def action_check_regulamin_acks(self):
        """Manual trigger of the unsigned-regulamin warning (activity/log)."""
        for teczka in self:
            self.env["camp.regulamin"].check_acks_for_event(teczka.event_id)
        return True
