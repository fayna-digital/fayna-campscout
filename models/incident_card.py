# Copyright 2026 Fayna Digital — Volodymyr Shevchenko
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Karta Wypadku (§11) + Rejestr Wypadków (§12) — TZ_SPRINT_2026-06-10.

Models:
  - camp.incident.card      Karta Wypadku — full 16-point official wzór
                            (kurs kierownika wypoczynku). One card per injured
                            child per accident. Frozen after confirmation
                            (only załączniki / notes stay editable).
  - camp.incident.register  Rejestr Wypadków — one per camp shift (turnus),
                            auto-aggregates all confirmed cards of the event
                            chronologically with automatic Lp. numbering.
                            Immutable after the turnus is closed (locked).

Relationship to camp.incident.report (emergency.py):
  camp.incident.report drives the *operational* response workflow (7 states,
  SLA, action ledger). camp.incident.card is the *legal document* — the
  official Karta Wypadku form. A card MAY reference its operational report
  via ``incident_report_id`` but never duplicates its workflow.

Legal basis:
  * Rozp. MEN i Sportu z 31.12.2002 r. w sprawie bezpieczeństwa i higieny
    (Dz.U. 2003 nr 6 poz. 69) — karta wypadku + rejestr wypadków
  * Art. 247 KK — klauzula odpowiedzialności za poświadczenie nieprawdy
    (rendered in the PDF, pkt 15)
  * Ustawa o systemie oświaty 1991, art. 92n — kontrola Kuratorium Oświaty
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Selection used for every tak/nie checkbox of the official wzór — printed
# verbatim in the PDF, so a Selection (not Boolean) keeps the legal wording.
_TAK_NIE = [("tak", "Tak"), ("nie", "Nie")]


# ===========================================================================
# camp.incident.card — Karta Wypadku (16 punktów wzoru)
# ===========================================================================


class CampIncidentCard(models.Model):
    """Karta Wypadku — official 16-point accident card (per child).

    Workflow: draft → confirmed. After confirmation every field is frozen
    (legal evidence) except the attachments list (pkt 16 — wykaz załączników
    may grow: zdjęcia, oświadczenia świadków) and internal ``notes``.
    """

    _name = "camp.incident.card"
    _description = "Karta Wypadku — wzór 16 pkt (kurs kierownika)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "incident_datetime, id"
    _rec_name = "display_name"

    # ------------------------------------------------------------------
    # Header / linkage
    # ------------------------------------------------------------------

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
        compute_sudo=True,
    )
    event_id = fields.Many2one(
        "event.event",
        string=_("Turnus (camp shift)"),
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
        help=_(
            "Camp shift during which the accident happened. Drives the "
            "Rejestr Wypadków aggregation and record-rule scoping."
        ),
    )
    incident_report_id = fields.Many2one(
        "camp.incident.report",
        string=_("Operational incident report"),
        index=True,
        ondelete="set null",
        tracking=True,
        help=_(
            "Optional link to the operational camp.incident.report "
            "(emergency response workflow, SLA, action ledger). The card "
            "does NOT duplicate that workflow — it is the legal Karta "
            "Wypadku document only."
        ),
    )
    state = fields.Selection(
        [
            ("draft", "Szkic"),
            ("confirmed", "Zatwierdzona"),
        ],
        string=_("State"),
        default="draft",
        required=True,
        tracking=True,
        index=True,
        help=_(
            "Draft cards are freely editable. Confirmed cards are frozen "
            "as legal evidence — only załączniki (pkt 16) and internal "
            "notes may still change."
        ),
    )
    notes = fields.Text(
        string=_("Uwagi wewnętrzne"),
        help=_(
            "Internal remarks (not part of the official wzór). "
            "Also rendered in Rejestr Wypadków column 9 (Uwagi). "
            "Stays editable after confirmation."
        ),
    )

    # ------------------------------------------------------------------
    # Pkt 1 — Nazwa placówki (pieczęć)
    # ------------------------------------------------------------------

    placowka_name = fields.Char(
        string=_("1. Nazwa placówki (pieczęć)"),
        default=lambda self: self.env.company.name,
        tracking=True,
        help=_("Official name of the placówka wypoczynku — printed where the stamp goes."),
    )

    # ------------------------------------------------------------------
    # Pkt 2 — Poszkodowany
    # ------------------------------------------------------------------

    participant_id = fields.Many2one(
        "camp.participant",
        string=_("2. Imię i nazwisko poszkodowanego"),
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
        help=_("Injured child. Birth date, address and group are prefilled from the record."),
    )
    participant_birth_date = fields.Date(
        related="participant_id.birth_date",
        string=_("2. Data urodzenia"),
        store=True,
        readonly=True,
    )
    participant_address = fields.Char(
        string=_("2. Adres zamieszkania"),
        compute="_compute_participant_prefill",
        store=True,
        readonly=False,
        tracking=True,
        help=_("Prefilled from the linked res.partner; editable to match the legal form."),
    )
    group_class = fields.Char(
        string=_("2. Klasa / grupa"),
        compute="_compute_participant_prefill",
        store=True,
        readonly=False,
        tracking=True,
        help=_("Camp group (or school class) of the injured child at the time of the accident."),
    )

    # ------------------------------------------------------------------
    # Pkt 3 — Czynność wykonywana podczas wypadku
    # ------------------------------------------------------------------

    czynnosc = fields.Text(
        string=_("3. Czynność wykonywana podczas wypadku"),
        tracking=True,
        help=_("What the child was doing when the accident happened (rodzaj zajęć)."),
    )

    # ------------------------------------------------------------------
    # Pkt 4 — Przeszkolenie BHP
    # ------------------------------------------------------------------

    bhp_rodzaj = fields.Char(
        string=_("4. Rodzaj przeszkolenia BHP"),
        tracking=True,
    )
    bhp_kiedy = fields.Date(
        string=_("4. Przeszkolenie BHP — kiedy"),
        tracking=True,
    )
    bhp_przez_kogo = fields.Char(
        string=_("4. Przeszkolenie BHP — przez kogo"),
        tracking=True,
    )
    bhp_czas_trwania = fields.Char(
        string=_("4. Przeszkolenie BHP — czas trwania"),
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Pkt 5 — Badanie lekarskie
    # ------------------------------------------------------------------

    zbadany_przez_lekarza = fields.Selection(
        _TAK_NIE,
        string=_("5. Czy zbadany przez lekarza"),
        tracking=True,
    )
    data_ostatniego_badania = fields.Date(
        string=_("5. Data ostatniego badania lekarskiego"),
        tracking=True,
    )
    przeciwwskazania = fields.Selection(
        _TAK_NIE,
        string=_("5. Czy były przeciwwskazania"),
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Pkt 6 — Data i czas wypadku + miejsce
    # ------------------------------------------------------------------

    incident_datetime = fields.Datetime(
        string=_("6. Data i czas wypadku"),
        required=True,
        tracking=True,
        index=True,
        help=_("When the accident happened. Drives chronological order in the Rejestr."),
    )
    miejsce = fields.Char(
        string=_("6. Miejsce wypadku"),
        required=True,
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Pkt 7 — Rodzaj i umiejscowienie uszkodzenia ciała
    # ------------------------------------------------------------------

    uraz_rodzaj = fields.Char(
        string=_("7. Rodzaj uszkodzenia ciała"),
        tracking=True,
    )
    uraz_umiejscowienie = fields.Char(
        string=_("7. Umiejscowienie uszkodzenia ciała"),
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Pkt 8 — Niezdolność do uczestnictwa
    # ------------------------------------------------------------------

    niezdolny_do_uczestnictwa = fields.Selection(
        _TAK_NIE,
        string=_("8. Czy niezdolny do uczestnictwa w zajęciach"),
        tracking=True,
    )
    niezdolnosc_czas = fields.Char(
        string=_("8. Przypuszczalny czas niezdolności"),
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Pkt 9 — Szczegółowy opis wypadku z podaniem przyczyny
    # ------------------------------------------------------------------

    opis_wypadku = fields.Text(
        string=_("9. Szczegółowy opis wypadku z podaniem przyczyny"),
        tracking=True,
        help=_("Detailed factual description including the cause. Required to confirm the card."),
    )

    # ------------------------------------------------------------------
    # Pkt 10 — Osoba sprawująca nadzór w chwili wypadku
    # ------------------------------------------------------------------

    osoba_nadzoru = fields.Char(
        string=_("10. Imię i nazwisko osoby sprawującej nadzór"),
        tracking=True,
        help=_(
            "Supervising person (wychowawca/opiekun) at the moment of the "
            "accident. Also rendered in Rejestr column 9 (wskazanie "
            "Wychowawcy opiekuna)."
        ),
    )

    # ------------------------------------------------------------------
    # Pkt 11 — Czy osoba nadzoru była obecna na miejscu
    # ------------------------------------------------------------------

    nadzor_obecny = fields.Selection(
        _TAK_NIE,
        string=_("11. Czy osoba nadzoru była obecna na miejscu"),
        tracking=True,
    )
    nadzor_nieobecny_przyczyna = fields.Text(
        string=_("11. Jeśli nieobecna — z jakiej przyczyny"),
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Pkt 12 — Pierwszej pomocy udzielono o godzinie
    # ------------------------------------------------------------------

    pierwsza_pomoc_godzina = fields.Datetime(
        string=_("12. Pierwszej pomocy udzielono o godzinie"),
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Pkt 13 — Świadkowie
    # ------------------------------------------------------------------

    swiadkowie = fields.Text(
        string=_("13. Imiona, nazwiska i adresy świadków"),
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Pkt 14 — Podjęte środki zapobiegawcze
    # ------------------------------------------------------------------

    srodki_zapobiegawcze = fields.Text(
        string=_("14. Podjęte środki zapobiegawcze (komendant / kierownik)"),
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Pkt 15 — Podpisy komisji + kierownik placówki
    # (klauzula art. 247 KK rendered in the PDF template)
    # ------------------------------------------------------------------

    komisja_sklad = fields.Text(
        string=_("15. Skład komisji (imiona i nazwiska)"),
        tracking=True,
        help=_("Members of the accident commission — signature lines printed in the PDF."),
    )
    kierownik_placowki = fields.Char(
        string=_("15. Kierownik placówki (imię i nazwisko)"),
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Pkt 16 — Wykaz załączników (stays editable after confirmation)
    # ------------------------------------------------------------------

    zalaczniki_wykaz = fields.Text(
        string=_("16. Wykaz załączników"),
        help=_(
            "List of attachments (oświadczenia świadków, dokumentacja "
            "medyczna, zdjęcia). Stays editable after confirmation."
        ),
    )
    attachment_ids = fields.Many2many(
        "ir.attachment",
        relation="camp_incident_card_attachment_rel",
        column1="card_id",
        column2="attachment_id",
        string=_("Załączniki (pliki)"),
        help=_("Attached files for pkt 16. Stays editable after confirmation."),
    )

    # ------------------------------------------------------------------
    # Rejestr Wypadków helper — Lp. within the event (computed, not stored)
    # ------------------------------------------------------------------

    register_lp = fields.Integer(
        string=_("Lp."),
        compute="_compute_register_lp",
        compute_sudo=True,
        help=_(
            "Ordinal number in the Rejestr Wypadków of this card's event — "
            "confirmed cards only, chronological order. 0 while draft."
        ),
    )

    # ==================================================================
    # Computes
    # ==================================================================

    @api.depends("participant_id.display_name", "incident_datetime", "state")
    def _compute_display_name(self):
        for rec in self:
            if rec.participant_id and rec.incident_datetime:
                date_str = rec.incident_datetime.strftime("%Y-%m-%d")
                rec.display_name = _(
                    "Karta Wypadku — %(child)s (%(date)s)",
                    child=rec.participant_id.display_name,
                    date=date_str,
                )
            else:
                rec.display_name = _("Karta Wypadku (szkic)")

    @api.depends("participant_id")
    def _compute_participant_prefill(self):
        """Prefill address + group from the participant — editable afterwards.

        The official form is a snapshot at accident time, so the values are
        stored Chars (not related) — later changes of the partner address or
        group reshuffles must NOT rewrite a confirmed legal document.
        """
        for rec in self:
            partner = rec.participant_id.partner_id
            rec.participant_address = (
                partner.contact_address.replace("\n", ", ").strip(", ") if partner else False
            )
            rec.group_class = rec.participant_id.group_id.name or False

    def _compute_register_lp(self):
        """Ordinal Lp. among confirmed cards of the same event, chronological."""
        for event in self.mapped("event_id"):
            confirmed = self.search(
                [("event_id", "=", event.id), ("state", "=", "confirmed")],
                order="incident_datetime, id",
            )
            lp_map = {card.id: idx for idx, card in enumerate(confirmed, start=1)}
            for rec in self.filtered(lambda r, _e=event: r.event_id == _e):
                rec.register_lp = lp_map.get(rec.id, 0)
        for rec in self.filtered(lambda r: not r.event_id):
            rec.register_lp = 0

    # ==================================================================
    # Workflow
    # ==================================================================

    def action_confirm(self):
        """draft → confirmed. Freezes the card as legal evidence."""
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft cards can be confirmed."))
            missing = []
            if not rec.opis_wypadku:
                missing.append(_("9. Szczegółowy opis wypadku"))
            if not rec.osoba_nadzoru:
                missing.append(_("10. Osoba sprawująca nadzór"))
            if missing:
                raise UserError(
                    _(
                        "Cannot confirm Karta Wypadku — missing: %(fields)s",
                        fields="; ".join(missing),
                    )
                )
            rec.state = "confirmed"
        return True

    # ==================================================================
    # Immutability — frozen after confirmation
    # ==================================================================

    # Fields that may still change on a confirmed card:
    #   pkt 16 (załączniki may keep arriving) + internal notes.
    #   message_main_attachment_id — written by mail.thread when posting
    #   attachments in the chatter; harmless metadata, never legal content.
    _MUTABLE_AFTER_CONFIRM = {
        "zalaczniki_wykaz",
        "attachment_ids",
        "notes",
        "message_main_attachment_id",
    }

    def write(self, vals):
        for rec in self:
            if rec.state == "confirmed":
                forbidden = set(vals) - self._MUTABLE_AFTER_CONFIRM
                if forbidden:
                    raise UserError(
                        _(
                            "Confirmed Karta Wypadku is frozen (legal evidence) "
                            "— cannot modify: %(fields)s",
                            fields=", ".join(sorted(forbidden)),
                        )
                    )
        return super().write(vals)

    def unlink(self):
        if any(rec.state != "draft" for rec in self):
            raise UserError(
                _(
                    "Confirmed Karta Wypadku cannot be deleted "
                    "(legal evidence retention). Only draft cards may be removed."
                )
            )
        return super().unlink()


# ===========================================================================
# camp.incident.register — Rejestr Wypadków (10 kolumn, per turnus)
# ===========================================================================


class CampIncidentRegister(models.Model):
    """Rejestr Wypadków — one per camp shift (event), 10-column official wzór.

    Lines are NOT stored — they are the confirmed camp.incident.card records
    of the event, ordered chronologically, with Lp. assigned by position.
    The register is therefore always up to date with no sync logic.

    After the turnus is closed the register is locked (``action_lock``) and
    becomes immutable; only Camp Admin / System may unlock it.
    """

    _name = "camp.incident.register"
    _description = "Rejestr Wypadków — wzór 10 kolumn (per turnus)"
    _order = "event_id"
    _rec_name = "display_name"

    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
        compute_sudo=True,
    )
    event_id = fields.Many2one(
        "event.event",
        string=_("Turnus (camp shift)"),
        required=True,
        index=True,
        ondelete="restrict",
        help=_("Camp shift this register belongs to. Exactly one register per turnus."),
    )
    line_ids = fields.Many2many(
        "camp.incident.card",
        string=_("Karty wypadków (zatwierdzone)"),
        compute="_compute_line_ids",
        compute_sudo=True,
        help=_(
            "All CONFIRMED accident cards of the event, chronological. "
            "Computed live — the register never goes stale."
        ),
    )
    line_count = fields.Integer(
        string=_("# wypadków"),
        compute="_compute_line_ids",
        compute_sudo=True,
    )
    locked = fields.Boolean(
        string=_("Zamknięty (turnus zakończony)"),
        default=False,
        help=_(
            "Set when the turnus is closed. A locked register is immutable; "
            "only Camp Admin / System administrators may unlock it."
        ),
    )

    _sql_constraints = [
        (
            "event_id_uniq",
            "unique(event_id)",
            "Rejestr Wypadków already exists for this turnus — "
            "exactly one register per camp shift is allowed.",
        ),
    ]

    # ==================================================================
    # Computes
    # ==================================================================

    @api.depends("event_id.name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _(
                "Rejestr Wypadków — %(event)s",
                event=rec.event_id.name or "?",
            )

    @api.depends("event_id")
    def _compute_line_ids(self):
        card_model = self.env["camp.incident.card"]
        for rec in self:
            cards = card_model.search(
                [("event_id", "=", rec.event_id.id), ("state", "=", "confirmed")],
                order="incident_datetime, id",
            )
            rec.line_ids = [(6, 0, cards.ids)]
            rec.line_count = len(cards)

    # ==================================================================
    # Lock workflow (turnus closing)
    # ==================================================================

    def _check_unlock_allowed(self):
        """Only Camp Admin / System may unlock a closed register."""
        if not (
            self.env.is_system() or self.env.user.has_group("fayna_camp_portal.group_camp_admin")
        ):
            raise UserError(_("Only a Camp Administrator may unlock a closed " "Rejestr Wypadków."))

    def action_lock(self):
        """Lock the register — call when the turnus is closed."""
        self.write({"locked": True})
        return True

    def action_unlock(self):
        """Unlock — Camp Admin / System only (audited via standard logging)."""
        self._check_unlock_allowed()
        self.write({"locked": False})
        return True

    # ==================================================================
    # Immutability — frozen after lock
    # ==================================================================

    def write(self, vals):
        for rec in self:
            if rec.locked:
                forbidden = set(vals) - {"locked"}
                if forbidden:
                    raise UserError(
                        _(
                            "Rejestr Wypadków is locked (turnus closed) — "
                            "cannot modify: %(fields)s",
                            fields=", ".join(sorted(forbidden)),
                        )
                    )
                if "locked" in vals and not vals["locked"]:
                    rec._check_unlock_allowed()
        return super().write(vals)

    def unlink(self):
        if any(rec.locked for rec in self):
            raise UserError(
                _("Locked Rejestr Wypadków cannot be deleted (legal evidence retention).")
            )
        return super().unlink()
