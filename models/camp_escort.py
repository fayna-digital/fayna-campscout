# -*- coding: utf-8 -*-
"""camp.escort — Indywidualna asysta / konwój uczestnika.

Збір даних супроводу дитини на конкретний заїзд (одна дитина може їхати на
кілька заїздів різними напрямками → окрема модель, не поля на participant).
Живий підпис батьків за патерном camp.participant.qualification_signature
(Binary base64 PNG + signed_date/ip/by + RODO log). Поля freeze після підпису.

TZ: DevJournal/projects/campscout/TZ-migracja-legacy-to-portal-2026-06-23.md §5.
Дизайн ухвалено мульти-агентним конвеєром + СТО-рев'ю 2026-06-23.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Поля, що замерзають після підпису (як _PROTECTED_AFTER_SIGNOFF у participant.py).
_PROTECTED_AFTER_SIGN = frozenset(
    {
        "participant_id",
        "registration_id",
        "direction",
        "home_city",
        "pkp_station",
        "departure_datetime",
        "arrival_datetime",
        "transport_mode",
        "escort_person_name",
        "escort_person_phone",
        "escort_person_doc",
        "medical_help_consent",
    }
)


class CampEscort(models.Model):
    _name = "camp.escort"
    _description = "Indywidualna asysta / konwój uczestnika"
    _inherit = ["mail.thread", "portal.mixin"]
    _order = "departure_datetime, id"

    name = fields.Char(
        string="Reference",
        compute="_compute_name",
        store=True,
    )
    participant_id = fields.Many2one(
        "camp.participant",
        string="Uczestnik",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    registration_id = fields.Many2one(
        "event.registration",
        string="Zapis na turnus",
        required=True,
        ondelete="cascade",
        tracking=True,
    )

    # ── Маршрут супроводу ────────────────────────────────────────────────
    direction = fields.Selection(
        [("tam", "Tam (do obozu)"), ("powrot", "Powrót"), ("oba", "Tam i powrót")],
        string="Kierunek",
        default="oba",
        required=True,
        tracking=True,
    )
    home_city = fields.Char(string="Miasto zamieszkania")
    pkp_station = fields.Char(string="Stacja PKP (zbiórka/wysiadka)")
    departure_datetime = fields.Datetime(string="Wyjazd")
    arrival_datetime = fields.Datetime(string="Przyjazd")
    transport_mode = fields.Selection(
        [("pociag", "Pociąg"), ("autokar", "Autokar"), ("wlasny", "Transport własny")],
        string="Środek transportu",
        default="pociag",
    )

    # ── Особа-супровідник (konwojent / opiekun) ─────────────────────────
    escort_person_name = fields.Char(string="Osoba odbierająca / konwojent")
    escort_person_phone = fields.Char(string="Telefon osoby")
    escort_person_doc = fields.Char(string="Dokument osoby (do odbioru)")

    # ── Zgoda na udzielenie pomocy medycznej (RODO art. 9(2)(a)) ─────────
    # NB: цю згоду ставить БАТЬКО в кабінеті — НЕ group-gate (інакше зламає
    # портал-флоу). Медперсонал бачить її через доступ до запису.
    medical_help_consent = fields.Boolean(
        string="Zgoda na udzielenie pomocy medycznej w drodze/na obozie",
        tracking=True,
        help="RODO art. 9(2)(a) — dobrowolna zgoda rodzica na udzielenie dziecku "
        "pomocy medycznej i wezwanie pogotowia w razie potrzeby.",
    )
    medical_help_consent_date = fields.Datetime(string="Data zgody medycznej", readonly=True)
    medical_help_consent_ip = fields.Char(string="IP zgody medycznej", readonly=True)

    # ── Живий підпис батьків (патерн qualification_signature) ────────────
    parent_signature = fields.Binary(string="Podpis rodzica", attachment=True)
    signed_date = fields.Datetime(string="Data podpisu", readonly=True)
    signed_ip = fields.Char(string="IP podpisu", readonly=True)
    signed_by = fields.Many2one("res.users", string="Podpisano przez", readonly=True)
    rodo_consent_id = fields.Many2one(
        "fayna.rodo.consent.log", string="RODO consent log", readonly=True
    )

    state = fields.Selection(
        [("draft", "Szkic"), ("collected", "Dane zebrane"), ("signed", "Podpisano")],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )

    @api.depends("participant_id.display_name", "direction")
    def _compute_name(self):
        dir_labels = dict(self._fields["direction"].selection)
        for rec in self:
            who = rec.participant_id.display_name or _("Asysta")
            rec.name = "%s — %s" % (who, dir_labels.get(rec.direction, ""))

    @api.constrains("participant_id", "registration_id")
    def _check_participant_matches_registration(self):
        """Учасник має відповідати дитині на цьому заїзді (захист від плутанини)."""
        for rec in self:
            reg_partner = rec.registration_id.partner_id
            part_partner = rec.participant_id.partner_id
            if reg_partner and part_partner and reg_partner != part_partner:
                # м'яка перевірка: лише якщо обидва задані й різні партнери
                raise ValidationError(
                    _("Uczestnik %(p)s nie pasuje do zapisu %(r)s.")
                    % {"p": rec.participant_id.display_name, "r": rec.registration_id.display_name}
                )

    # ── Конфіг обов'язковості (Q9 — дефолт опційний, СТО-рішення) ────────
    @api.model
    def _escort_required(self):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("fayna_camp_portal.escort_required", "False")
            == "True"
        )

    # ── State machine ───────────────────────────────────────────────────
    def action_collect(self):
        for rec in self:
            if rec.state != "draft":
                continue
            if not (rec.home_city and rec.pkp_station and rec.direction):
                raise UserError(_("Wypełnij: miasto, stacja PKP, kierunek."))
            rec.state = "collected"
        return True

    def action_sign(self, ip_address=None, signature=None):
        """Атомарно: позначає signed + лінкує RODO consent (патерн sign_qualification)."""
        self.ensure_one()
        if self.state == "signed":
            raise UserError(_("Asysta jest już podpisana."))
        if self.state == "draft":
            self.action_collect()
        if not signature and not self.parent_signature:
            raise ValidationError(_("Wymagany podpis rodzica."))

        consent = (
            self.env["fayna.rodo.consent.log"]
            .sudo()
            .record_consent(
                purpose="transactional",
                channel="website",
                partner_id=self.participant_id.parent_partner_id.id
                or self.participant_id.partner_id.id,
                exact_response="escort_signed",
                source="website_form",
                legal_basis="consent",
                evidence_model="camp.escort",
                evidence_id=self.id,
            )
        )
        vals = {
            "state": "signed",
            "signed_date": fields.Datetime.now(),
            "signed_ip": ip_address or "",
            "signed_by": self.env.user.id,
            "rodo_consent_id": consent.id,
        }
        if signature:
            # base64 PNG без префікса data:image/png;base64, — Odoo Binary raw.
            vals["parent_signature"] = signature
        if self.medical_help_consent:
            vals["medical_help_consent_date"] = fields.Datetime.now()
            vals["medical_help_consent_ip"] = ip_address or ""
        self.write(vals)
        _logger.info(
            "fayna_camp_portal.escort.sign: escort=%s participant=%s ip=%s consent=%s",
            self.id,
            self.participant_id.id,
            ip_address,
            consent.id,
        )
        return True

    # ── Immutability після підпису (патерн participant.write) ────────────
    def write(self, vals):
        if self.env.su or self.env.user.has_group("base.group_system"):
            return super().write(vals)
        changing_protected = _PROTECTED_AFTER_SIGN & set(vals.keys())
        if changing_protected:
            for rec in self:
                if rec.state == "signed":
                    raise UserError(
                        _(
                            "Asysta %(name)s jest podpisana — nie można zmienić %(fields)s. "
                            "Użyj nowego rekordu (kopia + nowy podpis).",
                        )
                        % {"name": rec.display_name, "fields": ", ".join(sorted(changing_protected))}
                    )
        return super().write(vals)
