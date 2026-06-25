# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — Camp Operations models
# Sources:
#   fayna_camp_operations:   CampReport, CampJournal, CampStaff, CampStaffCert,
#                            CampStaffMedical, CampDailyReport, CampProgramWypoczynku
#   fayna_camp_program:      CampProgram, CampProgramStructured, CampProgramDay,
#                            CampProgramActivity, CampProgramActivityLine, CampActivityTemplate
#   fayna_camp_dziennik_zajec: FaynaCampDziennik, FaynaCampDziennikActivity,
#                            FaynaCampDziennikNote, FaynaCampDziennikPlanLine
#   fayna_camp_kuratorium:   CampKuratoriumNotification, CampKuratoriumChecklist,
#                            CampKuratoriumStaff
import base64
import logging
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from markupsafe import Markup
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

_MANAGER_GROUP = "fayna_camp_portal.group_fayna_camp_manager"
_MEDICAL_GROUP = "fayna_camp_portal.group_medical_officer"
_ADMIN_GROUP = "fayna_camp_portal.group_camp_admin"

# Default checklist items per Załącznik 1 MEN 2016
_DEFAULT_CHECKLIST_ITEMS = [
    "Zgłoszenie wypoczynku (Załącznik 1) wypełnione i podpisane",
    "Kopia dokumentu potwierdzającego kwalifikacje kierownika",
    "Lista kadry z kwalifikacjami (wychowawcy)",
    "Zaświadczenia z KRK dla kierownika i wychowawców",
    "Sprawdzenie w RPS (Rejestr Sprawców Przestępstw na Tle Seksualnym)",
    "Opinia właściwego komendanta PSP (obiekty stałe)",
    "Szkic lub opis miejsca wypoczynku",
    "Program wypoczynku — ramowy plan",
    "Ubezpieczenie NNW uczestników",
    "Oświadczenie o zapewnieniu opieki medycznej",
    "Regulamin uczestnictwa przekazany rodzicom",
    "Zgody rodziców / opiekunów prawnych",
]


# ---------------------------------------------------------------------------
# Staff — core roster
# ---------------------------------------------------------------------------


class CampStaff(models.Model):
    _name = "camp.staff"
    _description = "Camp staff member"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "event_id, name"

    active = fields.Boolean(
        default=True,
        string=_("Active"),
        help=_("Inactive staff are hidden from lists but kept for archival."),
    )

    event_id = fields.Many2one(
        "event.event",
        required=True,
        ondelete="cascade",
        string=_("Camp shift (event)"),
        help=_("The specific shift/заїзд this staff member is assigned to."),
        index=True,
    )

    name = fields.Char(
        required=True,
        string=_("Full name"),
        help=_("Full legal name of the staff member."),
    )

    role = fields.Selection(
        [
            ("activity_lead", "Activity lead"),
            ("counselor", "Counselor"),
            ("medic", "Medical officer"),
            ("kitchen_staff", "Kitchen staff"),
            ("logistics", "Logistics"),
            ("director", "Director"),
            ("leader", "Kierownik wypoczynku (camp leader)"),
        ],
        required=True,
        string=_("Role"),
        tracking=True,
        help=_("Operational role of this staff member in the shift."),
    )

    user_id = fields.Many2one(
        "res.users",
        string=_("System user"),
        index=True,
        help=_(
            "Login account this staff member uses. Required for record-rule "
            "scoping — wychowawca sees only their own dzienniki; kierownik "
            "sees all groups in own camp."
        ),
    )

    phone = fields.Char(
        string=_("Phone"),
        help=_("Mobile phone number."),
    )
    email = fields.Char(
        string=_("Email"),
        help=_("Contact email address."),
    )

    medical_notes = fields.Text(
        string=_("Medical info"),
        help=_("Allergies, medical conditions, emergency contacts (staff internal)."),
        groups=(
            "fayna_camp_portal.group_medical_officer,"
            "fayna_camp_portal.group_camp_admin,"
            "base.group_system"
        ),
    )

    emergency_contact = fields.Char(
        string=_("Emergency contact name"),
        help=_("Name of the emergency contact person for this staff member."),
    )
    emergency_phone = fields.Char(
        string=_("Emergency contact phone"),
        help=_("Phone number of the emergency contact."),
    )

    assigned_groups = fields.Char(
        string=_("Assigned groups (obowiązki)"),
        help=_(
            "Which camp groups this staff member is responsible for. "
            "List group names separated by commas, or write 'Entire shift'."
        ),
    )

    date_from = fields.Date(
        required=True,
        string=_("Start date"),
        help=_("First day of shift participation."),
    )
    date_to = fields.Date(
        required=True,
        string=_("End date"),
        help=_("Last day of shift participation."),
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("active", "Active"),
            ("on_leave", "On leave"),
            ("finished", "Finished"),
        ],
        default="draft",
        string=_("Status"),
        tracking=True,
        help=_("Current participation status of this staff member."),
    )

    notes = fields.Text(
        string=_("Notes"),
        help=_("Additional info or instructions."),
    )

    # ------------------------------------------------------------------
    # Certifications
    # ------------------------------------------------------------------

    cert_ids = fields.One2many(
        "camp.staff.cert",
        "staff_id",
        string=_("Certifications"),
        help=_("KRK, RPS, course certificates and other required PL-law documents."),
    )

    has_valid_krk = fields.Boolean(
        compute="_compute_cert_status",
        store=True,
        string=_("Has valid KRK"),
        help=_("True when at least one active KRK certificate exists."),
    )
    has_valid_rps = fields.Boolean(
        compute="_compute_cert_status",
        store=True,
        string=_("Has valid RPS"),
        help=_("True when at least one active RPS certificate exists."),
    )
    has_valid_course = fields.Boolean(
        compute="_compute_cert_status",
        store=True,
        string=_("Has valid course cert"),
        help=_("True when at least one active kierownik or wychowawca course certificate exists."),
    )
    is_eligible_for_camp = fields.Boolean(
        compute="_compute_cert_status",
        store=True,
        string=_("Eligible for camp"),
        help=_("True when KRK + RPS + course certificate are all valid (PL law Rozp. MEN §4)."),
    )

    @api.depends("cert_ids.is_valid", "cert_ids.cert_type")
    def _compute_cert_status(self):
        for staff in self:
            valid_certs = staff.cert_ids.filtered("is_valid")
            krk_ok = any(c.cert_type == "krk" for c in valid_certs)
            rps_ok = any(c.cert_type == "rps" for c in valid_certs)
            course_ok = any(
                c.cert_type in ("kierownik_course", "wychowawca_course") for c in valid_certs
            )
            staff.has_valid_krk = krk_ok
            staff.has_valid_rps = rps_ok
            staff.has_valid_course = course_ok
            staff.is_eligible_for_camp = krk_ok and rps_ok and course_ok

    # --- §13 hard block: no admission without verified KRK+RSPTS -----------

    @api.constrains("event_id", "state")
    def _check_rspts_before_admission(self):
        """Ustawa Kamilka / art. 21 ustawy z 16.05.2016: staff may not be
        admitted to a camp shift without verified KRK + RSPTS certificates
        (manually accepted by Organizator/Admin, per-season — decision R2).
        Fires on confirmation/activation so legacy draft records migrate
        cleanly; the moment anyone confirms staff — the gate applies."""
        for staff in self:
            if (
                staff.state in ("confirmed", "active")
                and staff.event_id
                and not staff.is_eligible_for_camp
            ):
                raise ValidationError(
                    _(
                        "%(name)s cannot be admitted to '%(event)s': KRK/RSPTS "
                        "verification is missing, expired or not yet accepted "
                        "by the administrator (Ustawa Kamilka; art. 21 ustawy "
                        "z 16.05.2016 — admission without RSPTS verification "
                        "is punishable by arrest or a fine of min. 1000 zł). "
                        "Upload the documents and request admin acceptance."
                    )
                    % {"name": staff.name, "event": staff.event_id.name}
                )

    # ------------------------------------------------------------------
    # PL-law A6/A7 qualification attachments
    # ------------------------------------------------------------------

    krk_attachment = fields.Binary(
        attachment=True,
        string=_("KRK Wyciąg"),
        groups=(
            "fayna_camp_portal.group_camp_organizator,"
            "fayna_camp_portal.group_camp_admin,"
            "fayna_camp_portal.group_camp_kierownik"
        ),
        help=_(
            "Criminal record extract (Krajowy Rejestr Karny) — RODO art. 10 "
            "data: visible only to Organizator/Admin and the Kierownik of this "
            "camp (presents it during KO inspection, decision R3)."
        ),
    )
    krk_expiry_date = fields.Date(
        string=_("KRK ważna do"),
        index=True,
        help=_("Expiry date of the KRK extract."),
    )
    course_certificate_attachment = fields.Binary(
        attachment=True,
        string=_("Zaświadczenie o kursie"),
        help=_("Course completion certificate (wychowawca / kierownik)."),
    )
    course_date = fields.Date(
        string=_("Data ukończenia kursu"),
        help=_("Date of course completion."),
    )
    contract_attachment = fields.Binary(
        attachment=True,
        string=_("Umowa (kontrakt)"),
        help=_("Employment or volunteer contract."),
    )
    responsibility_text = fields.Html(
        string=_("Zakres czynności (A7)"),
        help=_(
            "Detailed responsibilities as required by PL law for each staff member "
            "(Załącznik A7 — zakres czynności)."
        ),
    )

    # ------------------------------------------------------------------
    # Фаза B — Self-onboarding PII fields (groups-gated, RODO)
    # ADR: 09-ADR-FAZA-B-build.md §B4
    # ------------------------------------------------------------------

    pesel = fields.Char(
        string=_("PESEL"),
        groups=(
            "fayna_camp_portal.group_camp_organizator,"
            "fayna_camp_portal.group_camp_admin,"
            "fayna_camp_portal.group_camp_hr"
        ),
        help=_(
            "Polish national ID number (PESEL) — RODO art.6/art.9 PII data. "
            "Visible only to HR / Admin / Organizator."
        ),
    )
    photo = fields.Image(
        string=_("Zdjęcie"),
        max_width=256,
        max_height=256,
        groups=(
            "fayna_camp_portal.group_camp_organizator,"
            "fayna_camp_portal.group_camp_admin,"
            "fayna_camp_portal.group_camp_hr,"
            "fayna_camp_portal.group_camp_candidate"
        ),
        help=_("Candidate / staff photo for ID card."),
    )
    cv_attachment = fields.Binary(
        attachment=True,
        string=_("CV"),
        groups=(
            "fayna_camp_portal.group_camp_organizator,"
            "fayna_camp_portal.group_camp_admin,"
            "fayna_camp_portal.group_camp_hr,"
            "fayna_camp_portal.group_camp_candidate"
        ),
        help=_("Curriculum Vitae uploaded by the candidate."),
    )
    id_document_attachment = fields.Binary(
        attachment=True,
        string=_("Dowód tożsamości"),
        groups=(
            "fayna_camp_portal.group_camp_organizator,"
            "fayna_camp_portal.group_camp_admin,"
            "fayna_camp_portal.group_camp_hr"
        ),
        help=_(
            "Scan of identity document (dowód/paszport) — RODO art.6 PII. "
            "Visible only to HR / Admin / Organizator."
        ),
    )

    # ------------------------------------------------------------------
    # D1-prep — ensure wychowawca system group when staff is confirmed/active
    # ------------------------------------------------------------------

    def _ensure_wychowawca_group(self, user):
        """Grant group_camp_wychowawca to *user* if not already a member.

        Called when a counselor (role='counselor') transitions to confirmed or
        active state so the wychowawca record rules kick in immediately.
        Pattern: recruitment.py:222 (user.sudo().write groups_id [(4, id)]).
        """
        if not user:
            return
        wychowawca_group = self.env.ref(
            "fayna_camp_portal.group_camp_wychowawca", raise_if_not_found=False
        )
        if not wychowawca_group:
            _logger.warning(
                "[camp_operations] group_camp_wychowawca not found — "
                "skipping _ensure_wychowawca_group for user %s",
                user.id,
            )
            return
        if wychowawca_group not in user.groups_id:
            user.sudo().write({"groups_id": [(4, wychowawca_group.id)]})
            _logger.info(
                "[camp_operations] D1-prep: granted group_camp_wychowawca to user %s (%s)",
                user.id,
                user.name,
            )

    def write(self, vals):
        """Hook: grant wychowawca group when a counselor becomes confirmed/active."""
        res = super().write(vals)
        if "state" in vals and vals["state"] in ("confirmed", "active"):
            for staff in self:
                if staff.role == "counselor" and staff.user_id:
                    try:
                        staff._ensure_wychowawca_group(staff.user_id)
                    except Exception:  # noqa: BLE001 — never block staff state change
                        _logger.exception(
                            "[camp_operations] _ensure_wychowawca_group failed for staff %s",
                            staff.id,
                        )
        return res

    # ------------------------------------------------------------------
    # 7-year retention cron (PL law)
    # ------------------------------------------------------------------

    @api.model
    def cron_archive_old_records(self):
        """Archive staff records from events that ended more than 7 years ago."""
        cutoff = fields.Date.today() - timedelta(days=7 * 365)
        old_staff = self.search([("event_id.date_end", "<", cutoff), ("active", "=", True)])
        old_staff.write({"active": False})
        _logger.info("[camp_operations] Archived %d old staff records (7y cutoff)", len(old_staff))
        return True

    @api.model
    def cron_archive_old_participants(self):
        """Archive camp.participant records whose last event ended > 7 years ago.

        RODO + PL Ustawa o rachunkowości — 7-year retention.
        Records are archived (active=False), NOT deleted (RODO art.17(3)(b) exemption).
        """
        cutoff = fields.Date.today() - timedelta(days=7 * 365 + 2)
        participant_model = self.env.get("camp.participant")
        if participant_model is None:
            _logger.warning(
                "[camp_operations] camp.participant model not available — "
                "fayna_camp_portal not fully installed?"
            )
            return False

        candidates = participant_model.with_context(active_test=False).search(
            [("active", "=", True)]
        )
        to_archive = participant_model.browse()
        for participant in candidates:
            event_ends = [
                r.event_id.date_end
                for r in participant.registration_ids
                if r.event_id and r.event_id.date_end
            ]
            if not event_ends:
                continue
            if max(event_ends) < cutoff:
                to_archive |= participant

        if to_archive:
            to_archive.write({"active": False})
        _logger.info(
            "[camp_operations] S.1.5 archival: %d participant(s) archived (7y cutoff: %s)",
            len(to_archive),
            cutoff,
        )
        return True


# ---------------------------------------------------------------------------
# Staff certification record
# ---------------------------------------------------------------------------


class CampStaffCert(models.Model):
    """Staff certification record — PL law Rozp. MEN 2016 §4."""

    _name = "camp.staff.cert"
    _description = "Staff certification record"
    _order = "staff_id, cert_type, issue_date desc"

    staff_id = fields.Many2one(
        "camp.staff",
        required=True,
        ondelete="cascade",
        string=_("Staff member"),
        index=True,
        help=_("Staff member this certificate belongs to."),
    )

    cert_type = fields.Selection(
        [
            ("krk", "KRK — Zaświadczenie o niekaralności"),
            ("rps", "RPS — Rejestr Sprawców"),
            ("kierownik_course", "Kurs kierownika (10h)"),
            ("wychowawca_course", "Kurs wychowawcy (36h)"),
            ("first_aid", "Pierwsza pomoc"),
            ("sanepid", "Zaświadczenie sanepid"),
        ],
        required=True,
        string=_("Certificate type"),
        help=_("Type of the certificate as required by PL law."),
    )

    cert_number = fields.Char(
        string=_("Certificate number"),
        help=_("Official certificate number as printed on the document."),
    )
    issue_date = fields.Date(
        string=_("Issue date"),
        help=_("Date the certificate was issued."),
    )
    expiry_date = fields.Date(
        string=_("Expiry date"),
        index=True,
        help=_("Leave blank for certificates that do not expire."),
    )

    attachment_id = fields.Many2one(
        "ir.attachment",
        string=_("Scanned document"),
        groups=(
            "fayna_camp_portal.group_camp_organizator,"
            "fayna_camp_portal.group_camp_admin,"
            "fayna_camp_portal.group_camp_kierownik"
        ),
        help=_(
            "Scanned copy of the certificate. KRK/RPS scans are criminal-record "
            "data (RODO art. 10) — visible only to Organizator/Admin and the "
            "Kierownik of this staff member's camp (record rule scoped). "
            "Kierownik presents these documents during a KO inspection (R3)."
        ),
    )

    is_valid = fields.Boolean(
        compute="_compute_is_valid",
        store=True,
        string=_("Valid"),
        help=_(
            "True when the certificate is not expired AND has been manually "
            "verified by an Organizator/Admin (Ustawa Kamilka §13 workflow)."
        ),
    )

    notes = fields.Text(
        string=_("Notes"),
        help=_("Additional notes about this certificate."),
    )

    # --- §13 RSPTS manual verification workflow (sprint R2/R3) -------------
    # Docs are uploaded in advance by HR/staff ("ready for acceptance");
    # ONLY Organizator/Admin may accept — checked in write(), not just UI.

    verification_status = fields.Selection(
        [
            ("pending", _("Oczekuje na weryfikację")),
            ("verified", _("Zweryfikowany")),
            ("rejected", _("Odrzucony")),
        ],
        default="pending",
        required=True,
        tracking=True,
        string=_("Verification"),
        help=_(
            "Manual verification by the portal administrator (Organizator/Admin). "
            "KRK/RPS verification is required BEFORE admitting staff to work with "
            "minors (art. 21 ustawy z 16.05.2016; brak weryfikacji = kara aresztu "
            "lub grzywny min. 1000 zł). Re-verified every season (decision R2)."
        ),
    )
    verified_by_id = fields.Many2one(
        "res.users",
        string=_("Verified by"),
        readonly=True,
        copy=False,
        help=_("Administrator who accepted/rejected — set automatically, immutable."),
    )
    verified_date = fields.Datetime(
        string=_("Verified on"),
        readonly=True,
        copy=False,
        help=_("Timestamp of the manual verification — set automatically."),
    )
    season_id = fields.Many2one(
        "fayna.camp.season",
        string=_("Season"),
        index=True,
        help=_(
            "Season this verification is valid for (decision R2: verification "
            "is re-done every season). Empty = legacy record, treat as expired."
        ),
    )

    _VERIFY_PROTECTED = ("verification_status", "verified_by_id", "verified_date")

    def _is_verifier(self):
        return self.env.user.has_group(
            "fayna_camp_portal.group_camp_organizator"
        ) or self.env.user.has_group("fayna_camp_portal.group_camp_admin")

    def action_verify(self):
        if not self._is_verifier():
            raise UserError(
                _("Only the Organizator/Admin may accept RSPTS/KRK verification (§13).")
            )
        self.write(
            {
                "verification_status": "verified",
                "verified_by_id": self.env.user.id,
                "verified_date": fields.Datetime.now(),
            }
        )

    def action_reject(self):
        if not self._is_verifier():
            raise UserError(
                _("Only the Organizator/Admin may reject RSPTS/KRK verification (§13).")
            )
        self.write(
            {
                "verification_status": "rejected",
                "verified_by_id": self.env.user.id,
                "verified_date": fields.Datetime.now(),
            }
        )

    def write(self, vals):
        # Hard server-side gate: status fields only via verifier (not just UI).
        if any(f in vals for f in self._VERIFY_PROTECTED) and not self._is_verifier():
            raise UserError(
                _(
                    "Verification fields are protected — only Organizator/Admin "
                    "may change them (Ustawa Kamilka §13)."
                )
            )
        return super().write(vals)

    @api.depends("expiry_date", "verification_status")
    def _compute_is_valid(self):
        today = fields.Date.today()
        for rec in self:
            not_expired = not rec.expiry_date or rec.expiry_date >= today
            rec.is_valid = not_expired and rec.verification_status == "verified"

    def name_get(self):
        result = []
        for rec in self:
            cert_label = dict(self._fields["cert_type"].selection).get(rec.cert_type, rec.cert_type)
            result.append(
                (
                    rec.id,
                    _("%(staff)s — %(cert)s") % {"staff": rec.staff_id.name, "cert": cert_label},
                )
            )
        return result


# ---------------------------------------------------------------------------
# Staff medical data (RODO art.9 — special-category health data)
# ---------------------------------------------------------------------------


class CampStaffMedical(models.Model):
    """RODO art.9 — special-category health data for camp staff.

    Separated into its own model so that ir.rule can restrict access to
    group_medical_officer only. Regular camp staff and portal users have
    no access to this model.
    """

    _name = "camp.staff.medical"
    _description = "Staff medical data (RODO art.9)"
    _order = "staff_id"

    staff_id = fields.Many2one(
        "camp.staff",
        required=True,
        ondelete="cascade",
        string=_("Staff member"),
        index=True,
        help=_("Staff member this medical record belongs to."),
    )

    allergies = fields.Text(
        string=_("Allergies"),
        help=_("Known allergies and reactions (RODO art.9 special-category data)."),
    )
    chronic_conditions = fields.Text(
        string=_("Chronic conditions"),
        help=_("Chronic medical conditions relevant for camp participation."),
    )
    medications = fields.Text(
        string=_("Current medications"),
        help=_("Medications taken during the camp shift."),
    )
    emergency_medical_notes = fields.Text(
        string=_("Emergency medical notes"),
        help=_("Critical info for emergency responders (blood type, known contraindications)."),
    )
    consent_given = fields.Boolean(
        string=_("RODO art.9 consent obtained"),
        default=False,
        help=_(
            "The staff member has given explicit written consent for processing "
            "this special-category data under RODO art.9 §2(a)."
        ),
    )
    consent_date = fields.Date(
        string=_("Consent date"),
        help=_("Date when written consent was signed."),
    )

    def name_get(self):
        result = []
        for rec in self:
            result.append((rec.id, _("Medical data — %s") % rec.staff_id.name))
        return result


# ---------------------------------------------------------------------------
# Camp Journal (Dziennik wpisów — daily event log)
# ---------------------------------------------------------------------------


class CampJournal(models.Model):
    _name = "camp.journal"
    _description = "Daily camp activity journal"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "event_id, date desc, create_date desc"

    event_id = fields.Many2one(
        "event.event",
        required=True,
        ondelete="cascade",
        string=_("Camp shift (event)"),
        help=_("The specific shift/заїзд this journal entry is for."),
        index=True,
    )

    date = fields.Date(
        required=True,
        string=_("Date"),
        help=_("Date of the journal entry."),
    )
    time = fields.Float(
        string=_("Time (hours)"),
        help=_("Time of the entry (optional; e.g. 14.5 for 14:30)."),
    )

    category = fields.Selection(
        [
            ("activity", "Activity"),
            ("incident", "Incident/accident"),
            ("medical", "Medical event"),
            ("weather", "Weather"),
            ("schedule_change", "Schedule change"),
            ("supply", "Supply/logistics"),
            ("note", "General note"),
        ],
        default="note",
        required=True,
        string=_("Category"),
        tracking=True,
        help=_("Category of the journal entry."),
    )

    title = fields.Char(
        required=True,
        string=_("Title"),
        help=_("Short summary of the journal entry."),
    )
    content = fields.Html(
        required=True,
        string=_("Description"),
        help=_("Detailed description of the event/activity."),
    )

    author_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        string=_("Author"),
        help=_("Staff member who created the entry."),
        index=True,
    )

    group_ids = fields.Char(
        string=_("Involved groups"),
        help=_("e.g. 'Group A', 'Group C' or 'All'."),
    )
    participant_count = fields.Integer(
        string=_("Participant count"),
        help=_("How many children were involved."),
    )

    severity = fields.Selection(
        [
            ("low", "Low (minor issue)"),
            ("medium", "Medium (moderate concern)"),
            ("high", "High (serious)"),
        ],
        string=_("Severity"),
        help=_("For incidents: severity level."),
    )

    attachment_ids = fields.Many2many(
        "ir.attachment",
        string=_("Photos/files"),
        help=_("Photos or supporting documents."),
    )

    active = fields.Boolean(
        default=True,
        string=_("Active"),
        help=_("Inactive entries are hidden from lists but kept for archival."),
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("published", "Published"),
        ],
        default="draft",
        string=_("Status"),
        tracking=True,
        help=_("Draft entries are only visible to staff; published entries feed into reports."),
    )

    @api.model
    def cron_archive_old_records(self):
        """Archive journal records from events that ended more than 7 years ago."""
        cutoff = fields.Date.today() - timedelta(days=7 * 365)
        old_records = self.search([("event_id.date_end", "<", cutoff), ("active", "=", True)])
        old_records.write({"active": False})
        _logger.info(
            "[camp_operations] Archived %d old journal records (7y cutoff)", len(old_records)
        )
        return True


# ---------------------------------------------------------------------------
# Camp Daily Report (Dzienny Raport Obozu — §2.11)
# ---------------------------------------------------------------------------


class CampDailyReport(models.Model):
    _name = "camp.daily.report"
    _description = "Dzienny Raport Obozu (§2.11 daily operations report)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "event_id, report_date desc"
    _rec_name = "name"

    _sql_constraints = [
        (
            "unique_event_date",
            "UNIQUE(event_id, report_date)",
            "A daily report already exists for this event on this date.",
        ),
    ]

    name = fields.Char(
        compute="_compute_name",
        store=True,
        string=_("Report name"),
        help=_("Auto-generated: 'Raport {event} {date}'."),
    )

    @api.depends("event_id", "report_date")
    def _compute_name(self):
        for rec in self:
            if rec.event_id and rec.report_date:
                rec.name = _("Raport %(event)s %(date)s") % {
                    "event": rec.event_id.name,
                    "date": rec.report_date.strftime("%Y-%m-%d"),
                }
            elif rec.event_id:
                rec.name = _("Raport %(event)s") % {"event": rec.event_id.name}
            else:
                rec.name = _("Daily Report (draft)")

    event_id = fields.Many2one(
        "event.event",
        required=True,
        ondelete="cascade",
        string=_("Camp shift (event)"),
        index=True,
        tracking=True,
        help=_("The camp shift this daily report belongs to."),
    )
    report_date = fields.Date(
        required=True,
        default=fields.Date.today,
        string=_("Report date"),
        index=True,
        tracking=True,
        help=_("Calendar date this report covers."),
    )
    author_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        string=_("Author"),
        index=True,
        ondelete="restrict",
        help=_("Staff member who created this report."),
    )

    participants_present = fields.Integer(
        string=_("Participants present"),
        help=_("Number of participants present on this day."),
    )
    participants_absent = fields.Integer(
        string=_("Participants absent"),
        help=_("Number of participants absent on this day."),
    )
    weather = fields.Text(
        string=_("Weather"),
        help=_("Weather conditions for the day (e.g. 'Sunny, 22°C')."),
    )
    weather_condition = fields.Selection(
        [
            ("sunny", "Sunny"),
            ("cloudy", "Cloudy"),
            ("rainy", "Rainy"),
            ("storm", "Storm"),
        ],
        string=_("Weather condition"),
        help=_("Structured weather condition for the day."),
        tracking=True,
    )

    morning_activities = fields.Text(
        string=_("Morning activities"),
        help=_("Activities and schedule for the morning period."),
    )
    afternoon_activities = fields.Text(
        string=_("Afternoon activities"),
        help=_("Activities and schedule for the afternoon period."),
    )
    evening_activities = fields.Text(
        string=_("Evening activities"),
        help=_("Activities and schedule for the evening period."),
    )

    staff_count_present = fields.Integer(
        string=_("Staff present today"),
        help=_("Number of staff on duty on this day."),
    )
    activities_summary = fields.Text(
        string=_("Activities summary"),
        help=_("Overall summary of activities conducted during the day."),
    )
    meals_summary = fields.Text(
        string=_("Meals / nutrition notes"),
        help=_("Meals served and any nutrition or catering notes."),
    )
    health_incidents = fields.Text(
        string=_("Health incidents today"),
        help=_(
            "Health-related incidents today (non-RODO; for RODO art.9 detail "
            "use medical_notes field)."
        ),
    )
    discipline_notes = fields.Text(
        string=_("Discipline notes"),
        help=_("Notes on participant behaviour, discipline issues or resolutions."),
    )
    external_visits = fields.Text(
        string=_("External visits / inspections"),
        help=_("Any external visitors, inspections or official visits today."),
    )
    kierownik_notes = fields.Text(
        string=_("Kierownik private notes"),
        help=_("Private operational notes by the kierownik — not shown on printed report."),
    )

    incidents = fields.Text(
        string=_("Incidents"),
        help=_("Description of any incidents or accidents that occurred."),
    )
    achievements = fields.Text(
        string=_("Achievements"),
        help=_("Positive outcomes, milestones or highlights of the day."),
    )
    challenges = fields.Text(
        string=_("Challenges"),
        help=_("Difficulties encountered and how they were addressed."),
    )
    next_day_plan = fields.Text(
        string=_("Next day plan"),
        help=_("Plan and preparations for the following day."),
    )

    medical_notes = fields.Text(
        string=_("Medical notes"),
        groups=_MEDICAL_GROUP,
        help=_(
            "RODO art.9 health data — visible only to medical officers. "
            "Document medications administered, health events, first aid."
        ),
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
        ],
        default="draft",
        required=True,
        string=_("Status"),
        tracking=True,
        help=_("Lifecycle state of this daily report."),
    )
    active = fields.Boolean(
        default=True,
        string=_("Active"),
        help=_("Inactive reports are hidden from lists but kept for archival."),
    )

    # ------------------------------------------------------------------
    # Python constraint (belt-and-suspenders alongside _sql_constraints)
    # ------------------------------------------------------------------

    @api.constrains("event_id", "report_date")
    def _check_unique_event_date(self):
        for rec in self:
            domain = [
                ("event_id", "=", rec.event_id.id),
                ("report_date", "=", rec.report_date),
                ("id", "!=", rec.id),
            ]
            if self.search_count(domain):
                raise ValidationError(
                    _("A daily report already exists for event '%(event)s' on %(date)s.")
                    % {"event": rec.event_id.name, "date": rec.report_date}
                )

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def action_submit(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Only draft reports can be submitted."))
        self.write({"state": "submitted"})
        _logger.info(
            "[camp_daily_report] Report %d submitted by uid=%d (event %s, date %s)",
            self.id,
            self.env.uid,
            self.event_id.name,
            self.report_date,
        )
        return True

    def action_approve(self):
        self.ensure_one()
        if self.state != "submitted":
            raise UserError(_("Only submitted reports can be approved."))
        if not (
            self.env.user.has_group(_MANAGER_GROUP)
            or self.env.user.has_group("base.group_system")
            or self.env.user.has_group(_ADMIN_GROUP)
        ):
            raise UserError(_("Only camp managers or admins can approve daily reports."))
        self.write({"state": "approved"})
        _logger.info(
            "[camp_daily_report] Report %d approved by uid=%d (event %s, date %s)",
            self.id,
            self.env.uid,
            self.event_id.name,
            self.report_date,
        )
        return True

    def action_back_to_draft(self):
        self.ensure_one()
        if not (
            self.env.user.has_group("base.group_system") or self.env.user.has_group(_ADMIN_GROUP)
        ):
            raise UserError(_("Only admins can revert a daily report to draft."))
        self.write({"state": "draft"})
        return True

    def action_print_report(self):
        return self.env.ref("fayna_camp_portal.report_camp_daily_report").report_action(self)

    # ------------------------------------------------------------------
    # Immutability after approval
    # ------------------------------------------------------------------

    _APPROVED_WRITABLE_FIELDS = frozenset(
        {
            "state",
            "active",
            "message_ids",
            "message_follower_ids",
            "message_partner_ids",
            "activity_ids",
            "message_main_attachment_id",
        }
    )

    def write(self, vals):
        if vals:
            disallowed = set(vals.keys()) - self._APPROVED_WRITABLE_FIELDS
            if disallowed:
                frozen = self.filtered(lambda r: r.state == "approved")
                if frozen:
                    raise UserError(
                        _(
                            "Approved daily reports are locked. "
                            "An admin must revert to draft first "
                            "(blocked fields: %s)."
                        )
                        % ", ".join(sorted(disallowed))
                    )
        return super().write(vals)

    # ------------------------------------------------------------------
    # 7-year retention cron
    # ------------------------------------------------------------------

    @api.model
    def cron_archive_old_records(self):
        cutoff = fields.Date.today() - timedelta(days=7 * 365)
        old_records = self.search([("event_id.date_end", "<", cutoff), ("active", "=", True)])
        old_records.write({"active": False})
        _logger.info(
            "[camp_daily_report] Archived %d old daily report records (7y cutoff)",
            len(old_records),
        )
        return True


# ---------------------------------------------------------------------------
# Camp Report — Sprawozdanie Kierownika
# ---------------------------------------------------------------------------


class CampReport(models.Model):
    _name = "camp.report"
    _description = "Camp shift summary report (Sprawozdanie Kierownika)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "event_id, date_from desc"

    event_id = fields.Many2one(
        "event.event",
        required=True,
        ondelete="cascade",
        string=_("Camp shift (event)"),
        help=_("The specific shift/заїзд this report covers."),
        index=True,
    )

    date_from = fields.Date(
        required=True,
        string=_("Report start date"),
        help=_("Start date of the reporting period."),
    )
    date_to = fields.Date(
        required=True,
        string=_("Report end date"),
        help=_("End date of the reporting period."),
    )

    report_type = fields.Selection(
        [
            ("daily", "Daily summary"),
            ("medical", "Medical incidents"),
            ("nutrition", "Nutrition/catering"),
            ("activities", "Activities & programs"),
            ("incidents", "Incidents & accidents"),
            ("final", "Final (end of shift)"),
        ],
        required=True,
        string=_("Report type"),
        tracking=True,
        help=_("Type of report — determines which sections are required."),
    )

    title = fields.Char(
        required=True,
        string=_("Report title"),
        help=_("e.g. 'Daily Report — July 5', 'Medical Summary'."),
    )

    total_participants = fields.Integer(
        string=_("Total participants"),
        help=_("Total number of participants (legacy field; prefer participant_count_total)."),
    )
    present_count = fields.Integer(
        string=_("Present today"),
        help=_("Number of participants present on the report date."),
    )
    absent_count = fields.Integer(
        string=_("Absent/sick"),
        help=_("Number of participants absent or sick on the report date."),
    )
    staff_count = fields.Integer(
        string=_("Staff count"),
        help=_("Total number of staff on duty."),
    )

    summary = fields.Html(
        string=_("Report content"),
        help=_("Detailed content of the report."),
    )
    highlights = fields.Text(
        string=_("Highlights"),
        help=_("Positive notes, achievements, memorable moments."),
    )
    issues = fields.Text(
        string=_("Issues & actions"),
        help=_("Problems, incidents, corrective actions taken."),
    )
    weather = fields.Char(
        string=_("Weather"),
        help=_("e.g. 'Sunny, 22°C' or 'Rainy, 18°C'."),
    )
    meals_served = fields.Text(
        string=_("Meals served"),
        help=_("Meals served this day (breakfast, lunch, dinner, snacks)."),
    )
    next_day_notes = fields.Text(
        string=_("Notes for next day"),
        help=_("Handover info, preparations needed, follow-ups."),
    )

    # ------------------------------------------------------------------
    # Sprawozdanie Kierownika fields (TZ §2.11)
    # ------------------------------------------------------------------

    kierownik_id = fields.Many2one(
        "camp.staff",
        string=_("Kierownik (author of report)"),
        help=_("Camp director who authored and signs this Sprawozdanie."),
        domain="[('event_id', '=', event_id), ('role', '=', 'director')]",
        index=True,
        ondelete="set null",
    )
    participant_count_total = fields.Integer(
        string=_("Total participants"),
        help=_("Total number of participants in the shift."),
    )
    participant_count_male = fields.Integer(
        string=_("Participants — male"),
        help=_("Male participant count."),
    )
    participant_count_female = fields.Integer(
        string=_("Participants — female"),
        help=_("Female participant count."),
    )
    general_assessment = fields.Text(
        string=_("Ogólna ocena wypoczynku"),
        help=_("Overall assessment of the camp shift — free-form text per PL law sprawozdanie."),
    )
    incidents_summary = fields.Text(
        string=_("Summary of incidents"),
        help=_("Summary of all incidents that occurred during the shift."),
    )
    recommendations = fields.Text(
        string=_("Recommendations for next season"),
        help=_("Organizer-facing recommendations for improvement."),
    )
    submitted_date = fields.Datetime(
        string=_("Submitted on"),
        readonly=True,
        help=_("Timestamp when the report was formally submitted."),
    )
    approved_by_id = fields.Many2one(
        "res.users",
        string=_("Approved by"),
        help=_("Management approval (optional)."),
        index=True,
    )

    author_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        string=_("Author"),
        help=_("Director or senior staff member who authored the report."),
        index=True,
    )
    approver_id = fields.Many2one(
        "res.users",
        string=_("Legacy approver"),
        help=_(
            "Legacy approver field — kept for backward compat; use approved_by_id for new records."
        ),
        index=True,
    )

    # ------------------------------------------------------------------
    # Sprawozdanie sections (TZ §2.11.2)
    # ------------------------------------------------------------------

    section_program = fields.Html(
        string=_("Shift program"),
        help=_("Camp shift program (auto-aggregated from dziennik activities)."),
    )
    section_staff = fields.Html(
        string=_("Staff work"),
        help=_("Staff work — manual notes + automatic hours statistics."),
    )
    section_children = fields.Html(
        string=_("Children"),
        help=_("Children section (attendance %, medical)."),
    )
    section_events = fields.Html(
        string=_("Events & incidents"),
        help=_("Events/incidents (auto-aggregated from dziennik incident notes)."),
    )
    section_kierownik_work = fields.Html(
        string=_("Kierownik own work"),
        help=_("Kierownik own work — free-form text."),
    )
    section_recommendations = fields.Html(
        string=_("Recommendations for organizer"),
        help=_("Recommendations for the organizer — free-form text."),
    )

    # ------------------------------------------------------------------
    # Kierownik signature
    # ------------------------------------------------------------------

    kierownik_signature = fields.Binary(
        attachment=True,
        string=_("Kierownik signature"),
        help=_("Canvas signature captured at submission time."),
    )
    kierownik_signed_date = fields.Datetime(
        string=_("Signed at"),
        readonly=True,
        help=_("Timestamp when the kierownik signed the report."),
    )
    kierownik_signed_by = fields.Many2one(
        "res.users",
        string=_("Signed by"),
        readonly=True,
        help=_("System user who applied the kierownik signature."),
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
        ],
        default="draft",
        required=True,
        string=_("Status"),
        tracking=True,
        help=_("Draft = editable; Submitted = frozen (legal record)."),
    )

    submitted_pdf = fields.Binary(
        attachment=True,
        string=_("Submitted PDF"),
        readonly=True,
        help=_("Frozen PDF snapshot generated at submission time."),
    )

    attachment_ids = fields.Many2many(
        "ir.attachment",
        string=_("Photos/documents"),
        help=_("Supporting photos, documents, evidence."),
    )

    active = fields.Boolean(
        default=True,
        string=_("Active"),
        help=_("Inactive reports are hidden from lists but kept for archival."),
    )

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------

    @api.constrains("state", "kierownik_signature")
    def _check_signature_required_on_submit(self):
        for rec in self:
            if rec.state == "submitted" and not rec.kierownik_signature:
                raise ValidationError(_("Submitted reports must have a kierownik signature."))

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def action_submit(self):
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Only draft reports can be submitted."))
        if not self.kierownik_signature:
            raise UserError(_("Kierownik signature required before submit."))
        if not self.section_kierownik_work:
            raise UserError(
                _("Секція «Власна робота керівника» не може бути порожньою перед поданням звіту.")
            )
        self.write(
            {
                "state": "submitted",
                "kierownik_signed_date": fields.Datetime.now(),
                "kierownik_signed_by": self.env.user.id,
                "submitted_date": fields.Datetime.now(),
            }
        )
        return True

    def action_reset_draft(self):
        return self.action_back_to_draft()

    def action_back_to_draft(self):
        self.ensure_one()
        if not (
            self.env.user.has_group("base.group_system") or self.env.user.has_group(_ADMIN_GROUP)
        ):
            raise UserError(_("Only admin can revert a submitted report."))
        self.write({"state": "draft"})
        return True

    def action_generate_from_data(self):
        """Auto-fill report sections from available data sources."""
        self.ensure_one()
        if self.state == "submitted":
            raise UserError(_("Cannot autofill a submitted report."))

        vals = {}

        try:
            confirmed_regs = self.env["event.registration"].search(
                [("event_id", "=", self.event_id.id), ("state", "in", ("open", "done"))]
            )
            total = len(confirmed_regs)
            if total:
                vals["total_participants"] = total
                vals["participant_count_total"] = total
        except Exception:  # noqa: BLE001
            _logger.debug("[camp.report] event.registration not available for auto-fill")

        try:
            entries = self.env["camp.journal"].search(
                [("event_id", "=", self.event_id.id), ("state", "=", "published")],
                order="date, create_date",
            )
            activities = entries.filtered(lambda e: e.category == "activity")
            adverse = entries.filtered(lambda e: e.category in ("incident", "medical"))

            if activities:
                lines = Markup("").join(
                    Markup("<li><strong>{date} — {title}</strong>{content}</li>").format(
                        date=str(e.date),
                        title=e.title or "",
                        content=Markup("<br/>") + Markup(e.content) if e.content else Markup(""),
                    )
                    for e in activities
                )
                vals["section_program"] = Markup("<ul>") + lines + Markup("</ul>")

            if adverse:
                lines = Markup("").join(
                    Markup("<li><strong>{date} — {title}</strong>{content}</li>").format(
                        date=str(e.date),
                        title=e.title or "",
                        content=Markup("<br/>") + Markup(e.content) if e.content else Markup(""),
                    )
                    for e in adverse
                )
                vals["section_events"] = Markup("<ul>") + lines + Markup("</ul>")
        except Exception:  # noqa: BLE001
            _logger.debug("[camp.report] camp.journal not available for auto-fill")

        if vals:
            self.write(vals)
        return True

    def action_autofill_from_journal(self):
        """Auto-fill section_program and section_events from published journal entries."""
        self.ensure_one()
        if self.state == "submitted":
            raise UserError(_("Cannot autofill a submitted report."))

        entries = self.env["camp.journal"].search(
            [("event_id", "=", self.event_id.id), ("state", "=", "published")],
            order="date, create_date",
        )
        activities = entries.filtered(lambda e: e.category == "activity")
        adverse = entries.filtered(lambda e: e.category in ("incident", "medical"))

        vals = {}
        if activities:
            lines = Markup("").join(
                Markup("<li><strong>{date} — {title}</strong>{content}</li>").format(
                    date=str(e.date),
                    title=e.title or "",
                    content=Markup("<br/>") + Markup(e.content) if e.content else Markup(""),
                )
                for e in activities
            )
            vals["section_program"] = Markup("<ul>") + lines + Markup("</ul>")

        if adverse:
            lines = Markup("").join(
                Markup("<li><strong>{date} — {title}</strong>{content}</li>").format(
                    date=str(e.date),
                    title=e.title or "",
                    content=Markup("<br/>") + Markup(e.content) if e.content else Markup(""),
                )
                for e in adverse
            )
            vals["section_events"] = Markup("<ul>") + lines + Markup("</ul>")

        if vals:
            self.write(vals)
        return True

    # ------------------------------------------------------------------
    # Immutability after submit
    # ------------------------------------------------------------------

    _SUBMITTED_WRITABLE_FIELDS = frozenset(
        {
            "state",
            "submitted_pdf",
            "submitted_date",
            "kierownik_signed_date",
            "kierownik_signed_by",
            "approved_by_id",
            "message_ids",
            "message_follower_ids",
            "message_partner_ids",
            "activity_ids",
            "message_main_attachment_id",
        }
    )

    def write(self, vals):
        if vals:
            disallowed_keys = set(vals.keys()) - self._SUBMITTED_WRITABLE_FIELDS
            if disallowed_keys:
                frozen = self.filtered(lambda r: r.state == "submitted")
                if frozen:
                    raise UserError(
                        _(
                            "Submitted reports are frozen. To edit, an admin must "
                            "first revert to draft (fields blocked: %s)."
                        )
                        % ", ".join(sorted(disallowed_keys))
                    )
        return super().write(vals)

    @api.model
    def _auto_create_report(self, event):
        """Create a blank draft Sprawozdanie for *event* if none exists. Idempotent."""
        existing = self.search(
            [("event_id", "=", event.id), ("report_type", "=", "final")], limit=1
        )
        if existing:
            return existing

        fallback_date = str(fields.Date.today())
        vals = {
            "event_id": event.id,
            "date_from": event.date_begin.date() if event.date_begin else fields.Date.today(),
            "date_to": event.date_end.date() if event.date_end else fields.Date.today(),
            "report_type": "final",
            "title": _("Sprawozdanie kierownika — %s") % (event.name or fallback_date),
        }
        return self.create(vals)

    @api.model
    def cron_archive_old_records(self):
        cutoff = fields.Date.today() - timedelta(days=7 * 365)
        old_records = self.search([("event_id.date_end", "<", cutoff), ("active", "=", True)])
        old_records.write({"active": False})
        _logger.info(
            "[camp_operations] Archived %d old report records (7y cutoff)", len(old_records)
        )
        return True


# ---------------------------------------------------------------------------
# Program Wypoczynku — Załącznik 9 (legal document submitted to kuratoria)
# ---------------------------------------------------------------------------


class CampProgramWypoczynku(models.Model):
    _name = "camp.program.wypoczynku"
    _description = "Program Wypoczynku (Załącznik 9 — oficjalny dokument MEN)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "event_id, create_date desc"
    _rec_name = "name"

    _sql_constraints = [
        (
            "unique_program_event_version",
            "UNIQUE(event_id, version)",
            "A program with this version already exists for this event. "
            "Use 'New Version' to create a new revision.",
        ),
    ]

    name = fields.Char(
        required=True,
        tracking=True,
        string=_("Name"),
        default=lambda self: _("Program Wypoczynku"),
        help=_("Display name of this Program Wypoczynku document."),
    )

    event_id = fields.Many2one(
        "event.event",
        required=True,
        ondelete="cascade",
        string=_("Camp shift (event)"),
        tracking=True,
        index=True,
        help=_("The camp shift this program document is for."),
    )

    kierownik_id = fields.Many2one(
        "camp.staff",
        domain=[("role", "=", "leader")],
        string=_("Kierownik"),
        index=True,
        help=_("Kierownik wypoczynku listed on this document."),
    )

    staff_ids = fields.Many2many(
        "camp.staff",
        "camp_program_staff_rel",
        "program_id",
        "staff_id",
        string=_("Kadra"),
        help=_("Staff members listed in this Program Wypoczynku (Załącznik 9 kadra section)."),
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("submitted", "Submitted to kuratoria"),
        ],
        default="draft",
        required=True,
        string=_("Status"),
        tracking=True,
        help=_("Lifecycle state — submitted = legally filed with Kuratorium Oświaty."),
    )

    version = fields.Integer(
        default=1,
        readonly=True,
        string=_("Version"),
        help=_("Version number — incremented each time the program is reset to draft."),
    )

    # Załącznik 9 — 6 content sections
    section_cel = fields.Html(
        string=_("Cel wypoczynku"),
        help=_("Cel wypoczynku — aims and objectives of the camp (Załącznik 9 §1)."),
    )
    section_tematyka = fields.Html(
        string=_("Tematyka"),
        help=_("Tematyka wypoczynku — camp theme/topic (Załącznik 9 §2)."),
    )
    section_wychowawcze = fields.Html(
        string=_("Zagadnienia wychowawcze"),
        help=_("Zagadnienia wychowawcze — educational aspects (Załącznik 9 §3)."),
    )
    section_formy = fields.Html(
        string=_("Formy i metody realizacji"),
        help=_("Formy i metody realizacji — forms and methods (Załącznik 9 §4)."),
    )
    section_harmonogram = fields.Html(
        string=_("Harmonogram (ogólny)"),
        help=_("Harmonogram ogólny — general schedule overview (Załącznik 9 §5)."),
    )
    section_bezpieczenstwo = fields.Html(
        string=_("Zapewnienie bezpieczeństwa"),
        help=_("Zapewnienie bezpieczeństwa — safety measures (Załącznik 9 §6)."),
    )

    submitted_date = fields.Date(
        readonly=True,
        tracking=True,
        string=_("Submitted date"),
        help=_("Date when the program was submitted to kuratoria."),
    )
    approved_by_id = fields.Many2one(
        "res.users",
        readonly=True,
        tracking=True,
        string=_("Approved by"),
        index=True,
        help=_("User who approved this program."),
    )
    approved_date = fields.Date(
        readonly=True,
        string=_("Approved date"),
        help=_("Date when the program was approved."),
    )

    retention_until = fields.Date(
        compute="_compute_retention_until",
        store=True,
        string=_("Retain until"),
        help=_("7-year retention deadline per Polish law (event end date + 7 years)."),
    )

    @api.depends("event_id", "event_id.date_end")
    def _compute_retention_until(self):
        for rec in self:
            if rec.event_id and rec.event_id.date_end:
                end = rec.event_id.date_end
                if hasattr(end, "date"):
                    end = end.date()
                rec.retention_until = end + relativedelta(years=7)
            else:
                rec.retention_until = False

    def action_approve(self):
        self.ensure_one()
        if not self.env.user.has_group(_MANAGER_GROUP) and not self.env.user.has_group(
            "base.group_system"
        ):
            raise AccessError(_("Only Camp Managers can approve a Program Wypoczynku."))
        if self.state == "approved":
            raise UserError(_("This program has already been approved."))
        if self.state == "submitted":
            raise UserError(_("A submitted program cannot be approved again."))
        self.write(
            {
                "state": "approved",
                "approved_date": fields.Date.today(),
                "approved_by_id": self.env.user.id,
            }
        )
        _logger.info(
            "[camp_program] Program %d approved by uid=%d (event %s)",
            self.id,
            self.env.uid,
            self.event_id.name,
        )
        return True

    def action_submit(self):
        self.ensure_one()
        if self.state != "approved":
            raise UserError(_("Only approved programs can be submitted to kuratoria."))
        self.write({"state": "submitted", "submitted_date": fields.Date.today()})
        _logger.info(
            "[camp_program] Program %d submitted to kuratoria (event %s)",
            self.id,
            self.event_id.name,
        )
        return True

    def action_reset_draft(self):
        self.ensure_one()
        if self.state != "approved":
            raise UserError(_("Only approved programs can be reset to draft."))
        self.write(
            {
                "state": "draft",
                "version": self.version + 1,
                "approved_date": False,
                "approved_by_id": False,
            }
        )
        _logger.info(
            "[camp_program] Program %d reset to draft v%d (event %s)",
            self.id,
            self.version,
            self.event_id.name,
        )
        return True

    def action_new_version(self):
        self.ensure_one()
        new_program = self.copy(
            {
                "version": self.version + 1,
                "state": "draft",
                "approved_date": False,
                "approved_by_id": False,
                "submitted_date": False,
            }
        )
        _logger.info(
            "[camp_program] New version %d created from record %d (event %s)",
            new_program.version,
            self.id,
            self.event_id.name,
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "camp.program.wypoczynku",
            "res_id": new_program.id,
            "view_mode": "form",
        }

    def action_print_program(self):
        self.ensure_one()
        return self.env.ref("fayna_camp_portal.action_report_camp_program").report_action(self)


# ---------------------------------------------------------------------------
# Activity template library
# ---------------------------------------------------------------------------


class CampActivityTemplate(models.Model):
    _name = "camp.activity.template"
    _description = "Reusable activity template for camp programs"
    _order = "category, name"

    _sql_constraints = [
        (
            "name_category_unique",
            "UNIQUE(name, category)",
            "An activity template with this name and category already exists.",
        )
    ]

    name = fields.Char(
        required=True,
        string=_("Activity name"),
        help=_("e.g. 'Morning warm-up run', 'Creative painting', 'Camp bonfire'."),
    )
    category = fields.Selection(
        [
            ("sport", "Sport"),
            ("creative", "Twórcze"),
            ("educational", "Edukacyjne"),
            ("rest", "Odpoczynek"),
            ("evening", "Ognisko / Wieczornica"),
            ("hygiene", "Higiena"),
            ("meal", "Posiłki"),
        ],
        required=True,
        string=_("Category"),
        help=_("Activity category used for schedule filtering and reporting."),
        index=True,
    )
    default_duration_minutes = fields.Integer(
        string=_("Default duration (min)"),
        help=_("Typical activity length in minutes; used as a planning hint."),
        default=60,
    )
    min_age = fields.Integer(
        string=_("Min age"),
        help=_("Minimum recommended participant age (leave 0 for no restriction)."),
    )
    max_age = fields.Integer(
        string=_("Max age"),
        help=_("Maximum recommended participant age (leave 0 for no restriction)."),
    )
    indoor_only = fields.Boolean(
        string=_("Indoor only"),
        help=_("This activity can only be conducted indoors."),
    )
    outdoor_only = fields.Boolean(
        string=_("Outdoor only"),
        help=_("This activity must be conducted outdoors (weather-dependent)."),
    )
    description = fields.Text(
        string=_("Description"),
        help=_("Full activity description: objectives, materials needed, safety notes."),
    )
    active = fields.Boolean(
        default=True,
        string=_("Active"),
        help=_("Inactive templates are hidden from the planning UI."),
    )


# ---------------------------------------------------------------------------
# Structured program (day-by-day plan, created before camp starts)
# ---------------------------------------------------------------------------


class CampProgramStructured(models.Model):
    _name = "camp.program.structured"
    _description = "Camp structured day-by-day program"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "event_id, is_rain_plan, id"
    _rec_name = "name"

    event_id = fields.Many2one(
        "event.event",
        required=True,
        ondelete="restrict",
        string=_("Camp shift (event)"),
        index=True,
        tracking=True,
        help=_("The camp shift this structured program belongs to."),
    )
    name = fields.Char(
        compute="_compute_name",
        store=True,
        string=_("Program name"),
        help=_("Auto-generated from event name and plan variant."),
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("published", "Published"),
        ],
        default="draft",
        required=True,
        string=_("Status"),
        tracking=True,
        help=_("Published programs are visible to counselors for execution."),
    )
    is_rain_plan = fields.Boolean(
        default=False,
        string=_("Rain plan (Plan B)"),
        help=_("When True, this is the rainy-day backup program variant."),
        tracking=True,
    )
    day_ids = fields.One2many(
        "camp.program.day",
        "program_id",
        string=_("Days"),
        help=_("Day-by-day schedule entries."),
    )
    day_count = fields.Integer(
        compute="_compute_day_count",
        store=True,
        string=_("# Days"),
        help=_("Number of days in this program."),
    )
    notes = fields.Text(
        string=_("General notes"),
        help=_("Overall program notes, objectives, special requirements."),
    )

    # ── Рамковий день (ADR Фаза A §1) ─────────────────────────────────────
    wake_time = fields.Float(
        default=7.0,
        string=_("Pobudka (hh.mm)"),
        help=_("Wake-up time in hour.decimal format (e.g. 7.0 = 07:00)."),
    )
    breakfast = fields.Float(
        default=8.0,
        string=_("Śniadanie"),
        help=_("Breakfast start time."),
    )
    lunch = fields.Float(
        default=13.0,
        string=_("Obiad"),
        help=_("Lunch start time."),
    )
    afternoon_rest = fields.Float(
        default=14.0,
        string=_("Cisza poobiednia"),
        help=_("Afternoon rest start time."),
    )
    snack = fields.Float(
        default=16.0,
        string=_("Podwieczorek"),
        help=_("Snack start time."),
    )
    dinner = fields.Float(
        default=18.0,
        string=_("Kolacja"),
        help=_("Dinner start time."),
    )
    lights_out = fields.Float(
        default=22.0,
        string=_("Cisza nocna"),
        help=_("Lights-out / silence start time."),
    )
    meal_duration = fields.Float(
        default=0.75,
        string=_("Czas posiłku (h)"),
        help=_("Default meal duration in hours (e.g. 0.75 = 45 min)."),
    )
    rest_duration = fields.Float(
        default=1.0,
        string=_("Czas ciszy poobiedniej (h)"),
        help=_("Afternoon rest duration in hours."),
    )

    @api.constrains("wake_time", "lights_out")
    def _check_sleep_duration(self):
        for rec in self:
            if rec.lights_out <= rec.wake_time:
                raise ValidationError(
                    _("Cisza nocna must be after wake-up time (lights_out > wake_time).")
                )
            sleep_hours = (24.0 - rec.lights_out) + rec.wake_time
            if sleep_hours < 9.0:
                raise ValidationError(
                    _(
                        "Minimum sleep time is 9 hours (MEN regulation). "
                        "Current: %(h).1f h (lights_out=%(lo)s, wake=%(w)s).",
                        h=sleep_hours,
                        lo=rec.lights_out,
                        w=rec.wake_time,
                    )
                )

    @api.depends("event_id", "is_rain_plan")
    def _compute_name(self):
        for rec in self:
            event_name = rec.event_id.name if rec.event_id else _("(no event)")
            suffix = _("(Rain Plan)") if rec.is_rain_plan else ""
            rec.name = (f"Program: {event_name} {suffix}").strip()

    @api.depends("day_ids")
    def _compute_day_count(self):
        for rec in self:
            rec.day_count = len(rec.day_ids)

    def action_publish(self):
        self.ensure_one()
        if self.state == "published":
            raise UserError(_("This program is already published."))
        self.write({"state": "published"})
        return True

    def action_back_to_draft(self):
        self.ensure_one()
        self.write({"state": "draft"})
        return True

    def action_print_program(self):
        self.ensure_one()
        return self.env.ref("fayna_camp_portal.camp_program_report_action").report_action(self)

    # ── ADR Фаза C — прогрес наповнення та гейт виховника ────────────────

    _FREE_MARKER = "Czas wolny — do wypełnienia"

    def _get_free_lines(self):
        """Return activity lines that are considered unfilled free slots."""
        return self.day_ids.mapped("activity_line_ids").filtered(
            lambda l: l.category == "free" or l.title == self._FREE_MARKER
        )

    def _get_filled_lines(self):
        """Return free-owned lines that have been concretely filled by wychowawca."""
        return self.day_ids.mapped("activity_line_ids").filtered(
            lambda l: l.owner_role == "wychowawca"
            and l.category != "free"
            and l.title != self._FREE_MARKER
        )

    @api.depends("day_ids.activity_line_ids.category", "day_ids.activity_line_ids.title",
                 "day_ids.activity_line_ids.owner_role")
    def _compute_fill_progress(self):
        for rec in self:
            all_wychowawca = rec.day_ids.mapped("activity_line_ids").filtered(
                lambda l: l.owner_role == "wychowawca"
            )
            total = len(all_wychowawca)
            if total == 0:
                rec.free_total = 0
                rec.free_filled = 0
                rec.fill_progress = 100.0
            else:
                filled = len(all_wychowawca.filtered(
                    lambda l: l.category != "free" and l.title != rec._FREE_MARKER
                ))
                rec.free_total = total
                rec.free_filled = filled
                rec.fill_progress = round(100.0 * filled / total, 1)

    free_total = fields.Integer(
        compute="_compute_fill_progress",
        string=_("Free slots total"),
        help=_("Total wychowawca-owned slots (free + filled)."),
    )
    free_filled = fields.Integer(
        compute="_compute_fill_progress",
        string=_("Free slots filled"),
        help=_("Wychowawca-owned slots already filled in."),
    )
    fill_progress = fields.Float(
        compute="_compute_fill_progress",
        string=_("Fill progress (%)"),
        help=_("Percentage of wychowawca slots filled. 100 % unlocks submission."),
    )
    wychowawca_done = fields.Boolean(
        default=False,
        string=_("Wychowawca done"),
        tracking=True,
        help=_("Set to True by action_wychowawca_submit when all free slots are filled."),
    )

    def action_wychowawca_submit(self):
        """Gate: all wychowawca slots must be filled before submission."""
        self.ensure_one()
        unfilled = self._get_free_lines()
        if unfilled:
            titles = ", ".join(unfilled.mapped("title")[:5])
            raise UserError(
                _("Uzupełnij wszystkie wolne sloty przed wysłaniem. Brakuje: %s") % titles
            )
        self.wychowawca_done = True
        return True

    # ── ADR Фаза A §2 — генератор скелету ────────────────────────────────

    @api.model
    def _generate_skeleton(self, event, structured):
        """Generate day records + fixed skeleton lines for every day of the camp.

        Args:
            event (event.event): The camp shift.
            structured (camp.program.structured): The structured program record.

        Returns:
            list[camp.program.day]: Created day records.
        """
        from datetime import date as date_cls, timedelta as td

        s = structured
        day_model = self.env["camp.program.day"]
        line_model = self.env["camp.program.activity.line"]

        start = event.date_begin.date() if hasattr(event.date_begin, "date") else event.date_begin
        end = event.date_end.date() if hasattr(event.date_end, "date") else event.date_end

        created_days = []
        current = start
        while current <= end:
            day = day_model.create(
                {
                    "program_id": s.id,
                    "date": current,
                }
            )

            # Fixed skeleton lines (is_skeleton=True)
            skeleton_lines = [
                {
                    "day_id": day.id,
                    "time_from": s.breakfast,
                    "time_to": s.breakfast + s.meal_duration,
                    "title": "Śniadanie",
                    "category": "meal",
                    "is_skeleton": True,
                    "is_locked": True,
                    "owner_role": "kierownik",
                },
                {
                    "day_id": day.id,
                    "time_from": s.lunch,
                    "time_to": s.lunch + s.meal_duration,
                    "title": "Obiad",
                    "category": "meal",
                    "is_skeleton": True,
                    "is_locked": True,
                    "owner_role": "kierownik",
                },
                {
                    "day_id": day.id,
                    "time_from": s.afternoon_rest,
                    "time_to": s.afternoon_rest + s.rest_duration,
                    "title": "Cisza poobiednia",
                    "category": "rest",
                    "is_skeleton": True,
                    "is_locked": True,
                    "owner_role": "kierownik",
                },
                {
                    "day_id": day.id,
                    "time_from": s.snack,
                    "time_to": s.snack + 0.25,
                    "title": "Podwieczorek",
                    "category": "meal",
                    "is_skeleton": True,
                    "is_locked": True,
                    "owner_role": "kierownik",
                },
                {
                    "day_id": day.id,
                    "time_from": s.dinner,
                    "time_to": s.dinner + s.meal_duration,
                    "title": "Kolacja",
                    "category": "meal",
                    "is_skeleton": True,
                    "is_locked": True,
                    "owner_role": "kierownik",
                },
                {
                    "day_id": day.id,
                    "time_from": s.lights_out,
                    "time_to": 24.0,
                    "title": "Cisza nocna",
                    "category": "sleep",
                    "is_skeleton": True,
                    "is_locked": True,
                    "owner_role": "kierownik",
                },
            ]
            # Night sleep that wraps midnight: 0:00 → wake_time
            skeleton_lines.append(
                {
                    "day_id": day.id,
                    "time_from": 0.0,
                    "time_to": s.wake_time,
                    "title": "Sen (noc)",
                    "category": "sleep",
                    "is_skeleton": True,
                    "is_locked": True,
                    "owner_role": "kierownik",
                }
            )
            line_model.create(skeleton_lines)

            # Fill free gaps between wake_time and lights_out
            self._fill_free_hours(day)

            created_days.append(day)
            current += td(days=1)

        return created_days

    @api.model
    def _fill_free_hours(self, day):
        """Insert 'Czas wolny' lines into gaps [wake..lights_out] > 0.25 h.

        Args:
            day (camp.program.day): The day record (must already have skeleton lines).
        """
        structured = day.program_id
        wake = structured.wake_time
        lights = structured.lights_out

        # Collect only lines within [wake, lights_out] window (excludes sleep wraps)
        busy = []
        for line in day.activity_line_ids.sorted("time_from"):
            tf = line.time_from
            tt = line.time_to
            # Clamp to [wake, lights] window
            if tt <= wake or tf >= lights:
                continue
            tf = max(tf, wake)
            tt = min(tt, lights)
            if tt > tf:
                busy.append((tf, tt))

        # Merge overlapping/adjacent slots
        merged = []
        for tf, tt in sorted(busy):
            if merged and tf <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], tt))
            else:
                merged.append((tf, tt))

        # Detect gaps
        cursor = wake
        free_vals = []
        for tf, tt in merged:
            if tf - cursor > 0.25:
                free_vals.append(
                    {
                        "day_id": day.id,
                        "time_from": cursor,
                        "time_to": tf,
                        "title": "Czas wolny — do wypełnienia",
                        "category": "free",
                        "is_skeleton": True,
                        "owner_role": "wychowawca",
                    }
                )
            cursor = max(cursor, tt)
        # Trailing gap
        if lights - cursor > 0.25:
            free_vals.append(
                {
                    "day_id": day.id,
                    "time_from": cursor,
                    "time_to": lights,
                    "title": "Czas wolny — do wypełnienia",
                    "category": "free",
                    "is_skeleton": True,
                    "owner_role": "wychowawca",
                }
            )
        if free_vals:
            self.env["camp.program.activity.line"].create(free_vals)


# ---------------------------------------------------------------------------
# Program day (one day within a structured program)
# ---------------------------------------------------------------------------


class CampProgramDay(models.Model):
    _name = "camp.program.day"
    _description = "Camp program — single day"
    _order = "date"
    _rec_name = "display_name"

    program_id = fields.Many2one(
        "camp.program.structured",
        required=True,
        ondelete="cascade",
        string=_("Program"),
        index=True,
        help=_("The structured program this day belongs to."),
    )
    date = fields.Date(
        required=True,
        string=_("Date"),
        help=_("Calendar date for this day of the program."),
    )
    day_number = fields.Integer(
        compute="_compute_day_number",
        store=True,
        string=_("Day #"),
        help=_("Day number within the shift (1-based, computed from event start)."),
    )
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
        string=_("Day label"),
        help=_("Human-readable label: 'Day N — YYYY-MM-DD'."),
    )
    activity_line_ids = fields.One2many(
        "camp.program.activity.line",
        "day_id",
        string=_("Activity lines"),
        help=_("Time-boxed activity slots for this day."),
    )
    notes = fields.Text(
        string=_("Day notes"),
        help=_("General notes for the day (weather, special circumstances, etc.)."),
    )

    @api.depends("date", "program_id", "program_id.event_id", "program_id.event_id.date_begin")
    def _compute_day_number(self):
        for rec in self:
            if rec.date and rec.program_id and rec.program_id.event_id:
                start = rec.program_id.event_id.date_begin
                if start:
                    if hasattr(start, "date"):
                        start = start.date()
                    rec.day_number = (rec.date - start).days + 1
                else:
                    rec.day_number = 0
            else:
                rec.day_number = 0

    @api.depends("date", "day_number")
    def _compute_display_name(self):
        for rec in self:
            if rec.date:
                rec.display_name = _("Day %(n)s — %(d)s", n=rec.day_number or "?", d=rec.date)
            else:
                rec.display_name = _("(no date)")


# ---------------------------------------------------------------------------
# Activity line (single time slot within a program day)
# ---------------------------------------------------------------------------


class CampProgramActivityLine(models.Model):
    _name = "camp.program.activity.line"
    _description = "Camp program — activity line (time slot)"
    _order = "time_from, id"

    day_id = fields.Many2one(
        "camp.program.day",
        required=True,
        ondelete="cascade",
        string=_("Program day"),
        index=True,
        help=_("The program day this time slot belongs to."),
    )
    time_from = fields.Float(
        string=_("From (hh.mm)"),
        help=_("Start time in hour.minute format (e.g. 9.0 = 09:00, 14.5 = 14:30)."),
    )
    time_to = fields.Float(
        string=_("To (hh.mm)"),
        help=_("End time in hour.minute format."),
    )
    activity_template_id = fields.Many2one(
        "camp.activity.template",
        string=_("Activity template"),
        ondelete="set null",
        help=_("Pick a reusable template — title will be pre-filled automatically."),
    )
    title = fields.Char(
        required=True,
        string=_("Activity title"),
        help=_("Name or description of the activity. Auto-filled from template if selected."),
    )
    location = fields.Char(
        string=_("Location"),
        help=_("Where this activity takes place (e.g. 'Sports field', 'Dining hall')."),
    )
    responsible_id = fields.Many2one(
        "camp.staff",
        string=_("Responsible (staff)"),
        ondelete="set null",
        help=_("Staff member leading this activity."),
    )
    notes = fields.Text(
        string=_("Notes"),
        help=_("Preparation notes, materials needed, special instructions."),
    )

    # ── Фаза A — категорія та замки (ADR §1) ──────────────────────────────
    category = fields.Selection(
        [
            ("meal", "Posiłek"),
            ("rest", "Odpoczynek"),
            ("sleep", "Cisza nocna"),
            ("free", "Czas wolny — do wypełnienia"),
            ("activity", "Zajęcia"),
        ],
        default="activity",
        string=_("Kategoria"),
        help=_("Activity category: meal / rest / sleep / free slot / regular activity."),
    )
    is_skeleton = fields.Boolean(
        default=False,
        string=_("Skeleton"),
        help=_("True if this line was auto-generated by the skeleton generator."),
    )
    is_locked = fields.Boolean(
        default=False,
        string=_("Locked"),
        help=_("Kierownik lock: wychowawca cannot edit this line (enforced in Phase C)."),
    )
    owner_role = fields.Selection(
        [
            ("kierownik", "Kierownik"),
            ("wychowawca", "Wychowawca"),
        ],
        default="kierownik",
        string=_("Owner role"),
        help=_("Role that owns this line. Wychowawca can only edit owner_role=wychowawca lines."),
    )

    # ── Фаза C — skeleton label (readonly, inherited from skeleton generator) ──
    skeleton_label = fields.Char(
        string=_("Skeleton label"),
        readonly=True,
        help=_("General activity name from the skeleton. Wychowawca fills in the concrete title."),
    )

    @api.constrains(
        "is_locked", "owner_role", "title", "time_from", "time_to",
        "activity_template_id", "location", "responsible_id", "notes", "category",
    )
    def _check_locked_write(self):
        """Phase C ENFORCE: wychowawca cannot write locked or kierownik-owned lines."""
        if self.env.su:
            return
        if self.env.user.has_group("fayna_camp_portal.group_camp_kierownik"):
            return
        if self.env.user.has_group("fayna_camp_portal.group_camp_organizator"):
            return
        for line in self:
            if line.is_locked or line.owner_role == "kierownik":
                raise ValidationError(
                    _("Slot zablokowany przez kierownika — wychowawca nie edytuje: %s") % line.title
                )

    @api.onchange("activity_template_id")
    def _onchange_activity_template(self):
        if self.activity_template_id and not self.title:
            self.title = self.activity_template_id.name
        if self.activity_template_id and self.activity_template_id.default_duration_minutes:
            mins = self.activity_template_id.default_duration_minutes
            if self.time_from:
                hours = int(self.time_from)
                frac = (self.time_from - hours) * 60 + mins
                self.time_to = hours + frac / 60


# ---------------------------------------------------------------------------
# Camp Program (execution tracking — per shift, per day)
# ---------------------------------------------------------------------------


class CampProgram(models.Model):
    _name = "camp.program"
    _description = "Camp program execution per shift"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "event_id, sequence"

    event_id = fields.Many2one(
        "event.event",
        required=True,
        ondelete="cascade",
        string=_("Camp shift (event)"),
        help=_("The specific shift/заїзд this program entry is for."),
        index=True,
    )
    product_tmpl_id = fields.Many2one(
        "product.template",
        related="event_id.camp_program_id",
        store=True,
        string=_("Camp template"),
        help=_("Camp product template — derived from the event."),
    )
    sequence = fields.Integer(
        default=10,
        string=_("Sequence"),
        help=_("Order within the shift program list."),
    )
    name = fields.Char(
        required=True,
        string=_("Program title"),
        help=_("e.g. 'Morning hike', 'Team building activity'."),
    )
    schedule_entry_id = fields.Many2one(
        "camp.schedule.entry",
        string=_("Scheduled activity"),
        help=_("Link to the master schedule (if this program is a variant of master schedule)."),
        domain="[('product_tmpl_id', '=', product_tmpl_id)]",
    )
    date = fields.Date(
        required=True,
        string=_("Date of activity"),
        tracking=True,
        help=_("Calendar date this program entry was executed."),
    )
    start_time = fields.Float(
        string=_("Start time (hours, e.g. 9.5 for 09:30)"),
        help=_("Start time in decimal hours."),
    )
    end_time = fields.Float(
        string=_("End time"),
        help=_("End time in decimal hours."),
    )
    plan_variant = fields.Selection(
        [
            ("a", "Plan A (sunny/ideal)"),
            ("b", "Plan B (rainy/backup)"),
        ],
        default="a",
        string=_("Which plan executed"),
        help=_("Which variant of the schedule was executed due to weather/circumstances."),
        tracking=True,
    )
    description = fields.Html(
        string=_("Program description"),
        help=_("What happened, notes, observations."),
    )
    photo_attachment_ids = fields.Many2many(
        "ir.attachment",
        string=_("Photos"),
        help=_("Photos from this activity."),
    )
    incidents = fields.Text(
        string=_("Incidents or deviations"),
        help=_("Any incidents, accidents, deviations from plan."),
    )
    participant_count = fields.Integer(
        string=_("Participants"),
        help=_("How many kids participated."),
    )
    staff_ids = fields.Many2many(
        "camp.staff",
        string=_("Staff lead"),
        help=_("Which staff members led this activity."),
    )
    theme = fields.Char(
        string=_("Theme"),
        translate=True,
        help=_("Day theme, e.g. 'Piratów', 'Kosmosu', 'Olimpijskie'."),
    )
    weather_plan = fields.Selection(
        [
            ("sun", "Plan A (Sunny)"),
            ("rain", "Plan B (Rainy)"),
        ],
        string=_("Weather plan"),
        help=_("Which weather-variant plan is in effect for this day."),
    )
    program_activity_ids = fields.One2many(
        "camp.program.activity",
        "program_id",
        string=_("Activities"),
        help=_("Inline activity slots (program builder flow)."),
    )
    activity_count = fields.Integer(
        compute="_compute_activity_count",
        store=True,
        string=_("# Activities"),
        help=_("Number of activity slots in this program entry."),
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("scheduled", "Scheduled"),
            ("ongoing", "Ongoing"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        string=_("Status"),
        tracking=True,
        help=_("Execution lifecycle state of this program entry."),
    )
    is_published = fields.Boolean(
        string=_("Published"),
        default=False,
        help=_("When True, this program is visible to portal users (parents)."),
        tracking=True,
    )

    @api.depends("program_activity_ids")
    def _compute_activity_count(self):
        for rec in self:
            rec.activity_count = len(rec.program_activity_ids)

    @api.onchange("schedule_entry_id")
    def _onchange_schedule_entry(self):
        if self.schedule_entry_id:
            activity = (
                self.schedule_entry_id.activity_a
                if self.plan_variant == "a"
                else self.schedule_entry_id.activity_b
            )
            if activity:
                self.name = activity

    def action_approve(self):
        for record in self:
            if record.state != "draft":
                continue
            record.write({"state": "approved"})

    def action_schedule(self):
        for record in self:
            if record.state not in ("draft", "approved"):
                continue
            record.write({"state": "scheduled"})

    def action_start(self):
        for record in self:
            record.write({"state": "ongoing"})

    def action_complete(self):
        for record in self:
            record.write({"state": "completed"})

    def action_cancel(self):
        for record in self:
            record.write({"state": "cancelled"})

    @api.constrains("start_time", "end_time")
    def _check_time_order(self):
        for rec in self:
            if rec.start_time and rec.end_time and rec.end_time <= rec.start_time:
                raise ValidationError(
                    _(
                        "End time must be later than start time on program '%(name)s'.",
                        name=rec.name,
                    )
                )


# ---------------------------------------------------------------------------
# Program activity slot (inline within CampProgram — program builder)
# ---------------------------------------------------------------------------


class CampProgramActivity(models.Model):
    _name = "camp.program.activity"
    _description = "Camp program — activity slot"
    _order = "time_start, id"

    program_id = fields.Many2one(
        "camp.program",
        required=True,
        ondelete="cascade",
        string=_("Program"),
        index=True,
        help=_("The program entry this activity slot belongs to."),
    )
    time_start = fields.Float(
        string=_("Start time"),
        help=_("Start time in decimal hours (e.g. 9.5 = 09:30)."),
    )
    time_end = fields.Float(
        string=_("End time"),
        help=_("End time in decimal hours."),
    )
    activity_name = fields.Char(
        required=True,
        string=_("Activity"),
        translate=True,
        help=_("Name or description of the activity."),
    )
    location = fields.Char(
        string=_("Location"),
        translate=True,
        help=_("Where this activity takes place."),
    )
    responsible_id = fields.Many2one(
        "res.partner",
        string=_("Responsible"),
        ondelete="set null",
        help=_("Person responsible for leading this activity."),
    )
    activity_type = fields.Selection(
        [
            ("sport", "Sport"),
            ("creative", "Creative"),
            ("educational", "Educational"),
            ("meal", "Meal"),
            ("rest", "Rest"),
            ("other", "Other"),
        ],
        string=_("Type"),
        index=True,
        help=_("Activity type — used for program statistics and reporting."),
    )
    risk_water = fields.Boolean(
        string=_("Water activity (§7)"),
        help=_(
            "Activity takes place on/in water (kąpiel, kajaki, basen). "
            "Triggers the hard block for participants flagged with hydrophobia "
            "(wzór 2026 pkt 9, sprint decision R1) and §7 lifeguard validation."
        ),
    )
    risk_heights = fields.Boolean(
        string=_("Heights activity"),
        help=_(
            "Activity involves heights (park linowy, wspinaczka, zjazdy). "
            "Triggers the hard block for participants flagged with fear of heights "
            "(wzór 2026 pkt 9, sprint decision R1)."
        ),
    )
    notes = fields.Text(
        string=_("Notes"),
        help=_("Preparation notes, materials needed, special instructions."),
    )
    time_label = fields.Char(
        compute="_compute_time_label",
        string=_("Time"),
        store=False,
        help=_("Human-readable time range label (e.g. '09:00 – 10:30')."),
    )

    @api.depends("time_start", "time_end")
    def _compute_time_label(self):
        for rec in self:
            parts = []
            for val in (rec.time_start, rec.time_end):
                if val:
                    h = int(val)
                    m = int(round((val - h) * 60))
                    parts.append(f"{h:02d}:{m:02d}")
            rec.time_label = " – ".join(parts) if parts else ""

    @api.constrains("time_start", "time_end")
    def _check_time_order(self):
        for rec in self:
            if rec.time_start and rec.time_end and rec.time_end <= rec.time_start:
                raise ValidationError(
                    _(
                        "End time must be later than start time on activity '%(name)s'.",
                        name=rec.activity_name,
                    )
                )


# ---------------------------------------------------------------------------
# Dziennik Zajęć — Załącznik 5 Rozp. MEN 2016 (per group)
# ---------------------------------------------------------------------------


class FaynaCampDziennik(models.Model):
    _name = "fayna.camp.dziennik"
    _description = "Dziennik zajęć — Załącznik 5 Rozp. MEN 2016 (per group)"
    _inherit = ["mail.thread"]
    _order = "date_start desc, group_name"
    _rec_name = "display_name"

    _sql_constraints = [
        (
            "group_unique_per_event",
            "UNIQUE(event_id, group_name)",
            "Group name must be unique within the same event.",
        ),
    ]

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active (camp running)"),
            ("submitted", "Submitted to organizer"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
        string=_("Status"),
        help=_("Submitted dzienniki are frozen and cannot be modified (legal record)."),
    )

    event_id = fields.Many2one(
        "event.event",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
        string=_("Camp shift (event.event)"),
        help=_("The camp shift this dziennik belongs to."),
    )
    group_name = fields.Char(
        required=True,
        index=True,
        tracking=True,
        string=_("Oznaczenie grupy wypoczynku"),
        help=_("Group designation (e.g. 'A', 'Poszumymi-1', 'Old timers')."),
    )
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
        string=_("Display name"),
        help=_("Auto-generated: '{event} — grupa {group}'."),
    )
    location = fields.Char(
        compute="_compute_header_from_event",
        store=True,
        string=_("Miejsce wypoczynku"),
        help=_("Camp location address — auto-derived from event.event.address."),
    )
    organizer = fields.Char(
        compute="_compute_header_from_event",
        store=True,
        string=_("Organizator"),
        help=_("Organizer name — auto-derived from event company."),
    )
    kierownik_id = fields.Many2one(
        "camp.staff",
        string=_("Imię i nazwisko kierownika wypoczynku"),
        domain="[('event_id', '=', event_id), ('role', '=', 'leader')]",
        tracking=True,
        help=_("Camp leader assigned to this group."),
    )
    wychowawca_ids = fields.Many2many(
        "camp.staff",
        relation="fayna_camp_dziennik_wychowawca_rel",
        column1="dziennik_id",
        column2="staff_id",
        string=_("Imiona i nazwiska wychowawców"),
        domain="[('event_id', '=', event_id), ('role', '=', 'counselor')]",
        help=_("Counselors assigned to this group."),
    )
    date_start = fields.Date(
        required=True,
        string=_("Zajęcia rozpoczęto"),
        tracking=True,
        help=_("Date the group's activities began."),
    )
    date_end = fields.Date(
        string=_("Zajęcia zakończono"),
        tracking=True,
        help=_("Date the group's activities ended."),
    )

    # Section 1 — participants
    participant_ids = fields.Many2many(
        "camp.participant",
        relation="fayna_camp_dziennik_participant_rel",
        column1="dziennik_id",
        column2="participant_id",
        string=_("Uczestnicy grupy"),
        help=_("Participants assigned to this group."),
    )
    participant_count = fields.Integer(
        compute="_compute_participant_count",
        store=True,
        string=_("# uczestników"),
        help=_("Number of participants in this group."),
    )

    # Section 2 — weekly plan
    plan_line_ids = fields.One2many(
        "fayna.camp.dziennik.plan.line",
        "dziennik_id",
        string=_("Tygodniowy plan pracy"),
        help=_("Weekly work plan (Załącznik 5 Section 2)."),
    )

    # Section 3 — activity entries
    activity_ids = fields.One2many(
        "fayna.camp.dziennik.activity",
        "dziennik_id",
        string=_("Dziennik zajęć (записи занять)"),
        help=_("Daily activity entries (Załącznik 5 Section 3)."),
    )
    activity_count = fields.Integer(
        compute="_compute_activity_count",
        store=True,
        string=_("# entries"),
        help=_("Total number of activity entries in this dziennik."),
    )
    activity_signed_count = fields.Integer(
        compute="_compute_activity_count",
        store=True,
        string=_("# signed"),
        help=_("Number of activity entries that have been signed."),
    )

    # Section 4 — notes & recommendations
    note_ids = fields.One2many(
        "fayna.camp.dziennik.note",
        "dziennik_id",
        string=_("Uwagi i zalecenia"),
        help=_("Notes and recommendations (Załącznik 5 Section 4)."),
    )

    submitted_at = fields.Datetime(
        readonly=True,
        tracking=True,
        string=_("Submitted at"),
        help=_("Timestamp when this dziennik was submitted."),
    )
    submitted_by = fields.Many2one(
        "res.users",
        readonly=True,
        tracking=True,
        string=_("Submitted by"),
        help=_("User who submitted this dziennik."),
    )
    submitted_pdf = fields.Binary(
        string=_("Submitted PDF (frozen snapshot)"),
        attachment=True,
        readonly=True,
        help=_("Frozen PDF snapshot stored at submission time for 7-year legal archival."),
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends("event_id.name", "group_name")
    def _compute_display_name(self):
        for rec in self:
            if rec.event_id and rec.group_name:
                rec.display_name = f"{rec.event_id.name} — grupa {rec.group_name}"
            else:
                rec.display_name = rec.group_name or _("Draft dziennik")

    @api.depends("event_id", "event_id.address_inline", "event_id.company_id.name")
    def _compute_header_from_event(self):
        for rec in self:
            ev = rec.event_id
            rec.location = (ev.address_inline if ev and hasattr(ev, "address_inline") else "") or (
                ev and ev.address_id.display_name or ""
            )
            rec.organizer = ev.company_id.name if ev and ev.company_id else ""

    @api.depends("participant_ids")
    def _compute_participant_count(self):
        for rec in self:
            rec.participant_count = len(rec.participant_ids)

    @api.depends("activity_ids", "activity_ids.signature")
    def _compute_activity_count(self):
        for rec in self:
            rec.activity_count = len(rec.activity_ids)
            rec.activity_signed_count = len(rec.activity_ids.filtered(lambda a: a.signature))

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def action_activate(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Only draft dzienniki can be activated."))
            if not rec.kierownik_id or not rec.wychowawca_ids:
                raise UserError(_("Set kierownik and at least one wychowawca before activating."))
            rec.state = "active"

    def action_submit(self):
        """Freeze the journal and save a PDF snapshot (legal record — 7-year retention)."""
        for rec in self:
            if rec.state != "active":
                raise UserError(_("Only active dzienniki can be submitted."))
            if not rec.activity_ids:
                raise UserError(_("Cannot submit an empty journal — add at least one activity."))
            unsigned = rec.activity_ids.filtered(lambda a: not a.signature)
            if unsigned:
                raise UserError(
                    _(
                        "All activity entries must be signed before submission. "
                        "Missing signatures: %(count)s",
                        count=len(unsigned),
                    )
                )
            rec.write(
                {
                    "state": "submitted",
                    "submitted_at": fields.Datetime.now(),
                    "submitted_by": self.env.user.id,
                }
            )
            try:
                report = self.env.ref("fayna_camp_portal.action_report_dziennik")
                pdf_content, _fmt = report._render_qweb_pdf(
                    "fayna_camp_portal.action_report_dziennik",
                    res_ids=rec.ids,
                )
                rec.write({"submitted_pdf": base64.b64encode(pdf_content)})
            except Exception:  # noqa: BLE001 — fail-safe: don't block submit on PDF failure
                self.env.cr.rollback()
                rec.write(
                    {
                        "state": "submitted",
                        "submitted_at": fields.Datetime.now(),
                        "submitted_by": self.env.user.id,
                    }
                )
                rec.message_post(
                    body=_(
                        "PDF snapshot generation failed — submit succeeded; "
                        "use Print menu to re-render."
                    )
                )

    # ------------------------------------------------------------------
    # Immutability after submit
    # ------------------------------------------------------------------

    _MUTABLE_AFTER_SUBMIT = {"submitted_pdf"}

    def write(self, vals):
        for rec in self:
            if rec.state == "submitted":
                forbidden = set(vals) - self._MUTABLE_AFTER_SUBMIT
                if forbidden:
                    raise UserError(
                        _(
                            "Submitted dziennik is frozen — cannot modify %(fields)s",
                            fields=", ".join(sorted(forbidden)),
                        )
                    )
        return super().write(vals)

    def unlink(self):
        if any(rec.state == "submitted" for rec in self):
            raise UserError(
                _(
                    "Submitted dzienniki cannot be deleted (legal retention). "
                    "Archive workflow handles long-term storage."
                )
            )
        return super().unlink()


# ---------------------------------------------------------------------------
# Dziennik activity entry (Section 3 — Załącznik 5)
# ---------------------------------------------------------------------------


class FaynaCampDziennikActivity(models.Model):
    _name = "fayna.camp.dziennik.activity"
    _description = "Dziennik zajęć — single activity entry"
    _inherit = ["mail.thread"]
    _order = "datetime, id"

    dziennik_id = fields.Many2one(
        "fayna.camp.dziennik",
        required=True,
        ondelete="cascade",
        index=True,
        string=_("Dziennik"),
        help=_("The dziennik this activity entry belongs to."),
    )
    state = fields.Selection(
        related="dziennik_id.state",
        store=True,
        string=_("Status"),
        help=_("Mirrored from parent dziennik — controls immutability."),
    )

    datetime = fields.Datetime(
        string=_("Data, godzina"),
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        help=_("Date and time when this activity was conducted."),
    )
    content = fields.Text(
        string=_("Treść zajęcia"),
        required=True,
        tracking=True,
        help=_("What activity was conducted (subject, scope)."),
    )
    notes = fields.Text(
        string=_("Uwagi o przebiegu zajęć"),
        tracking=True,
        help=_("Achievements, difficulties, conclusions."),
    )
    risk_water = fields.Boolean(
        string=_("Water activity (§7)"),
        tracking=True,
        help=_(
            "Hard block: dziennik group must not contain participants with "
            "hydrophobia (wzór 2026 pkt 9, decision R1 — no override)."
        ),
    )
    risk_heights = fields.Boolean(
        string=_("Heights activity"),
        tracking=True,
        help=_(
            "Hard block: dziennik group must not contain participants with "
            "fear of heights (wzór 2026 pkt 9, decision R1 — no override)."
        ),
    )

    @api.constrains("risk_water", "risk_heights", "dziennik_id")
    def _check_risk_flags_vs_participants(self):
        """R1 hard block (no override): a water/heights activity cannot be
        scheduled for a group containing a child flagged hydrophobia /
        fear_of_heights on the qualification card (wzór 2026 pkt 9).
        Fields are RODO art. 9 group-gated → read via sudo() but never
        expose the medical flag itself, only the legal block reason."""
        for rec in self:
            if not (rec.risk_water or rec.risk_heights):
                continue
            participants = rec.dziennik_id.sudo().participant_ids
            if rec.risk_water:
                blocked = participants.filtered("hydrophobia")
                if blocked:
                    raise ValidationError(
                        _(
                            "Water activity blocked (karta kwalifikacyjna 2026, "
                            "pkt 9): the group contains participants who must "
                            "not take part in water activities: %s. Reassign "
                            "the children to another group/activity first."
                        )
                        % ", ".join(blocked.mapped("display_name"))
                    )
            if rec.risk_heights:
                blocked = participants.filtered("fear_of_heights")
                if blocked:
                    raise ValidationError(
                        _(
                            "Heights activity blocked (karta kwalifikacyjna "
                            "2026, pkt 9): the group contains participants who "
                            "must not take part in heights activities: %s. "
                            "Reassign the children first."
                        )
                        % ", ".join(blocked.mapped("display_name"))
                    )

    author_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True,
        string=_("Author (system user)"),
        help=_("System user who created this activity entry."),
    )
    author_role = fields.Selection(
        [
            ("kierownik", "Kierownik"),
            ("wychowawca", "Wychowawca"),
            ("other", "Other"),
        ],
        compute="_compute_author_role",
        store=True,
        string=_("Author role"),
        help=_("Role of the author within the group — computed from dziennik assignments."),
    )

    signature = fields.Binary(
        string=_("Podpis prowadzącego"),
        attachment=True,
        tracking=True,
        help=_("Canvas signature of the person who led this activity."),
    )
    signed_at = fields.Datetime(
        readonly=True,
        tracking=True,
        string=_("Signed at"),
        help=_("Timestamp when the signature was applied."),
    )
    signed_by_id = fields.Many2one(
        "camp.staff",
        string=_("Podpisał (kadra)"),
        readonly=True,
        help=_(
            "Camp staff member who signed this activity entry. "
            "Auto-filled on signature from dziennik's kierownik or wychowawca list."
        ),
        ondelete="set null",
        index=True,
    )

    @api.depends("author_id", "dziennik_id.kierownik_id", "dziennik_id.wychowawca_ids")
    def _compute_author_role(self):
        for rec in self:
            au = rec.author_id
            if not au or not rec.dziennik_id:
                rec.author_role = "other"
                continue
            d = rec.dziennik_id
            if d.kierownik_id and d.kierownik_id.user_id == au:
                rec.author_role = "kierownik"
            elif au in d.wychowawca_ids.mapped("user_id"):
                rec.author_role = "wychowawca"
            else:
                rec.author_role = "other"

    def _resolve_signed_by_staff(self):
        """Return the camp.staff record for the current user within the dziennik's event."""
        self.ensure_one()
        if not self.dziennik_id or not self.dziennik_id.event_id:
            return self.env["camp.staff"].browse()
        return self.env["camp.staff"].search(
            [
                ("event_id", "=", self.dziennik_id.event_id.id),
                ("name", "ilike", self.env.user.name),
            ],
            limit=1,
        )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("signature"):
                vals.setdefault("signed_at", fields.Datetime.now())
        records = super().create(vals_list)
        for rec in records:
            if rec.signature and not rec.signed_by_id:
                staff = rec._resolve_signed_by_staff()
                if staff:
                    super(FaynaCampDziennikActivity, rec).write({"signed_by_id": staff.id})
        return records

    def write(self, vals):
        for rec in self:
            if rec.state == "submitted":
                raise UserError(_("Cannot edit activities on a submitted dziennik."))
            if rec.signature and not (set(vals) <= {"signed_at", "signed_by_id"}):
                forbidden = set(vals) - {"signed_at", "signed_by_id"}
                if forbidden:
                    raise UserError(
                        _(
                            "Signed activity is immutable. Cannot modify: %(fields)s",
                            fields=", ".join(sorted(forbidden)),
                        )
                    )
        if vals.get("signature"):
            vals.setdefault("signed_at", fields.Datetime.now())
        result = super().write(vals)
        if vals.get("signature"):
            for rec in self:
                if not rec.signed_by_id:
                    staff = rec._resolve_signed_by_staff()
                    if staff:
                        super(FaynaCampDziennikActivity, rec).write({"signed_by_id": staff.id})
        return result

    def unlink(self):
        if any(r.state == "submitted" for r in self):
            raise UserError(_("Cannot delete activities on a submitted dziennik."))
        if any(r.signature for r in self):
            raise UserError(_("Cannot delete a signed activity (legal record)."))
        return super().unlink()


# ---------------------------------------------------------------------------
# Dziennik notes — Section 4 (Uwagi i zalecenia)
# ---------------------------------------------------------------------------


class FaynaCampDziennikNote(models.Model):
    _name = "fayna.camp.dziennik.note"
    _description = "Uwagi i zalecenia — entry"
    _inherit = ["mail.thread"]
    _order = "date desc, id desc"

    dziennik_id = fields.Many2one(
        "fayna.camp.dziennik",
        required=True,
        ondelete="cascade",
        index=True,
        string=_("Dziennik"),
        help=_("The dziennik this note belongs to."),
    )
    state = fields.Selection(
        related="dziennik_id.state",
        store=True,
        string=_("Status"),
        help=_("Mirrored from parent dziennik — controls immutability."),
    )

    date = fields.Date(
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        string=_("Date"),
        help=_("Date of this note or recommendation."),
    )
    content = fields.Text(
        string=_("Treść"),
        required=True,
        tracking=True,
        help=_("Content of the note or recommendation."),
    )
    note_type = fields.Selection(
        [
            ("info", "Info"),
            ("recommendation", "Zalecenie"),
            ("incident", "Incydent"),
            ("kurator", "Wizyta kuratora"),
        ],
        default="info",
        required=True,
        tracking=True,
        string=_("Type"),
        help=_("Type of note — kurator visits require formal logging."),
    )
    author_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True,
        string=_("Author"),
        help=_("User who wrote this note."),
    )

    def write(self, vals):
        for rec in self:
            if rec.state == "submitted":
                raise UserError(_("Cannot edit notes on a submitted dziennik."))
        return super().write(vals)

    def unlink(self):
        if any(r.state == "submitted" for r in self):
            raise UserError(_("Cannot delete notes on a submitted dziennik."))
        return super().unlink()


# ---------------------------------------------------------------------------
# Dziennik weekly plan — Section 2 (Tygodniowy plan pracy)
# ---------------------------------------------------------------------------


class FaynaCampDziennikPlanLine(models.Model):
    _name = "fayna.camp.dziennik.plan.line"
    _description = "Tygodniowy plan pracy — entry"
    _order = "week_number, sequence, id"

    dziennik_id = fields.Many2one(
        "fayna.camp.dziennik",
        required=True,
        ondelete="cascade",
        index=True,
        string=_("Dziennik"),
        help=_("The dziennik this plan line belongs to."),
    )
    state = fields.Selection(
        related="dziennik_id.state",
        store=True,
        string=_("Status"),
        help=_("Mirrored from parent dziennik — controls immutability."),
    )
    sequence = fields.Integer(
        default=10,
        string=_("Sequence"),
        help=_("Display order within the week."),
    )
    week_number = fields.Integer(
        string=_("Tydzień"),
        required=True,
        default=1,
        help=_("Week number within the camp shift (1, 2, 3, ...)."),
    )
    task = fields.Char(
        string=_("Zadania do wykonania"),
        required=True,
        help=_("Task or work to be completed this week."),
    )
    deadline = fields.Date(
        string=_("Termin"),
        help=_("Deadline for completing this task."),
    )
    responsible_id = fields.Many2one(
        "camp.staff",
        string=_("Odpowiedzialny za wykonanie"),
        help=_("Staff member responsible for this task."),
    )
    completion_note = fields.Text(
        string=_("Uwagi o wykonaniu"),
        help=_("Notes on how and when the task was completed."),
    )

    def write(self, vals):
        for rec in self:
            if rec.state == "submitted":
                raise UserError(_("Cannot edit plan lines on a submitted dziennik."))
        return super().write(vals)

    def unlink(self):
        if any(r.state == "submitted" for r in self):
            raise UserError(_("Cannot delete plan lines on a submitted dziennik."))
        return super().unlink()


# ---------------------------------------------------------------------------
# Kuratorium — Zgłoszenie Wypoczynku (Załącznik 1 MEN 2016)
# ---------------------------------------------------------------------------


class CampKuratoriumNotification(models.Model):
    _name = "camp.kuratorium.notification"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Zgłoszenie Wypoczynku do Kuratorium Oświaty"
    _order = "date_start desc"

    name = fields.Char(
        compute="_compute_name",
        store=True,
        string=_("Name"),
        help=_("Auto-generated: 'Zgłoszenie: {event}'."),
    )
    event_id = fields.Many2one(
        "event.event",
        required=True,
        ondelete="restrict",
        index=True,
        string=_("Event / Camp"),
        help=_("The camp shift this notification is filed for."),
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("ready", "Ready to Submit"),
            ("submitted", "Submitted"),
            ("registered", "Registered"),
            ("deficiency", "Deficiency"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        tracking=True,
        string=_("Status"),
        help=_("Workflow state of the notification in the Kuratorium process."),
    )
    notification_type = fields.Selection(
        [
            ("krajowy", "Krajowy (Załącznik 1)"),
            ("zagraniczny", "Zagraniczny (Załącznik 3)"),
        ],
        default="krajowy",
        required=True,
        string=_("Type"),
        help=_("Krajowy = domestic camp; Zagraniczny = abroad."),
    )

    # Section A — Organizer
    organizer_type = fields.Selection(
        [
            ("company", "Przedsiębiorca"),
            ("school", "Szkoła lub placówka"),
            ("person", "Osoba fizyczna"),
            ("legal", "Osoba prawna"),
            ("other", "Inna jednostka"),
        ],
        required=True,
        default="company",
        string=_("Organizer type"),
        help=_("Legal category of the organizing entity."),
    )
    organizer_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
        string=_("Organizer"),
        help=_("Organizing party (res.partner) named on the notification."),
    )
    regon = fields.Char(string=_("REGON"), help=_("REGON statistical number of the organizer."))
    krs = fields.Char(string=_("KRS"), help=_("KRS registration number (if applicable)."))
    is_profit = fields.Boolean(
        string=_("Działalność zarobkowa"),
        default=True,
        help=_("True if the organizer runs the camp for profit."),
    )
    tourism_registry_decl = fields.Boolean(
        string=_("Deklaracja — rejestr turystyki"),
        help=_("Declaration of entry in the tourism services register."),
    )
    organizer_purpose = fields.Text(
        string=_("Cel działania organizatora"),
        help=_("Stated purpose and mission of the organizer."),
    )

    # Section B — Camp details
    camp_type = fields.Selection(
        [
            ("kolonijny", "Kolonijny"),
            ("obozowy", "Obozowy"),
            ("inne", "Inne"),
        ],
        string=_("Typ obozu"),
        tracking=True,
        help=_("Camp type classification for Kuratorium filing."),
    )
    vacation_form = fields.Selection(
        [
            ("kolonia", "Kolonia"),
            ("oboz", "Obóz"),
            ("biwak", "Biwak"),
            ("zimowisko", "Zimowisko"),
            ("inne", "Inne"),
        ],
        required=True,
        default="oboz",
        string=_("Forma wypoczynku"),
        help=_("Formal form of leisure as classified by MEN regulation."),
    )
    accommodation_type = fields.Selection(
        [
            ("hotel", "Hotel / pensjonat"),
            ("occasional", "Obiekt okazjonalny"),
            ("tent", "Pole namiotowe"),
            ("school", "Szkoła / placówka"),
            ("other", "Inne"),
        ],
        required=True,
        default="hotel",
        string=_("Rodzaj obiektu"),
        help=_("Type of accommodation used."),
    )
    date_start = fields.Datetime(
        related="event_id.date_begin",
        store=True,
        string=_("Start Date"),
        help=_("Camp start date/time — mirrored from event."),
    )
    date_end = fields.Datetime(
        related="event_id.date_end",
        store=True,
        string=_("End Date"),
        help=_("Camp end date/time — mirrored from event."),
    )
    date_from = fields.Date(
        compute="_compute_date_aliases",
        store=True,
        string=_("Date From"),
        help=_("Camp start date (date only)."),
    )
    date_to = fields.Date(
        compute="_compute_date_aliases",
        store=True,
        string=_("Date To"),
        help=_("Camp end date (date only)."),
    )
    location = fields.Char(
        string=_("Lokalizacja (pełny adres)"),
        help=_("Full postal address of the camp."),
    )
    participant_count = fields.Integer(
        string=_("Liczba uczestników"),
        help=_("Total number of participants."),
    )
    participant_count_under10 = fields.Integer(
        string=_("w tym dzieci poniżej 10 lat"),
        help=_("Participants under 10 years of age."),
    )
    participant_count_special = fields.Integer(
        string=_("w tym z niepełnosprawnościami"),
        help=_("Participants with disabilities."),
    )
    kadra_count = fields.Integer(
        string=_("Liczba wychowawców"),
        tracking=True,
        help=_("Number of counselors (kadra) declared in the notification."),
    )
    location_city = fields.Char(string=_("Miejscowość"), help=_("City/village of the camp."))
    location_street = fields.Char(
        string=_("Ulica i numer"),
        help=_("Street and building number."),
    )
    location_zip = fields.Char(string=_("Kod pocztowy"), help=_("Postal code."))
    transport_method = fields.Selection(
        [
            ("bus", "Autobus"),
            ("train", "Pociąg"),
            ("plane", "Samolot"),
            ("own", "Własny dojazd"),
            ("other", "Inne"),
        ],
        string=_("Środek transportu"),
        help=_("Primary transport method to reach the camp."),
    )
    program_description = fields.Text(
        string=_("Program wypoczynku"),
        help=_("Brief description of the leisure program."),
    )
    medical_care_desc = fields.Text(
        string=_("Zapewnienie opieki medycznej"),
        help=_("Description of medical care arrangements."),
    )
    deadline_date = fields.Date(
        compute="_compute_deadline",
        store=True,
        string=_("Submission Deadline"),
        help=_("Required submission deadline: 21 days before camp (14 for abroad)."),
    )
    kierownik_id = fields.Many2one(
        "res.partner",
        index=True,
        string=_("Kierownik wypoczynku"),
        tracking=True,
        help=_("Camp leader named on this notification (Załącznik 1 required field)."),
    )
    notification_number = fields.Char(
        tracking=True,
        string=_("Numer zgłoszenia (MEN)"),
        help=_("Official registration number assigned by MEN / Kuratorium database."),
    )
    registration_number = fields.Char(
        tracking=True,
        string=_("Numer zgłoszenia"),
        help=_("Internal registration reference."),
    )
    submission_date = fields.Date(
        tracking=True,
        string=_("Submission Date"),
        help=_("Date the notification was formally submitted."),
    )

    # Section C — Staff declarations
    staff_decl = fields.Boolean(
        string=_("Oświadczenie o dokumentach kadry"),
        help=_("Organizer declares all staff documents are complete and valid."),
    )

    staff_ids = fields.One2many(
        "camp.kuratorium.staff",
        "notification_id",
        string=_("Kadra wypoczynku"),
        help=_("Staff listed in this notification (Załącznik 1 kadra section)."),
    )

    checklist_ids = fields.One2many(
        "camp.kuratorium.checklist",
        "notification_id",
        string=_("Lista kontrolna"),
        help=_("Compliance checklist pre-populated with standard Załącznik 1 items."),
    )
    checklist_done_count = fields.Integer(
        compute="_compute_checklist_progress",
        string=_("Gotowe pozycje"),
        help=_("Number of completed checklist items."),
    )
    checklist_total_count = fields.Integer(
        compute="_compute_checklist_progress",
        string=_("Wszystkie pozycje"),
        help=_("Total number of checklist items."),
    )

    attach_fire_opinion_ids = fields.Many2many(
        "ir.attachment",
        "kur_fire_rel",
        "notif_id",
        "attach_id",
        string=_("Opinia PSP"),
        help=_("Fire brigade opinion (required for permanent facilities)."),
    )
    attach_sketch_ids = fields.Many2many(
        "ir.attachment",
        "kur_sketch_rel",
        "notif_id",
        "attach_id",
        string=_("Szkic obiektu"),
        help=_("Sketch or description of the camp premises."),
    )

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends("event_id", "date_start", "notification_type")
    def _compute_name(self):
        for rec in self:
            event = rec.event_id.name or "—"
            rec.name = f"Zgłoszenie: {event}"

    @api.depends("date_start", "date_end")
    def _compute_date_aliases(self):
        for rec in self:
            rec.date_from = rec.date_start.date() if rec.date_start else False
            rec.date_to = rec.date_end.date() if rec.date_end else False

    @api.depends("date_start", "notification_type")
    def _compute_deadline(self):
        for rec in self:
            if rec.date_start:
                days = 14 if rec.notification_type == "zagraniczny" else 21
                rec.deadline_date = (rec.date_start - timedelta(days=days)).date()
            else:
                rec.deadline_date = False

    @api.depends("checklist_ids.is_done")
    def _compute_checklist_progress(self):
        for rec in self:
            rec.checklist_total_count = len(rec.checklist_ids)
            rec.checklist_done_count = len(rec.checklist_ids.filtered("is_done"))

    # ------------------------------------------------------------------
    # ORM hooks
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec._create_default_checklist()
        return records

    def _create_default_checklist(self):
        """Populate checklist with standard Załącznik 1 items on creation."""
        self.ensure_one()
        if self.checklist_ids:
            return
        self.env["camp.kuratorium.checklist"].create(
            [
                {
                    "notification_id": self.id,
                    "sequence": (seq + 1) * 10,
                    "name": item,
                }
                for seq, item in enumerate(_DEFAULT_CHECKLIST_ITEMS)
            ]
        )

    # ------------------------------------------------------------------
    # Workflow actions
    # ------------------------------------------------------------------

    def action_mark_ready(self):
        self.write({"state": "ready"})

    def action_mark_submitted(self):
        self.write({"state": "submitted", "submission_date": fields.Date.today()})

    def action_submit(self):
        """draft/ready → submitted; sets submission_date to today."""
        for rec in self:
            if rec.state == "cancelled":
                raise UserError(
                    _("Cannot submit a cancelled notification. Create a new one instead.")
                )
        self.write({"state": "submitted", "submission_date": fields.Date.today()})

    def action_approve(self):
        """submitted → registered (approved by Kuratorium)."""
        state_labels = dict(self._fields["state"].selection)
        for rec in self:
            if rec.state != "submitted":
                raise UserError(
                    _("Only a submitted notification can be approved. Current state: %s")
                    % state_labels.get(rec.state, rec.state)
                )
        self.write({"state": "registered"})

    def action_cancel(self):
        self.write({"state": "cancelled"})


# ---------------------------------------------------------------------------
# Kuratorium checklist item
# ---------------------------------------------------------------------------


class KuratoriumChecklist(models.Model):
    _name = "camp.kuratorium.checklist"
    _description = "Kuratorium compliance checklist item"
    _order = "sequence, id"

    notification_id = fields.Many2one(
        "camp.kuratorium.notification",
        required=True,
        ondelete="cascade",
        index=True,
        string=_("Notification"),
        help=_("The notification this checklist item belongs to."),
    )
    sequence = fields.Integer(
        default=10,
        string=_("Sequence"),
        help=_("Display order within the checklist."),
    )
    name = fields.Char(
        required=True,
        string=_("Pozycja kontrolna"),
        help=_("Description of the compliance item to verify."),
    )
    is_done = fields.Boolean(
        default=False,
        string=_("Zrealizowane"),
        help=_("Mark as done when this compliance item has been satisfied."),
    )
    notes = fields.Text(
        string=_("Uwagi"),
        help=_("Additional notes or evidence for this checklist item."),
    )


# ---------------------------------------------------------------------------
# Kuratorium staff record (kadra listed in the notification)
# ---------------------------------------------------------------------------


class CampKuratoriumStaff(models.Model):
    _name = "camp.kuratorium.staff"
    _description = "Kadra wypoczynku (kuratorium)"

    notification_id = fields.Many2one(
        "camp.kuratorium.notification",
        required=True,
        ondelete="cascade",
        index=True,
        string=_("Notification"),
        help=_("The notification this staff record belongs to."),
    )
    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        string=_("Person"),
        help=_("Staff member named in the notification."),
    )
    role = fields.Selection(
        [
            ("kierownik", "Kierownik wypoczynku"),
            ("wychowawca", "Wychowawca"),
            ("other", "Pozostały personel"),
        ],
        required=True,
        default="wychowawca",
        string=_("Rola"),
        help=_("Role of this person in the camp, as declared to Kuratorium."),
    )
    qualification_basis = fields.Selection(
        [
            ("teacher", "Nauczyciel"),
            ("course_k", "Kurs kierownika (10h)"),
            ("course_w", "Kurs wychowawcy (36h)"),
            ("zhr", "Instruktor ZHP/ZHR"),
            ("principal", "Dyrektor / wicedyrektor"),
            ("other", "Inne"),
        ],
        string=_("Podstawa kwalifikacji"),
        help=_("Legal basis for the person's qualification to act in this role."),
    )
    course_cert_number = fields.Char(
        string=_("Nr zaświadczenia"),
        help=_("Certificate number of the relevant course or qualification."),
    )
    krk_valid_until = fields.Date(
        string=_("KRK ważne do"),
        help=_("Expiry date of the KRK (criminal record clearance) certificate."),
    )
    rps_checked = fields.Boolean(
        string=_("RPS checked (Ustawa Kamilka)"),
        help=_(
            "Confirmation that this person was checked against the RPS "
            "(Rejestr Sprawców Przestępstw na Tle Seksualnym) — mandatory per Ustawa Kamilka."
        ),
    )
