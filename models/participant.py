# Fayna CampScout — Participant & Qualification Card models
import logging
import re
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Protected fields that cannot be modified after qualification_signed=True.
# Amendments require the amend() flow (new signed record + archive).
_PROTECTED_AFTER_SIGNOFF = frozenset(
    {
        "first_name",
        "last_name",
        "birth_date",
        "gender",
        "nationality_id",
        "pesel",
        "passport_number",
        "allergies",
        "medications",
        "chronic_conditions",
        "vaccination_status",
        "diet_restrictions",
        "doctor_notes",
        "emergency_contact_1_name",
        "emergency_contact_1_phone",
        "emergency_contact_1_relation",
        "emergency_contact_2_name",
        "emergency_contact_2_phone",
        "emergency_contact_2_relation",
        "parent_partner_id",
    }
)

# Section III fields — locked once `iii_completed_date` is set (kierownik signs).
_PROTECTED_AFTER_III_SIGN = frozenset(
    {
        "iii_adaptation_notes",
        "iii_health_events",
        "iii_medication_given",
        "iii_completed_by",
        "iii_completed_date",
    }
)

# Section IV+V fields — locked once `iv_kierownik_signature` exists.
# Section IV and V are signed together by the kierownik via the same wizard,
# so we use a single signature field as the gate for both.
_PROTECTED_AFTER_IV_V_SIGN = frozenset(
    {
        "iv_objectives_achieved",
        "iv_group_dynamics",
        "iv_signed_place",
        "v_health_notes",
        "v_recommendations",
        "v_signed_place",
        # iv_presence_interval_ids — guarded inside camp.presence.interval.write/unlink
    }
)

# Section VI fields — locked once `vi_wychowawca_signature` exists.
_PROTECTED_AFTER_VI_SIGN = frozenset(
    {
        "vi_observations",
        "vi_recommendations",
        "vi_signed_place",
    }
)


class CampParticipant(models.Model):
    _name = "camp.participant"
    _description = "Camp Participant (Child)"
    _inherits = {"res.partner": "partner_id"}
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "display_name"
    _order = "last_name, first_name, birth_date"

    # --- delegation + parent link -----------------------------------------

    partner_id = fields.Many2one(
        "res.partner",
        string=_("Related Partner"),
        required=True,
        ondelete="cascade",
        index=True,
        help=_("Linked res.partner record — provides address, email, phone via delegation."),
    )
    parent_partner_id = fields.Many2one(
        "res.partner",
        string=_("Parent / Legal Guardian"),
        index=True,
        tracking=True,
        help=_(
            "The parent or legal guardian who registered this child. "
            "Receives notification emails and signs the qualification card."
        ),
    )

    # --- identity ----------------------------------------------------------

    first_name = fields.Char(
        string=_("First name"),
        required=True,
        tracking=True,
        help=_("Child's legal first name as it appears on identity documents."),
    )
    last_name = fields.Char(
        string=_("Last name"),
        required=True,
        tracking=True,
        help=_("Child's legal last name as it appears on identity documents."),
    )
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
        index=True,
        help=_("Computed full name (first + last). Used as record title throughout the UI."),
    )
    birth_date = fields.Date(
        string=_("Date of birth"),
        required=True,
        tracking=True,
        help=_("Child's date of birth. Required for age calculation and PL legal compliance."),
    )
    age = fields.Integer(
        string=_("Age"),
        compute="_compute_age",
        store=True,
        help=_("Current age in full years, recalculated daily from birth_date."),
    )
    gender = fields.Selection(
        selection=[
            ("m", _("Male")),
            ("f", _("Female")),
            ("x", _("Other / Prefer not to say")),
        ],
        string=_("Gender"),
        tracking=True,
        help=_(
            "Gender as declared by the parent — used for accommodation group planning. "
            "Not shared externally; RODO art. 6(1)(b) contract performance."
        ),
    )
    nationality_id = fields.Many2one(
        "res.country",
        string=_("Nationality"),
        help=_("Child's nationality. Required when PESEL is not available (non-PL nationals)."),
    )
    # Avatar UI hint — purely visual fallback for hero emoji. NOT a structural
    # gender attribute (camp does not segregate). If `image_1920` is present —
    # photo takes priority; otherwise hero renders boy/girl/neutral emoji per this field.
    avatar_type = fields.Selection(
        selection=[
            ("boy", _("Boy avatar")),
            ("girl", _("Girl avatar")),
            ("photo", _("Own photo")),
        ],
        string=_("Avatar choice"),
        help=_(
            "Visual hint for cabinet hero — separate from any gender semantics. "
            "If the child has a profile photo uploaded, the photo takes priority."
        ),
    )
    pesel = fields.Char(
        string="PESEL",
        size=11,
        help=_(
            "Polish 11-digit national ID number. Leave empty for non-PL nationals. "
            "Checksum is validated on save (Luhn-style PL algorithm)."
        ),
    )
    passport_number = fields.Char(
        string=_("Passport / ID number"),
        help=_(
            "Travel document number — used when PESEL is absent. "
            "RODO art. 9 applies if the document reveals health/nationality data."
        ),
    )

    # --- medical (RODO art. 9 — group-restricted) --------------------------

    allergies = fields.Text(
        string=_("Allergies"),
        groups="fayna_camp_portal.group_medical_officer,fayna_camp_portal.group_camp_kierownik",
        tracking=True,
        help=_(
            "RODO art. 9 — list of known allergies (food, medication, environmental). "
            "Visible only to users with the Medical Officer role."
        ),
    )
    medications = fields.Text(
        string=_("Regular medications"),
        groups="fayna_camp_portal.group_medical_officer,fayna_camp_portal.group_camp_kierownik",
        tracking=True,
        help=_(
            "RODO art. 9 — list of medications the child takes regularly during the camp. "
            "Include dosage and schedule. Visible only to Medical Officers."
        ),
    )
    diet_restrictions = fields.Selection(
        selection=[
            ("vegetarian", _("Vegetarian")),
            ("vegan", _("Vegan")),
            ("halal", _("Halal")),
            ("kosher", _("Kosher")),
            ("lactose_free", _("Lactose-free")),
            ("gluten_free", _("Gluten-free")),
            ("other", _("Other (see notes)")),
        ],
        string=_("Diet restriction"),
        help=_(
            "Primary dietary requirement for the kitchen. "
            "Use 'Other (see notes)' and fill doctor_notes for complex combinations."
        ),
    )
    chronic_conditions = fields.Text(
        string=_("Chronic conditions"),
        groups="fayna_camp_portal.group_medical_officer,fayna_camp_portal.group_camp_kierownik",
        tracking=True,
        help=_(
            "RODO art. 9 — chronic health conditions the camp staff should know about "
            "(e.g. asthma, diabetes, epilepsy). Visible only to Medical Officers."
        ),
    )
    vaccination_status = fields.Selection(
        selection=[
            ("complete", _("Complete (per national schedule)")),
            ("partial", _("Partial")),
            ("exempt_medical", _("Exempt (medical reason)")),
            ("exempt_parental", _("Exempt (parental refusal)")),
        ],
        string=_("Vaccination status"),
        help=_(
            "Vaccination status as declared by the parent. "
            "Partial or exempt status may trigger additional health protocols at camp."
        ),
    )
    doctor_notes = fields.Html(
        string=_("Doctor / medical notes"),
        groups="fayna_camp_portal.group_medical_officer,fayna_camp_portal.group_camp_kierownik",
        help=_(
            "RODO art. 9 — free-form medical notes from the child's physician. "
            "Attach relevant certificates or diagnoses. Medical Officers only."
        ),
    )

    # --- Section III pkt 2 (special needs — PL law) ----------------------

    special_needs = fields.Text(
        string=_("Special needs"),
        translate=True,
        help=_(
            "Additional needs the camp staff should know about — behavioural, learning, "
            "or physical. Not RODO art. 9 category unless they indicate a health condition."
        ),
    )
    swimming_ability = fields.Selection(
        selection=[
            ("none", _("Does not swim")),
            ("surface", _("Swims on the surface")),
            ("deep", _("Swims confidently including deep water")),
        ],
        string=_("Swimming ability"),
        help=_(
            "Required by the camp to plan water activities safely. "
            "Declared by the parent at qualification card signing."
        ),
    )
    stay_alone_permission = fields.Boolean(
        string=_("May be alone outside the camp area"),
        help=_(
            "Parental permission for short solo outings (e.g. to a shop) while at camp. "
            "Per PL Ustawa o wypoczynku — must be explicitly granted."
        ),
    )

    # --- emergency contacts ------------------------------------------------

    emergency_contact_1_name = fields.Char(
        string=_("Emergency contact 1 — name"),
        tracking=True,
        help=_(
            "Full name of the primary emergency contact. "
            "Required at qualification card sign-off, not at child creation. "
            "Constraint _check_emergency_before_signoff enforces presence before signed=True."
        ),
    )
    emergency_contact_1_phone = fields.Char(
        string=_("Emergency contact 1 — phone"),
        tracking=True,
        help=_(
            "Phone number of the primary emergency contact — must be reachable 24/7 "
            "during the camp. Required at sign-off alongside the name."
        ),
    )
    emergency_contact_1_relation = fields.Char(
        string=_("Emergency contact 1 — relation"),
        help=_("Relationship to child (e.g. mother, father, grandparent)."),
    )
    emergency_contact_2_name = fields.Char(
        string=_("Emergency contact 2 — name"),
        help=_("Full name of the secondary emergency contact (optional but strongly recommended)."),
    )
    emergency_contact_2_phone = fields.Char(
        string=_("Emergency contact 2 — phone"),
        help=_("Phone number of the secondary emergency contact."),
    )
    emergency_contact_2_relation = fields.Char(
        string=_("Emergency contact 2 — relation"),
        help=_("Relationship to child for the secondary emergency contact."),
    )

    # --- signoff (immutable after signed) ---------------------------------

    qualification_signed = fields.Boolean(
        string=_("Qualification card signed"),
        tracking=True,
        help=_(
            "Set to True when the parent completes and signs the qualification card. "
            "Once True, most identity and medical fields become immutable "
            "(amendment flow required for any corrections)."
        ),
    )
    qualification_signed_date = fields.Datetime(
        string=_("Signed at"),
        readonly=True,
        tracking=True,
        help=_("Timestamp when the parent completed the signing workflow in the portal."),
    )
    qualification_signed_ip = fields.Char(
        string=_("Signed from IP"),
        readonly=True,
        help=_("IP address of the parent's browser at the moment of signing — legal evidence."),
    )
    qualification_signed_by = fields.Many2one(
        "res.users",
        string=_("Signed by (user)"),
        readonly=True,
        index=True,
        ondelete="set null",
        help=_("Odoo user account used to submit the signing — usually the parent's portal user."),
    )
    rodo_consent_id = fields.Many2one(
        "fayna.rodo.consent.log",
        string=_("RODO consent record"),
        ondelete="set null",
        help=_(
            "Link to the RODO consent log entry created at signing. "
            "Evidence that art. 9(2)(c) consent was obtained."
        ),
    )
    qualification_signature = fields.Binary(
        string=_("Parent signature (PNG)"),
        attachment=True,
        help=_(
            "Parent's signature drawn on the signing page — stored as PNG binary. "
            "Retained as legal evidence of consent per PL Ustawa o wypoczynku."
        ),
    )
    qualification_signed_by_name = fields.Char(
        string=_("Signer name (typed)"),
        readonly=True,
        help=_("Name typed by the parent next to their drawn signature at sign-off."),
    )

    # --- Sections III-VI — Karta Kwalifikacyjna (master TZ §2.10) ----------
    # III — kierownik fills adaptation/health/medication notes during camp.
    # IV  — kierownik confirms presence intervals + educational assessment + signs.
    # V   — kierownik writes health notes + recommendations + signs (RODO art. 9).
    # VI  — wychowawca writes observations + recommendations + signs.
    # III is locked once iii_completed_date is set.
    # IV+V are immutable once iv_kierownik_signature is captured.
    # VI is immutable once vi_wychowawca_signature is captured.
    # All enforced in write(). PDF template renders populated fields or
    # leaves areas blank for handwritten entry (PL law §6 Rozp. MEN 2016).

    # Section III — Adaptacja uczestnika (kierownik fills during camp) -----

    iii_adaptation_notes = fields.Text(
        string=_("Uwagi o adaptacji dziecka"),
        tracking=True,
        help=_(
            "Kierownik wypoczynku: obserwacje dotyczące adaptacji uczestnika "
            "do warunków wypoczynku, kontaktów z grupą, zachowania w pierwszych dniach."
        ),
    )
    iii_health_events = fields.Text(
        string=_("Zdarzenia zdrowotne"),
        groups="fayna_camp_portal.group_medical_officer,fayna_camp_portal.group_camp_kierownik",
        tracking=True,
        help=_(
            "RODO art. 9 — zdarzenia zdrowotne uczestnika podczas wypoczynku: "
            "wizyty u lekarza, urazy, gorączka, reakcje alergiczne itp. "
            "Widoczne tylko dla Medical Officer."
        ),
    )
    iii_medication_given = fields.Text(
        string=_("Podane leki w czasie wypoczynku"),
        groups="fayna_camp_portal.group_medical_officer,fayna_camp_portal.group_camp_kierownik",
        tracking=True,
        help=_(
            "RODO art. 9 — lista leków podanych uczestnikowi podczas wypoczynku "
            "wraz z dawką i datą podania. Uzupełniane przez pielęgniarkę/kierownika. "
            "Widoczne tylko dla Medical Officer."
        ),
    )
    iii_completed_by = fields.Many2one(
        "res.users",
        string=_("Uzupełnił kierownik"),
        readonly=True,
        index=True,
        ondelete="set null",
        help=_("Kierownik który zatwierdził Sekcję III (wypełnił i zapisał datę)."),
    )
    iii_completed_date = fields.Date(
        string=_("Data uzupełnienia Sekcji III"),
        readonly=True,
        tracking=True,
        help=_(
            "Data finalizacji Sekcji III przez kierownika. Ustawiana automatycznie "
            "po wywołaniu complete_section_iii(). Po ustawieniu — pola III są zamrożone."
        ),
    )

    # Section IV — Pobyt + podpis kierownika

    iv_signed_place = fields.Char(
        string=_("Miejscowość podpisu (Sekcja IV)"),
        tracking=True,
        help=_("Miejscowość wpisana przez kierownika przy podpisie Sekcji IV karty."),
    )
    iv_signed_date = fields.Datetime(
        string=_("Data podpisu (Sekcja IV)"),
        readonly=True,
        tracking=True,
        help=_("Automatycznie ustawiana data i godzina złożenia podpisu Sekcji IV."),
    )
    iv_kierownik_signature = fields.Binary(
        string=_("Podpis kierownika (Sekcja IV)"),
        attachment=True,
        help=_(
            "Podpis kierownika przechwycony przez wizard Sekcji IV-V. "
            "Po zapisaniu — pola Sekcji IV i V stają się niemodyfikowalne."
        ),
    )
    iv_signed_by = fields.Many2one(
        "res.users",
        string=_("Podpisał (Sekcja IV)"),
        readonly=True,
        index=True,
        ondelete="set null",
        help=_("Konto użytkownika kierownika który podpisał Sekcję IV."),
    )
    iv_presence_interval_ids = fields.One2many(
        "camp.presence.interval",
        "participant_id",
        string=_("Okresy pobytu (Sekcja IV)"),
        help=_(
            "Lista okresów pobytu uczestnika w obozie — główny pobyt + ewentualne "
            "tymczasowe odbiory przez rodziców. Wymagane przez Rozp. MEN §6."
        ),
    )

    # Section IV — Ocena wychowawcza (kierownik assessment)

    iv_objectives_achieved = fields.Text(
        string=_("Stopień realizacji celów wychowawczych"),
        tracking=True,
        help=_(
            "Kierownik ocenia stopień realizacji celów wychowawczych dla uczestnika "
            "w kontekście programu zmiany. Wypełniany po zakończeniu turnusu."
        ),
    )
    iv_group_dynamics = fields.Text(
        string=_("Uwagi o dynamice grupy"),
        tracking=True,
        help=_(
            "Obserwacje kierownika dotyczące zachowania uczestnika w grupie, "
            "roli jaką przyjął, relacji z rówieśnikami i kadrą."
        ),
    )

    # Section V — Notatki zdrowotne + podpis kierownika.
    # `v_health_notes` is RODO art. 9 (medical) — group-gated.

    v_health_notes = fields.Text(
        string=_("V. Notatki zdrowotne (kierownik)"),
        groups="fayna_camp_portal.group_medical_officer,fayna_camp_portal.group_camp_kierownik",
        tracking=True,
        help=_(
            "RODO art. 9 — notatki kierownika o stanie zdrowia uczestnika podczas "
            "turnusu: choroby przebyte, wizyty u lekarza, incydenty medyczne. "
            "Wypełniane przez wizard Sekcji IV-V. Widoczne tylko dla Medical Officer."
        ),
    )
    v_recommendations = fields.Text(
        string=_("V. Zalecenia dla rodziców i szkoły"),
        tracking=True,
        help=_(
            "Zalecenia kierownika skierowane do rodziców i szkoły po zakończeniu "
            "turnusu — wskazówki dot. dalszej pracy z dzieckiem, potrzeb "
            "edukacyjnych, kontynuacji terapii itp."
        ),
    )
    v_signed_place = fields.Char(
        string=_("Miejscowość podpisu (Sekcja V)"),
        tracking=True,
        help=_("Miejscowość wpisana przy podpisie Sekcji V."),
    )
    v_signed_date = fields.Datetime(
        string=_("Data podpisu (Sekcja V)"),
        readonly=True,
        tracking=True,
        help=_("Automatycznie ustawiana data i godzina złożenia podpisu Sekcji V."),
    )
    v_kierownik_signature = fields.Binary(
        string=_("Podpis kierownika (Sekcja V)"),
        attachment=True,
        help=_(
            "Podpis kierownika przechwycony przez wizard Sekcji IV-V. " "Zamraża pola Sekcji V."
        ),
    )
    v_signed_by = fields.Many2one(
        "res.users",
        string=_("Podpisał (Sekcja V)"),
        readonly=True,
        index=True,
        ondelete="set null",
        help=_("Konto użytkownika kierownika który podpisał Sekcję V."),
    )

    # Section VI — Obserwacje wychowawcy + podpis.

    vi_observations = fields.Text(
        string=_("VI. Obserwacje wychowawcy"),
        tracking=True,
        help=_(
            "Obserwacje wychowawcy dot. zachowania uczestnika, charakterystyki, "
            "incydentów. Wypełniane przez wizard Sekcji VI."
        ),
    )
    vi_recommendations = fields.Text(
        string=_("VI. Zalecenia wychowawcy"),
        tracking=True,
        help=_(
            "Zalecenia wychowawcy dla rodziców i przyszłych kadr obozu — "
            "wskazówki dot. pracy z dzieckiem w kolejnym sezonie, dynamiki grupy, "
            "umiejętności społecznych uczestnika."
        ),
    )
    vi_signed_place = fields.Char(
        string=_("Miejscowość podpisu (Sekcja VI)"),
        tracking=True,
        help=_("Miejscowość wpisana przy podpisie Sekcji VI."),
    )
    vi_signed_date = fields.Datetime(
        string=_("Data podpisu (Sekcja VI)"),
        readonly=True,
        tracking=True,
        help=_("Automatycznie ustawiana data i godzina złożenia podpisu Sekcji VI."),
    )
    vi_wychowawca_signature = fields.Binary(
        string=_("Podpis wychowawcy (Sekcja VI)"),
        attachment=True,
        help=_(
            "Podpis wychowawcy przechwycony przez wizard Sekcji VI. "
            "Po zapisaniu — pola Sekcji VI stają się niemodyfikowalne."
        ),
    )
    vi_signed_by = fields.Many2one(
        "res.users",
        string=_("Podpisał (Sekcja VI)"),
        readonly=True,
        index=True,
        ondelete="set null",
        help=_("Konto użytkownika wychowawcy który podpisał Sekcję VI."),
    )

    # --- relations --------------------------------------------------------

    registration_ids = fields.One2many(
        "event.registration",
        "participant_id",
        string=_("Camp registrations"),
        help=_("All event.registration records where this child is the participant."),
    )

    # --- Current booking projection (read-only computed, no duplication) -----
    # Single source of truth = sale.order/order_line (commerce domain).
    # We compute display-friendly snapshot for portal cabinet + backend support.
    # Per Best Practice 2026 (architecture §3): DRY, no field duplication.

    current_registration_id = fields.Many2one(
        "event.registration",
        compute="_compute_current_booking",
        store=False,
        string=_("Current booking"),
        help=_("Latest active registration (preferring future events). Computed, not stored."),
    )
    current_sale_order_id = fields.Many2one(
        "sale.order",
        compute="_compute_current_booking",
        store=False,
        string=_("Current order"),
        help=_("Sale order linked to the current booking. Computed, not stored."),
    )
    current_currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_current_booking_extras",
        store=False,
        help=_("Currency of the current sale order. Computed."),
    )
    current_amount_total = fields.Monetary(
        compute="_compute_current_booking_extras",
        store=False,
        currency_field="current_currency_id",
        string=_("Total paid"),
        help=_("Grand total of the current sale order. Computed."),
    )
    current_insurance_name = fields.Char(
        compute="_compute_current_booking_extras",
        store=False,
        string=_("Insurance"),
        help=_("Name of the insurance product in the current order (keyword-matched). Computed."),
    )
    current_merch_name = fields.Char(
        compute="_compute_current_booking_extras",
        store=False,
        string=_("Merch (T-shirt set)"),
        help=_("Name of the merch product in the current order (keyword-matched). Computed."),
    )
    current_camp_name = fields.Char(
        compute="_compute_current_booking_extras",
        store=False,
        string=_("Camp name"),
        help=_("Name of the event (camp) in the current booking. Computed."),
    )

    # --- Dodatek 4a — Zgoda na wizerunek -----------------------------------

    image_consent_state = fields.Selection(
        selection=[
            ("pending", _("Oczekuje na decyzję")),
            ("yes", _("Wyrażono zgodę")),
            ("no", _("Odmowa")),
        ],
        string=_("Image consent"),
        default="pending",
        tracking=True,
        copy=False,
        help=_(
            "Per Dodatek 4a — zgoda rodzica na utrwalanie i wykorzystanie "
            "wizerunku Uczestnika w celach promocyjnych. Składana w panelu "
            "klienta przed turnusem. RODO art. 6(1)(a) — dobrowolna."
        ),
    )
    image_consent_signed_date = fields.Datetime(
        string=_("Image consent signed at"),
        readonly=True,
        tracking=True,
        help=_("Timestamp when the parent submitted their image consent decision."),
    )
    image_consent_signed_ip = fields.Char(
        string=_("Image consent signed from IP"),
        readonly=True,
        help=_("IP address at time of image consent decision — legal evidence."),
    )
    image_consent_signature = fields.Binary(
        string=_("Image consent signature"),
        attachment=True,
        help=_("Optional signature for the image consent (Dodatek 4a)."),
    )
    image_consent_rodo_id = fields.Many2one(
        "fayna.rodo.consent.log",
        string=_("Image consent RODO log"),
        ondelete="set null",
        help=_("RODO consent log entry for image consent. Created by sign_image_consent()."),
    )

    # --- Dodatek 4b — Zgoda na komunikację marketingową --------------------

    marketing_consent = fields.Boolean(
        string=_("Marketing consent"),
        tracking=True,
        copy=False,
        help=_("Per Dodatek 4b — dobrowolna zgoda na komunikaty marketingowe. RODO art. 6(1)(a)."),
    )
    marketing_consent_signed_date = fields.Datetime(
        string=_("Marketing consent signed at"),
        readonly=True,
        tracking=True,
        help=_("Timestamp when the parent last changed marketing consent."),
    )
    marketing_consent_signed_ip = fields.Char(
        string=_("Marketing consent signed from IP"),
        readonly=True,
        help=_("IP address at time of marketing consent decision."),
    )
    marketing_consent_rodo_id = fields.Many2one(
        "fayna.rodo.consent.log",
        string=_("Marketing consent RODO log"),
        ondelete="set null",
        help=_(
            "RODO consent log entry for marketing consent. Created by update_marketing_consent()."
        ),
    )

    # --- absorb-compat fields (fn_*) used by qualification_card_template ---
    # Mirror the API surface of the BonSens card 1:1 so the PDF template renders
    # identically to the production variant. All are computed/related, no own storage.

    signed_on = fields.Datetime(
        related="qualification_signed_date",
        string=_("Signed on"),
        readonly=True,
        store=False,
        help=_("Alias for qualification_signed_date — used by PDF template."),
    )
    fn_client_consent = fields.Boolean(
        related="qualification_signed",
        string=_("Client consent (fn compat)"),
        readonly=True,
        store=False,
        help=_("Alias for qualification_signed — used by PDF template."),
    )
    fn_parents_signature = fields.Binary(
        related="qualification_signature",
        string=_("Parent signature (fn compat)"),
        readonly=True,
        store=False,
        help=_("Alias for qualification_signature — used by PDF template."),
    )
    fn_event_product_id = fields.Many2one(
        "event.event",
        compute="_compute_fn_card",
        store=False,
        string=_("Event (fn compat)"),
        help=_("First linked event — used by PDF template."),
    )
    fn_event_date_from = fields.Date(
        compute="_compute_fn_card",
        store=False,
        string=_("Event start (fn compat)"),
        help=_("Start date of the first linked event — used by PDF template."),
    )
    fn_event_date_to = fields.Date(
        compute="_compute_fn_card",
        store=False,
        string=_("Event end (fn compat)"),
        help=_("End date of the first linked event — used by PDF template."),
    )
    fn_event_address = fields.Char(
        compute="_compute_fn_card",
        store=False,
        string=_("Event address (fn compat)"),
        help=_("Camp location from the first linked camp program — used by PDF template."),
    )
    fn_hiking_route = fields.Char(
        compute="_compute_fn_card",
        store=False,
        string=_("Hiking route (fn compat)"),
        help=_("Hiking route from camp program — used by PDF template."),
    )
    fn_country_name = fields.Char(
        compute="_compute_fn_card",
        store=False,
        string=_("Country (fn compat)"),
        help=_("Camp country name — used by PDF template."),
    )
    fn_qc_place = fields.Char(
        compute="_compute_fn_card",
        store=False,
        string=_("QC place (fn compat)"),
        help=_("Place of qualification card signing — used by PDF template."),
    )
    fn_qc_date = fields.Date(
        compute="_compute_fn_card",
        store=False,
        string=_("QC date (fn compat)"),
        help=_("Date of qualification card signing — used by PDF template."),
    )
    fn_child_name = fields.Char(
        compute="_compute_fn_child",
        store=False,
        string=_("Child name (fn compat)"),
        help=_("Full child name — used by PDF template."),
    )
    fn_parents_names = fields.Char(
        compute="_compute_fn_child",
        store=False,
        string=_("Parent name (fn compat)"),
        help=_("Parent's full name — used by PDF template."),
    )
    fn_birth_date = fields.Char(
        compute="_compute_fn_child",
        store=False,
        string=_("Birth date string (fn compat)"),
        help=_("Birth date formatted as string — used by PDF template."),
    )
    fn_child_address = fields.Char(
        compute="_compute_fn_child",
        store=False,
        string=_("Child address (fn compat)"),
        help=_("Child's street, city, zip — used by PDF template."),
    )
    fn_parents_address = fields.Char(
        compute="_compute_fn_child",
        store=False,
        string=_("Parent address (fn compat)"),
        help=_("Parent's street, city, zip — used by PDF template."),
    )
    fn_parents_phone = fields.Char(
        compute="_compute_fn_child",
        store=False,
        string=_("Parent phone (fn compat)"),
        help=_("Parent's phone number — used by PDF template."),
    )
    fn_child_needs = fields.Text(
        compute="_compute_fn_child",
        store=False,
        string=_("Child special needs (fn compat)"),
        help=_("Special needs text — used by PDF template."),
    )
    fn_child_health_info = fields.Text(
        compute="_compute_fn_child",
        store=False,
        string=_("Child health info (fn compat)"),
        help=_("Concatenated health info (allergies, medications, diet) — used by PDF template."),
    )
    fn_child_vaccination_info = fields.Text(
        compute="_compute_fn_child",
        store=False,
        string=_("Child vaccination (fn compat)"),
        help=_("Vaccination status label — used by PDF template."),
    )
    fn_passport_number = fields.Char(
        compute="_compute_fn_child",
        store=False,
        string=_("PESEL / passport (fn compat)"),
        help=_("PESEL or passport number — used by PDF template."),
    )

    # --- migration flag (bs_campscout_addon one-off) ----------------------

    migration_needs_review = fields.Boolean(
        string=_("Needs review after migration"),
        default=False,
        help=_(
            "Record was imported automatically from bs_campscout_addon. "
            "The parent must review dates and medical info in the customer portal "
            "before the qualification card can be signed."
        ),
    )

    # --- retention --------------------------------------------------------

    retention_until = fields.Date(
        string=_("Retain until"),
        compute="_compute_retention_until",
        store=True,
        compute_sudo=True,
        help=_(
            "Earliest date this record may be anonymised or removed. "
            "Calculated as max(last event end, sign date) + 7 years per Polish law "
            "(Art. 118 k.c. 6-year limitation + 1-year buffer)."
        ),
    )

    # --- auto-refusal (life-critical / RODO invariant) --------------------

    auto_refusal_date = fields.Date(
        string=_("Auto-refusal deadline"),
        compute="_compute_auto_refusal_date",
        store=True,
        compute_sudo=True,
        help=_(
            "Deadline for signing the qualification card — earliest linked camp "
            "start minus one day. If still unsigned past this date the daily cron "
            "cancels the registration automatically (PL Ustawa o wypoczynku + RODO art. 9)."
        ),
    )
    auto_refusal_state = fields.Selection(
        selection=[
            ("pending", _("Pending — signature still expected")),
            ("refused", _("Refused — card not signed in time")),
            ("cleared", _("Cleared — signed off or coordinator override")),
        ],
        string=_("Auto-refusal status"),
        compute="_compute_auto_refusal_state",
        store=True,
        compute_sudo=True,
        tracking=True,
        help=_(
            "Tracks whether the participant is still expected to sign (pending), "
            "has been auto-cancelled by the system (refused), or is no longer "
            "at risk — either because the card is signed or a coordinator overrode."
        ),
    )
    auto_refusal_cleared_by = fields.Many2one(
        "res.users",
        string=_("Cleared by"),
        readonly=True,
        help=_("Coordinator who manually cleared the auto-refusal risk."),
    )
    auto_refusal_cleared_reason = fields.Char(
        string=_("Clear reason"),
        readonly=True,
        help=_("Short note from the coordinator explaining the manual override."),
    )
    auto_refusal_refused_at = fields.Datetime(
        string=_("Auto-refused at"),
        readonly=True,
        help=_("Timestamp when the daily cron flipped this participant to refused."),
    )
    # Comma-separated list of reminder tags that have been sent — e.g. "14d,7d".
    # Using a Char avoids a separate log-table just to de-duplicate emails.
    auto_refusal_reminders_sent = fields.Char(
        string=_("Reminders sent"),
        readonly=True,
        default="",
        help=_("Internal tracker — which reminder emails have been sent already (e.g. '14d,7d')."),
    )

    # --- SQL constraints --------------------------------------------------

    _sql_constraints = [
        (
            "partner_id_unique",
            "UNIQUE(partner_id)",
            "Each res.partner can be linked to at most one camp.participant record.",
        ),
    ]

    # --- create override (auto-fill res.partner.name from first/last) -----

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                # res.partner has a NOT-NULL check on name via check constraint.
                # Synthesize from first_name + last_name so _inherits delegation works.
                parts = [vals.get("first_name"), vals.get("last_name")]
                name = " ".join(filter(None, parts)).strip()
                vals["name"] = name or "—"
        return super().create(vals_list)

    # --- computes ---------------------------------------------------------

    @api.depends("first_name", "last_name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = " ".join(filter(None, [rec.first_name, rec.last_name])) or "—"

    @api.depends("birth_date")
    def _compute_age(self):
        today = date.today()
        for rec in self:
            if rec.birth_date:
                delta = relativedelta(today, rec.birth_date)
                rec.age = delta.years
            else:
                rec.age = 0

    @api.depends(
        "qualification_signed_date",
        "registration_ids.event_id.date_end",
    )
    def _compute_retention_until(self):
        # Art. 118 k.c. 6 lat przedawnienia + 1 rok buffer = 7 років.
        # Anchor = max(last event.date_end, qualification_signed_date).
        for rec in self:
            anchors = []
            if rec.qualification_signed_date:
                anchors.append(rec.qualification_signed_date.date())
            for reg in rec.registration_ids:
                if reg.event_id and reg.event_id.date_end:
                    anchors.append(reg.event_id.date_end.date())
            rec.retention_until = max(anchors) + relativedelta(years=7) if anchors else False

    @api.depends(
        "registration_ids.state",
        "registration_ids.event_id.date_begin",
    )
    def _compute_auto_refusal_date(self):
        """Deadline = earliest active-registration event start - 1 day.

        Active = registration.state in ('draft', 'open'). Cancelled + done
        registrations do not count (child no longer attending).
        """
        for rec in self:
            starts = [
                reg.event_id.date_begin.date()
                for reg in rec.registration_ids
                if reg.state in ("draft", "open") and reg.event_id and reg.event_id.date_begin
            ]
            rec.auto_refusal_date = min(starts) - timedelta(days=1) if starts else False

    @api.depends(
        "auto_refusal_date",
        "qualification_signed",
        "auto_refusal_refused_at",
        "auto_refusal_cleared_by",
        "registration_ids.state",
    )
    def _compute_auto_refusal_state(self):
        """State machine:

        - refused   — cron flipped `auto_refusal_refused_at` (latched, persists)
        - cleared   — coordinator override (`auto_refusal_cleared_by`) OR signed
        - pending   — has active unsigned registration + future deadline
        - False     — no active registrations or deadline already past without cron run
        """
        for rec in self:
            if rec.auto_refusal_refused_at:
                rec.auto_refusal_state = "refused"
                continue
            if rec.auto_refusal_cleared_by or rec.qualification_signed:
                rec.auto_refusal_state = "cleared" if rec.auto_refusal_date else False
                continue
            rec.auto_refusal_state = "pending" if rec.auto_refusal_date else False

    @api.depends(
        "registration_ids",
        "registration_ids.state",
        "registration_ids.event_id.date_begin",
        "registration_ids.sale_order_id",
    )
    def _compute_current_booking(self):
        """Latest active registration — prefer future event, else most recent.

        Used by portal cabinet to show 'current booking' widget for the child.
        """
        now = fields.Datetime.now()
        for rec in self:
            regs = rec.registration_ids.filtered(lambda r: r.state != "cancel")
            if not regs:
                rec.current_registration_id = False
                rec.current_sale_order_id = False
                continue
            future = regs.filtered(lambda r: r.event_id.date_begin and r.event_id.date_begin > now)
            if future:
                chosen = future.sorted(lambda r: r.event_id.date_begin)[0]
            else:
                chosen = regs.sorted(
                    lambda r: r.event_id.date_begin or fields.Datetime.now(), reverse=True
                )[0]
            rec.current_registration_id = chosen
            rec.current_sale_order_id = chosen.sale_order_id or False

    @api.depends(
        "current_sale_order_id",
        "current_sale_order_id.order_line",
        "current_sale_order_id.amount_total",
        "current_registration_id.event_id.name",
    )
    def _compute_current_booking_extras(self):
        """Extract camp / insurance / merch names + total from current order.

        Heuristic: identifies products by Ukrainian/Polish keywords in name.
        Migration-safe — does not require structured product categories.
        """
        ins_kw = ("страхування", "ubezpiecz", "медичний захист", "ochrona medyczna", "nnw", "oc ")
        merch_kw = ("набір", "zestaw", "merch")
        skip_kw = ("сервісний збір", "знижк", "наконкретні", "rabat", "opłata serwisowa")
        for rec in self:
            order = rec.current_sale_order_id
            if not order:
                rec.current_currency_id = False
                rec.current_amount_total = 0.0
                rec.current_camp_name = False
                rec.current_insurance_name = False
                rec.current_merch_name = False
                continue
            rec.current_currency_id = order.currency_id
            rec.current_amount_total = order.amount_total
            rec.current_camp_name = (
                rec.current_registration_id.event_id.name
                if rec.current_registration_id and rec.current_registration_id.event_id
                else False
            )
            ins = False
            merch = False
            for line in order.order_line:
                name_lower = (line.product_id.name or "").lower()
                if any(kw in name_lower for kw in skip_kw):
                    continue
                if not ins and any(kw in name_lower for kw in ins_kw):
                    ins = line.product_id.name
                elif not merch and any(kw in name_lower for kw in merch_kw):
                    merch = line.product_id.name
            rec.current_insurance_name = ins or False
            rec.current_merch_name = merch or False

    @api.depends(
        "registration_ids.event_id",
        "registration_ids.event_id.date_begin",
        "registration_ids.event_id.date_end",
        "registration_ids.event_id.camp_program_id",
        "qualification_signed_date",
    )
    def _compute_fn_card(self):
        for rec in self:
            first_reg = rec.registration_ids[:1]
            event = first_reg.event_id if first_reg else False
            camp = event.camp_program_id if event else False

            rec.fn_event_product_id = event.id if event else False
            rec.fn_event_date_from = (
                event.date_begin.date() if event and event.date_begin else False
            )
            rec.fn_event_date_to = event.date_end.date() if event and event.date_end else False
            rec.fn_event_address = camp.camp_location if camp else False
            rec.fn_hiking_route = camp.camp_hiking_route if camp else False
            rec.fn_country_name = (
                dict(camp._fields["camp_location_country"].selection).get(
                    camp.camp_location_country, ""
                )
                if camp and camp.camp_location_country
                else False
            )
            rec.fn_qc_place = camp.camp_location if camp else False
            rec.fn_qc_date = (
                rec.qualification_signed_date.date() if rec.qualification_signed_date else False
            )

    @api.depends(
        "display_name",
        "parent_partner_id.name",
        "parent_partner_id.street",
        "parent_partner_id.city",
        "parent_partner_id.zip",
        "parent_partner_id.phone",
        "birth_date",
        "street",
        "city",
        "zip",
        "emergency_contact_1_phone",
        "special_needs",
        "allergies",
        "medications",
        "chronic_conditions",
        "diet_restrictions",
        "doctor_notes",
        "vaccination_status",
        "pesel",
        "passport_number",
    )
    def _compute_fn_child(self):
        # Read in sudo so medical fields (allergies/medications/...) pass
        # field-level group ACL — PDF rendering must include them. Access to
        # actually print the report stays restricted at action level.
        for rec in self:
            su = rec.sudo()
            parent = su.parent_partner_id

            rec.fn_child_name = su.display_name
            rec.fn_parents_names = parent.name if parent else False
            rec.fn_birth_date = su.birth_date.strftime("%Y-%m-%d") if su.birth_date else False

            child_addr = ", ".join(p for p in [su.street or "", su.city or "", su.zip or ""] if p)
            rec.fn_child_address = child_addr or False

            if parent:
                parent_addr = ", ".join(
                    p for p in [parent.street or "", parent.city or "", parent.zip or ""] if p
                )
                rec.fn_parents_address = parent_addr or False
                rec.fn_parents_phone = parent.phone or su.emergency_contact_1_phone or False
            else:
                rec.fn_parents_address = False
                rec.fn_parents_phone = su.emergency_contact_1_phone or False

            rec.fn_child_needs = su.special_needs or False

            diet_label = (
                dict(su._fields["diet_restrictions"].selection).get(su.diet_restrictions, "")
                if su.diet_restrictions
                else ""
            )
            health_parts = [
                v
                for v in [
                    su.allergies,
                    su.medications,
                    su.chronic_conditions,
                    diet_label or None,
                ]
                if v
            ]
            rec.fn_child_health_info = "; ".join(health_parts) if health_parts else False

            rec.fn_child_vaccination_info = (
                dict(su._fields["vaccination_status"].selection).get(su.vaccination_status, "")
                if su.vaccination_status
                else False
            )

            rec.fn_passport_number = su.pesel or su.passport_number or False

    # --- constraints ------------------------------------------------------

    @api.constrains("parent_partner_id", "partner_id")
    def _check_parent_different_from_child(self):
        for rec in self:
            if rec.parent_partner_id and rec.parent_partner_id.id == rec.partner_id.id:
                raise ValidationError(_("A child cannot be their own parent/guardian."))

    @api.constrains("pesel")
    def _check_pesel_validity(self):
        for rec in self:
            if not rec.pesel:
                continue
            if not re.fullmatch(r"\d{11}", rec.pesel):
                raise ValidationError(_("PESEL must be exactly 11 digits."))
            weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
            digits = [int(c) for c in rec.pesel]
            calc_sum = sum(digits[i] * weights[i] for i in range(10))
            checksum = (10 - calc_sum % 10) % 10
            if checksum != digits[10]:
                raise ValidationError(_("PESEL checksum invalid — please double-check the number."))

    @api.constrains("qualification_signed", "emergency_contact_1_name", "emergency_contact_1_phone")
    def _check_emergency_before_signoff(self):
        for rec in self:
            if rec.qualification_signed and not (
                rec.emergency_contact_1_name and rec.emergency_contact_1_phone
            ):
                raise ValidationError(
                    _("Emergency contact 1 (name + phone) is required before signoff.")
                )

    # --- res.partner core-plumbing overrides -----------------------------

    def _commercial_sync_to_children(self):
        # res.partner.child_ids is overridden to point at camp.participant,
        # so Odoo core recurses commercial-fields sync onto us. We are not a
        # commercial entity — stop the cascade instead of crashing.
        return False

    # --- immutability enforcement ----------------------------------------

    def write(self, vals):
        # Allow admin override (group_system) — explicit emergency cases only.
        if self.env.su or self.env.user.has_group("base.group_system"):
            return super().write(vals)

        keys = set(vals.keys())

        # Detect any attempt to change protected fields on signed records.
        changing_protected = _PROTECTED_AFTER_SIGNOFF & keys
        if changing_protected:
            for rec in self:
                if rec.qualification_signed:
                    raise UserError(
                        _(
                            "Participant %(name)s is signed off — cannot modify %(fields)s. "
                            "Use the amendment flow (copy + new signature + archive the old).",
                            name=rec.display_name,
                            fields=", ".join(sorted(changing_protected)),
                        )
                    )

        # Section III immutability — once iii_completed_date is set, III body fields freeze.
        changing_iii = _PROTECTED_AFTER_III_SIGN & keys
        if changing_iii:
            for rec in self:
                if rec.iii_completed_date:
                    raise UserError(
                        _(
                            "Section III is finalized for %(name)s — cannot modify %(fields)s.",
                            name=rec.display_name,
                            fields=", ".join(sorted(changing_iii)),
                        )
                    )

        # Section IV+V immutability — once kierownik signs, IV+V body fields freeze.
        # The signature itself is excluded so the wizard's atomic write is allowed.
        changing_iv_v = _PROTECTED_AFTER_IV_V_SIGN & keys
        if changing_iv_v:
            for rec in self:
                if rec.iv_kierownik_signature:
                    raise UserError(
                        _(
                            "Sections IV-V are signed for %(name)s — cannot modify %(fields)s.",
                            name=rec.display_name,
                            fields=", ".join(sorted(changing_iv_v)),
                        )
                    )

        # Section VI immutability — once wychowawca signs, VI body fields freeze.
        changing_vi = _PROTECTED_AFTER_VI_SIGN & keys
        if changing_vi:
            for rec in self:
                if rec.vi_wychowawca_signature:
                    raise UserError(
                        _(
                            "Section VI is signed for %(name)s — cannot modify %(fields)s.",
                            name=rec.display_name,
                            fields=", ".join(sorted(changing_vi)),
                        )
                    )

        return super().write(vals)

    # --- public API --------------------------------------------------------

    def sign_qualification(
        self,
        ip_address=None,
        rodo_purpose="transactional",
        signature=None,
        signer_name=None,
    ):
        """Atomically marks participant as signed + links RODO consent.

        Raises UserError if already signed; ValidationError if prerequisites unmet.
        """
        self.ensure_one()
        if self.qualification_signed:
            raise UserError(_("Participant is already signed off."))
        if self.migration_needs_review:
            raise ValidationError(
                _(
                    "Цей запис мігровано з bs_campscout_addon і потребує review: "
                    "перевірте DOB + medical дані перед підписом."
                )
            )
        if not (self.emergency_contact_1_name and self.emergency_contact_1_phone):
            raise ValidationError(_("Emergency contact 1 (name + phone) is required."))

        consent_log = self.env["fayna.rodo.consent.log"]
        consent = consent_log.sudo().record_consent(
            purpose=rodo_purpose,
            channel="website",
            partner_id=self.parent_partner_id.id or self.partner_id.id,
            exact_response="qualification_signed",
            source="website_form",
            evidence_model="camp.participant",
            evidence_id=self.id,
        )
        vals = {
            "qualification_signed": True,
            "qualification_signed_date": fields.Datetime.now(),
            "qualification_signed_ip": ip_address or "",
            "qualification_signed_by": self.env.user.id,
            "rodo_consent_id": consent.id,
        }
        if signature:
            # signature is base64 PNG (without data:image/png;base64, prefix — Odoo Binary stores raw).
            vals["qualification_signature"] = signature
        if signer_name:
            vals["qualification_signed_by_name"] = signer_name
        self.write(vals)
        _logger.info(
            "fayna_camp_portal.signoff: participant=%s parent=%s ip=%s consent=%s",
            self.id,
            self.parent_partner_id.id,
            ip_address,
            consent.id,
        )
        return True

    def complete_section_iii(self):
        """Kierownik finalizes Section III — locks iii_* body fields.

        Sets iii_completed_date (today) and iii_completed_by (current user).
        Raises UserError if already completed or caller lacks kierownik group.
        Security: group_camp_kierownik required — checked programmatically so
        the action can be called from wizards that run as sudo().
        """
        self.ensure_one()
        if self.iii_completed_date:
            raise UserError(
                _(
                    "Section III is already finalized for %(name)s.",
                    name=self.display_name,
                )
            )
        if not (
            self.env.su
            or self.env.user.has_group("base.group_system")
            or self.env.user.has_group("fayna_camp_portal.group_camp_kierownik")
        ):
            raise UserError(_("Only the camp director (kierownik) can finalize Section III."))
        self.sudo().write(
            {
                "iii_completed_date": fields.Date.today(),
                "iii_completed_by": self.env.user.id,
            }
        )
        self.message_post(
            body=_(
                "Section III finalized by %(user)s on %(date)s.",
                user=self.env.user.display_name,
                date=self.iii_completed_date,
            )
        )
        _logger.info(
            "fayna_camp_portal.section_iii_complete: participant=%s user=%s",
            self.id,
            self.env.user.id,
        )
        return True

    # --- auto-refusal business logic -------------------------------------

    def _mark_reminder_sent(self, tag):
        """Append a reminder tag (e.g. '14d') to the sent-tracker atomically."""
        self.ensure_one()
        existing = set(filter(None, (self.auto_refusal_reminders_sent or "").split(",")))
        existing.add(tag)
        self.sudo().write({"auto_refusal_reminders_sent": ",".join(sorted(existing))})

    def _was_reminder_sent(self, tag):
        self.ensure_one()
        return tag in (self.auto_refusal_reminders_sent or "").split(",")

    def _log_rodo_auto_refusal(self):
        """Record a RODO audit entry for the auto-refusal event.

        Semantics: at the moment the cron fires, medical data cannot be
        lawfully processed (no signed consent per art. 9(2)(c)), so we log
        a consent_given=False record with source='system_cron' as evidence
        that the system stopped processing at the required threshold.
        """
        self.ensure_one()
        partner_id = self.parent_partner_id.id or self.partner_id.id
        try:
            return (
                self.env["fayna.rodo.consent.log"]
                .sudo()
                .record_consent(
                    purpose="transactional",
                    channel="website",
                    partner_id=partner_id,
                    evidence_model="camp.participant",
                    evidence_id=self.id,
                    consent_given=False,
                    exact_response="auto_refusal_unsigned_qualification",
                    legal_basis="consent",
                    source="api",
                    notes=_(
                        "Automatic refusal triggered by fayna_camp_portal cron — "
                        "qualification card unsigned by deadline "
                        "(auto_refusal_date=%(deadline)s). Medical data processing "
                        "(RODO art. 9(2)(c)) terminated — no consent on file.",
                        deadline=self.auto_refusal_date,
                    ),
                )
            )
        except Exception as exc:  # noqa: BLE001
            # RODO log is critical but must never block the refusal flow.
            _logger.exception("auto_refusal: RODO log failed participant=%s: %s", self.id, exc)
            return False

    def _schedule_refund(self):
        """Placeholder for Phase 3 (fayna_camp_sales).

        Records a mail.thread message + logger entry so the refund obligation
        is visible to finance until the real integration lands. When
        fayna_camp_sales is installed this method will be overridden to create
        an actual account.move credit per Umowa §6.x.
        """
        self.ensure_one()
        self.message_post(
            body=_(
                "Refund scheduled (placeholder — fayna_camp_sales not yet "
                "installed). Finance should process manually per Umowa §6.x "
                "until Phase 3 lands."
            )
        )
        _logger.info(
            "auto_refusal: refund placeholder logged participant=%s parent=%s",
            self.id,
            self.parent_partner_id.id,
        )
        return True

    def _apply_auto_refusal(self):
        """Execute the refusal for one participant — cancel active registrations,
        latch state, log RODO + refund, post audit message.

        Idempotent: participants already refused are skipped.
        Returns True on success, False if nothing was done.
        """
        self.ensure_one()
        if self.auto_refusal_refused_at:
            return False  # already refused
        active = self.registration_ids.filtered(lambda r: r.state in ("draft", "open"))
        if not active:
            return False  # nothing active to cancel
        active.sudo().action_cancel()
        self.sudo().write({"auto_refusal_refused_at": fields.Datetime.now()})
        self._log_rodo_auto_refusal()
        self._schedule_refund()
        # Best-effort notification — don't block the refusal if the email fails.
        try:
            self._send_auto_refusal_email("refusal")
            self._mark_reminder_sent("refusal")
        except Exception as exc:  # noqa: BLE001
            _logger.exception(
                "auto_refusal: notification email failed participant=%s: %s",
                self.id,
                exc,
            )
        self.message_post(
            body=_(
                "Auto-refusal triggered — qualification card unsigned by "
                "%(deadline)s. %(count)d registration(s) cancelled.",
                deadline=self.auto_refusal_date,
                count=len(active),
            )
        )
        _logger.info(
            "auto_refusal: participant=%s parent=%s cancelled=%d",
            self.id,
            self.parent_partner_id.id,
            len(active),
        )
        return True

    @api.model
    def _cron_auto_refusal_scan(self):
        """Daily job — cancel unsigned registrations whose deadline has passed.

        Scope: participants with auto_refusal_state='pending' and
        auto_refusal_date <= today. Already-refused or cleared records are
        excluded by the state filter (see _compute_auto_refusal_state).
        """
        today = fields.Date.today()
        candidates = self.sudo().search(
            [
                ("auto_refusal_state", "=", "pending"),
                ("auto_refusal_date", "<=", today),
                ("qualification_signed", "=", False),
                ("auto_refusal_refused_at", "=", False),
            ]
        )
        refused = 0
        for participant in candidates:
            if participant._apply_auto_refusal():
                refused += 1
        _logger.info(
            "auto_refusal cron: scanned=%d refused=%d",
            len(candidates),
            refused,
        )
        return {"scanned": len(candidates), "refused": refused}

    @api.model
    def _cron_auto_refusal_reminders(self):
        """Daily job — send 14d/7d/3d reminder emails before auto_refusal_date.

        Each participant receives each tag at most once (tracked via
        auto_refusal_reminders_sent). Emails go in the parent's language
        (partner.lang) — UK default, PL when lang starts with 'pl'.
        """
        today = fields.Date.today()
        thresholds = [("14d", 14), ("7d", 7), ("3d", 3)]

        candidates = self.sudo().search(
            [
                ("auto_refusal_state", "=", "pending"),
                ("auto_refusal_date", "!=", False),
                ("qualification_signed", "=", False),
            ]
        )
        sent = 0
        for participant in candidates:
            days_left = (participant.auto_refusal_date - today).days
            for tag, threshold in thresholds:
                if days_left != threshold or participant._was_reminder_sent(tag):
                    continue
                if participant._send_auto_refusal_email(tag):
                    participant._mark_reminder_sent(tag)
                    sent += 1
        _logger.info(
            "auto_refusal reminders cron: candidates=%d emails_sent=%d",
            len(candidates),
            sent,
        )
        return {"candidates": len(candidates), "sent": sent}

    def _send_auto_refusal_email(self, tag):
        """Render and send the email for a given reminder tag.

        Templates live in data/mail_templates.xml — one technical template per
        tag with translatable body (terms translated via standard .po flow).
        Note: XML IDs reference fayna_camp_portal module (consolidated).
        """
        self.ensure_one()
        xml_id_map = {
            "14d": "fayna_camp_portal.email_qualification_reminder_14d",
            "7d": "fayna_camp_portal.email_qualification_reminder_7d",
            "3d": "fayna_camp_portal.email_qualification_reminder_3d",
            "refusal": "fayna_camp_portal.email_auto_refusal",
        }
        xml_id = xml_id_map.get(tag)
        if not xml_id:
            _logger.warning("auto_refusal: unknown reminder tag=%s", tag)
            return False
        template = self.env.ref(xml_id, raise_if_not_found=False)
        if not template:
            _logger.warning(
                "auto_refusal: template %s not found — skip participant=%s",
                xml_id,
                self.id,
            )
            return False
        template.sudo().with_context(lang=self._auto_refusal_email_lang()).send_mail(
            self.id, force_send=False
        )
        return True

    def _auto_refusal_email_lang(self):
        """Pick template language — parent's partner lang, falling back to uk_UA."""
        self.ensure_one()
        lang = (self.parent_partner_id.lang or "").strip()
        if lang.startswith("pl"):
            return "pl_PL"
        return "uk_UA"

    def action_open_clear_auto_refusal_wizard(self):
        """Header-button entry point — opens the reason-capture wizard."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Clear auto-refusal hold"),
            "res_model": "camp.participant.auto_refusal_clear_wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_participant_id": self.id},
        }

    def action_clear_auto_refusal(self, reason=None):
        """Coordinator override — manually clear the refusal risk.

        Used for edge cases (parent called, promised to sign, etc.). Writes
        audit trail in mail.thread and populates cleared_by/cleared_reason
        so the reason is preserved even if the user is deleted later.

        Security: requires group_camp_leader (checked in view via groups=).
        """
        self.ensure_one()
        if not self.env.user.has_group("fayna_camp_portal.group_camp_leader"):
            raise UserError(_("Only camp leaders can clear auto-refusal holds."))
        if self.auto_refusal_state == "refused":
            raise UserError(
                _(
                    "Cannot clear an already-refused participant — the registration "
                    "was cancelled. Reinstate through the booking flow instead."
                )
            )
        self.write(
            {
                "auto_refusal_cleared_by": self.env.user.id,
                "auto_refusal_cleared_reason": (reason or "").strip() or False,
            }
        )
        self.message_post(
            body=_(
                "Auto-refusal risk manually cleared by %(user)s. Reason: %(reason)s",
                user=self.env.user.display_name,
                reason=reason or _("(no reason provided)"),
            )
        )
        return True

    # --- Dodatek 4a — Zgoda na wizerunek ------------------------------------

    def sign_image_consent(self, decision, ip_address=None, signature=None):
        """Record parent's decision on image/video consent (Dodatek 4a).

        `decision` must be 'yes' or 'no'. Creates a row in the shared RODO
        consent log (`purpose=child_photo`) and stores signature/date/ip on
        the participant. Consent is re-settable — parent can later withdraw
        or toggle via a second call (produces a new log row each time).
        """
        self.ensure_one()
        if decision not in ("yes", "no"):
            raise ValidationError(_("Image consent decision must be 'yes' or 'no'."))

        consent = (
            self.env["fayna.rodo.consent.log"]
            .sudo()
            .record_consent(
                purpose="child_photo",
                channel="website",
                partner_id=self.parent_partner_id.id or self.partner_id.id,
                consent_given=(decision == "yes"),
                exact_response=f"dodatek_4a:{decision}",
                legal_basis="consent",
                source="website_form",
                evidence_model="camp.participant",
                evidence_id=self.id,
                notes="Dodatek 4a — zgoda na wizerunek",
            )
        )
        vals = {
            "image_consent_state": decision,
            "image_consent_signed_date": fields.Datetime.now(),
            "image_consent_signed_ip": ip_address or "",
            "image_consent_rodo_id": consent.id,
        }
        if signature:
            vals["image_consent_signature"] = signature
        self.write(vals)
        _logger.info(
            "dodatek_4a: participant=%s decision=%s consent_log=%s ip=%s",
            self.id,
            decision,
            consent.id,
            ip_address,
        )
        return True

    # --- Dodatek 4b — Zgoda marketingowa ------------------------------------

    def update_marketing_consent(self, granted, ip_address=None):
        """Toggle marketing consent (Dodatek 4b). Writes log + stores state."""
        self.ensure_one()
        granted = bool(granted)

        consent = (
            self.env["fayna.rodo.consent.log"]
            .sudo()
            .record_consent(
                purpose="marketing_email",
                channel="email",
                partner_id=self.parent_partner_id.id or self.partner_id.id,
                email=self.parent_partner_id.email or False,
                consent_given=granted,
                exact_response=f"dodatek_4b:{'yes' if granted else 'no'}",
                legal_basis="consent",
                source="website_form",
                evidence_model="camp.participant",
                evidence_id=self.id,
                notes="Dodatek 4b — zgoda marketingowa (dobrowolna)",
            )
        )
        self.write(
            {
                "marketing_consent": granted,
                "marketing_consent_signed_date": fields.Datetime.now(),
                "marketing_consent_signed_ip": ip_address or "",
                "marketing_consent_rodo_id": consent.id,
            }
        )
        _logger.info(
            "dodatek_4b: participant=%s granted=%s consent_log=%s ip=%s",
            self.id,
            granted,
            consent.id,
            ip_address,
        )
        return True

    # --- one-off migration з bs_campscout_addon --------------------------

    _BS_PLACEHOLDER_DOB = "2010-01-01"  # explicit placeholder; parent corrects in portal

    @api.model
    def migrate_from_bs_campscout_addon(self, dry_run=True):
        """Мігрує дітей з paid `bs_campscout_addon` (bs_* fields на sale.order)
        у правильні camp.participant records.

        Source of truth: `sale.order.bs_child_name` (+ bs_birth_date,
        bs_parents_phone, bs_child_health_info). Groups orders by
        (partner_id, normalized child_name) — one unique participant
        per family × child, even if registered for multiple camp turns.

        Idempotent: if (partner, child_name) participant already exists —
        skips, only links event.registration if not yet linked.
        Safe-by-default: if bs_campscout_addon not installed → no-op.
        Re-signoff: each migrated record = migration_needs_review=True
        → cannot signoff until parent reviews DOB + medical data.

        Args:
            dry_run (bool): True — report only (default). False — executes.

        Returns:
            dict with keys status/dry_run/touched/skipped/regs_linked/failed.
        """
        sale_model = self.env["sale.order"]
        if "bs_child_name" not in sale_model._fields:
            _logger.info("bs_migration: bs_campscout_addon not installed — skip")
            return {"status": "skipped", "reason": "bs_campscout_addon not installed"}

        source_orders = sale_model.sudo().search(
            [("bs_child_name", "!=", False), ("partner_id", "!=", False)]
        )
        report = {
            "status": "done",
            "dry_run": dry_run,
            "touched": 0,
            "skipped": 0,
            "regs_linked": 0,
            "failed": [],
        }

        # Group (partner_id, normalized_name) → list of sale.orders
        groups = {}
        for order in source_orders:
            raw = (order.bs_child_name or "").strip()
            if not raw:
                continue
            key = (order.partner_id.id, raw.lower())
            groups.setdefault(key, []).append(order)

        event_registration = self.env["event.registration"]

        for (partner_id, _norm_name), orders in groups.items():
            first = orders[0]
            partner = first.partner_id

            name_parts = (first.bs_child_name or "").strip().split(None, 1)
            if not name_parts or not name_parts[0]:
                report["failed"].append({"partner_id": partner_id, "reason": "bs_child_name empty"})
                continue
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else "—"

            phone = first.bs_parents_phone or partner.phone or partner.mobile or ""
            if not phone:
                report["failed"].append({"partner_id": partner_id, "reason": "no phone anywhere"})
                continue

            existing = self.sudo().search(
                [
                    ("parent_partner_id", "=", partner_id),
                    ("first_name", "=ilike", first_name),
                ],
                limit=1,
            )
            if existing:
                report["skipped"] += 1
                if not dry_run:
                    order_ids = [o.id for o in orders]
                    orphan_regs = event_registration.sudo().search(
                        [("sale_order_id", "in", order_ids), ("participant_id", "=", False)]
                    )
                    if orphan_regs:
                        orphan_regs.write({"participant_id": existing.id})
                        report["regs_linked"] += len(orphan_regs)
                continue

            birth_date = self._BS_PLACEHOLDER_DOB
            raw_dob = first.bs_birth_date
            if raw_dob:
                try:
                    if hasattr(raw_dob, "year"):
                        birth_date = raw_dob
                    else:
                        birth_date = fields.Date.from_string(str(raw_dob))
                except (ValueError, TypeError):
                    birth_date = self._BS_PLACEHOLDER_DOB

            health_notes = [o.bs_child_health_info for o in orders if o.bs_child_health_info]
            allergies = "\n---\n".join(dict.fromkeys(health_notes))  # dedupe, preserve order

            vals = {
                "parent_partner_id": partner_id,
                "first_name": first_name,
                "last_name": last_name,
                "birth_date": birth_date,
                "emergency_contact_1_name": partner.name or first_name,
                "emergency_contact_1_phone": phone,
                "emergency_contact_1_relation": "Батько/мати (мігровано)",
                "allergies": allergies,
                "migration_needs_review": True,
            }

            if not dry_run:
                try:
                    child = self.sudo().create(vals)
                    order_ids = [o.id for o in orders]
                    orphan_regs = event_registration.sudo().search(
                        [("sale_order_id", "in", order_ids), ("participant_id", "=", False)]
                    )
                    if orphan_regs:
                        orphan_regs.write({"participant_id": child.id})
                        report["regs_linked"] += len(orphan_regs)
                    _logger.info(
                        "bs_migration: partner=%s child=%s → participant=%s (orders=%d regs=%d)",
                        partner_id,
                        first_name,
                        child.id,
                        len(orders),
                        len(orphan_regs),
                    )
                except Exception as e:  # noqa: BLE001
                    report["failed"].append(
                        {"partner_id": partner_id, "reason": f"create/link failed: {e}"}
                    )
                    continue

            report["touched"] += 1

        _logger.info(
            "bs_migration: dry_run=%s touched=%d skipped=%d regs_linked=%d failed=%d",
            dry_run,
            report["touched"],
            report["skipped"],
            report["regs_linked"],
            len(report["failed"]),
        )
        return report


# ---------------------------------------------------------------------------
# camp.presence.interval — Section IV presence tracking
# ---------------------------------------------------------------------------


class CampPresenceInterval(models.Model):
    """Presence interval for Section IV — when child was at camp.

    Sekcja IV Karty Kwalifikacyjnej wymaga zapisu okresów pobytu uczestnika:
    główny pobyt + ewentualne tymczasowe odbiory rodziców (np. wyjazd
    rodzinny w trakcie turnusu). Każdy interval ma `from_date` (obowiązkowo)
    + `to_date` (puste = uczestnik nadal w obozie). Kierownik wpisuje to
    przed podpisem Sekcji IV.
    """

    _name = "camp.presence.interval"
    _description = "Presence interval (Section IV — when child was at camp)"
    _order = "from_date, id"

    participant_id = fields.Many2one(
        "camp.participant",
        string=_("Participant"),
        required=True,
        ondelete="cascade",
        index=True,
        help=_("The child this presence interval belongs to."),
    )
    from_date = fields.Date(
        string=_("From date"),
        required=True,
        help=_("Date the participant was checked into camp for this interval."),
    )
    to_date = fields.Date(
        string=_("To date"),
        help=_("Date the participant left camp. Leave empty if they are still present."),
    )
    interval_type = fields.Selection(
        selection=[
            ("main", _("Pobyt główny")),
            ("temporary_pickup", _("Tymczasowy odbiór")),
        ],
        string=_("Interval type"),
        default="main",
        required=True,
        help=_(
            "Main stay = normal camp attendance. "
            "Temporary pickup = child left temporarily (e.g. family trip) and returned."
        ),
    )
    notes = fields.Text(
        string=_("Notes"),
        help=_("Optional notes about this presence interval (reason for temporary absence, etc.)."),
    )

    @api.constrains("from_date", "to_date")
    def _check_interval_dates(self):
        for rec in self:
            if rec.to_date and rec.from_date and rec.to_date < rec.from_date:
                raise ValidationError(
                    _("Presence interval: 'to_date' cannot be earlier than 'from_date'.")
                )

    @api.constrains("participant_id")
    def _check_participant_not_locked(self):
        """Once kierownik has signed Section IV, intervals are frozen."""
        for rec in self:
            if rec.participant_id and rec.participant_id.iv_kierownik_signature:
                raise ValidationError(
                    _(
                        "Section IV is already signed for participant %(name)s — "
                        "presence intervals are immutable. Use the amendment flow.",
                        name=rec.participant_id.display_name,
                    )
                )

    def write(self, vals):
        # Defense-in-depth: Section IV signature locks the participant's
        # intervals from any further write. Catches edits that don't touch
        # participant_id (which @api.constrains would miss).
        for rec in self:
            if rec.participant_id and rec.participant_id.iv_kierownik_signature:
                raise ValidationError(
                    _(
                        "Section IV is already signed for participant %(name)s — "
                        "presence intervals are immutable.",
                        name=rec.participant_id.display_name,
                    )
                )
        return super().write(vals)

    def unlink(self):
        for rec in self:
            if rec.participant_id and rec.participant_id.iv_kierownik_signature:
                raise ValidationError(
                    _(
                        "Section IV is already signed for participant %(name)s — "
                        "presence intervals cannot be deleted.",
                        name=rec.participant_id.display_name,
                    )
                )
        return super().unlink()


# ---------------------------------------------------------------------------
# event.registration — extend with participant link
# ---------------------------------------------------------------------------


class EventRegistration(models.Model):
    _inherit = "event.registration"

    # Note: required=False at field level so install on existing DB doesn't break
    # on legacy registrations without participant. Strict enforcement moves to
    # Phase 2b Step 5 migration (flip to required=True after backfill). For now,
    # new registrations still need participant_id — enforced via constrains.
    participant_id = fields.Many2one(
        "camp.participant",
        string=_("Participant (Child)"),
        ondelete="restrict",
        index=True,
        tracking=True,
        help=_(
            "The child (camp.participant) this registration belongs to. "
            "Required for camp events once fully migrated."
        ),
    )

    # Related fields — list view shows CHILD, not parent. Stored so filtering
    # and sorting operate on concrete DB columns.
    child_name = fields.Char(
        related="participant_id.display_name",
        string=_("Child name"),
        store=True,
        readonly=True,
        help=_("Child's full name — stored for efficient list-view search and sort."),
    )
    child_birth_date = fields.Date(
        related="participant_id.birth_date",
        string=_("Child birth date"),
        store=True,
        readonly=True,
        help=_("Child's date of birth — stored for efficient filtering."),
    )
    child_age = fields.Integer(
        related="participant_id.age",
        string=_("Child age"),
        store=True,
        readonly=True,
        help=_("Child's current age in years — stored for efficient filtering."),
    )

    @api.constrains("participant_id", "event_id", "state")
    def _check_participant_required_on_camp_events(self):
        """Orphan registrations (paid, not-yet-assigned child) are a legitimate
        transient state — parent buys the ticket first, fills the qualification
        card in the portal afterwards. The auto-refusal cron enforces the hard
        deadline (24h before event start).

        We only block saves that mark the registration as `done` (attendance
        processed) without a linked participant — that would be a data bug.
        Camp programs are identified via fayna_camp_template's is_camp_program.
        """
        for rec in self:
            camp_program = getattr(rec.event_id, "camp_program_id", False)
            is_camp_event = bool(camp_program and camp_program.is_camp_program)
            if is_camp_event and rec.state == "done" and not rec.participant_id:
                raise ValidationError(
                    _(
                        "Attended camp registration must have a linked participant. "
                        "Event: %(event)s",
                        event=rec.event_id.display_name,
                    )
                )


# ---------------------------------------------------------------------------
# res.partner — parent ↔ child link
# ---------------------------------------------------------------------------


class ResPartner(models.Model):
    _inherit = "res.partner"

    child_ids = fields.One2many(
        "camp.participant",
        "parent_partner_id",
        string=_("Children / Діти у кабінеті"),
        help=_("Children registered under this parent account for camp enrollment."),
    )
    child_count = fields.Integer(
        string=_("Child count"),
        compute="_compute_child_count",
        store=True,
        help=_("Number of camp participants registered under this parent."),
    )

    @api.depends("child_ids")
    def _compute_child_count(self):
        for rec in self:
            rec.child_count = len(rec.child_ids)

    def _children_sync(self, values):
        # child_ids is overridden above to point at camp.participant, which is
        # not a commercial res.partner — Odoo core's cascade (_commercial_sync_
        # to_children → _compute_commercial_partner on children) would crash
        # with AttributeError on our one2many target. Short-circuit the cascade;
        # camp.participant does not inherit commercial fields from the parent.
        return


# ---------------------------------------------------------------------------
# res.company — organizer signature + consent body fields
# ---------------------------------------------------------------------------


class ResCompany(models.Model):
    _inherit = "res.company"

    camp_organizer_signature = fields.Binary(
        string=_("Camp organizer signature"),
        attachment=True,
        help=_(
            "Signature of the organizer — appears pre-filled on every qualification "
            "card PDF. Uploaded once in Settings → Companies → your company."
        ),
    )
    # Absorb-compat alias used by qualification_card_template (1:1 з BonSens).
    fn_organizer_signature = fields.Binary(
        related="camp_organizer_signature",
        string=_("Organizer signature (fn compat)"),
        readonly=False,
        store=False,
        help=_("Alias for camp_organizer_signature — used by PDF template."),
    )

    # Legal-text bodies for parental consent dodatki (4a, 4b). Admin fills via
    # Settings → Companies → Camp organizer profile. Translatable + sanitized
    # so a copywriter can paste organizer-specific Polish legal text without
    # touching code, and Ukrainian translation lives in i18n .po.
    image_consent_body = fields.Html(
        string=_("Image consent body (Dodatek 4a)"),
        sanitize=True,
        translate=True,
        help=_(
            "Pełna treść Dodatku 4a (Zgoda na wizerunek). Wyświetlana w panelu "
            "klienta nad checkboxami TAK / NIE oraz w wygenerowanym PDF."
        ),
    )
    marketing_consent_body = fields.Html(
        string=_("Marketing consent body (Dodatek 4b)"),
        sanitize=True,
        translate=True,
        help=_(
            "Pełna treść Dodatku 4b (Zgoda marketingowa, dobrowolna). "
            "Wyświetlana w panelu klienta nad pojedynczym checkboxem."
        ),
    )
    child_registration_consent_body = fields.Html(
        string=_("Child registration consent body (pre-contract)"),
        sanitize=True,
        translate=True,
        help=_(
            "Treść klauzuli informacyjnej art. 13 RODO + treść zgody, którą "
            "rodzic potwierdza checkboxem na kroku «Dodaj dziecko» (przed "
            "umową). Wyświetlana w panelu klienta nad obowiązkowym checkboxem."
        ),
    )


# ---------------------------------------------------------------------------
# fayna.rodo.consent.log — extend evidence model selection
# ---------------------------------------------------------------------------


class FaynaRodoConsentLog(models.Model):
    _inherit = "fayna.rodo.consent.log"

    @api.model
    def _evidence_model_selection(self):
        # Extend dropdown so consent log entries that point to a child's
        # qualification record render a clickable "Доказ" reference instead
        # of plain Char/Integer pair.
        return super()._evidence_model_selection() + [
            ("camp.participant", "Camp Participant (kwalifikacja)"),
        ]
