# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
from . import (  # noqa: I001 — preserve historical order; new imports appended below
    camp,
    commercial,
    operations,
    emergency,
    nutrition,
    participant,
    sms,
    training,
)

# SMS notification layer — appended at the end per module conventions.
from . import res_partner_inherit, sms_notify  # noqa: E402,I001

# N-9 — public-form rate-limit + retry-with-backoff helpers (pure functions).
from . import rate_limit  # noqa: E402,I001

# SMS staff broadcast (wychowawca → group) — RODO + cost audit.
from . import (  # noqa: E402,I001
    participant_sms_extension,
    staff_sms_extension,
    staff_sms_log,
)

# Organizator (admin) impersonation log + login redirect.
from . import admin_access_log, res_users_inherit  # noqa: E402,I001

# Ustawa Kamilka 2024 — vital-interest SMS override + 5-min escalation
# + immutable Kuratorium audit log + event.event deputy backup contact.
from . import (  # noqa: E402,I001
    event_backup_contact,
    incident_kamilka,
    incident_notification_log,
)

# Auto-subscribe followers (mail.thread) + auto-create discuss.channel for
# camp shift staff teams.
from . import auto_subscribe_extensions, event_channel_create  # noqa: E402,I001

# Portal chatter — adds portal.mixin to participant / support / loyalty so
# /my/<…>/<id> pages can render `portal.message_thread`.
from . import portal_mixin_extensions  # noqa: E402,I001

# camp.story — migrated from fayna_camp_stories (TZ §9 step 4, 2026-04-30).
from . import stories  # noqa: E402,I001

# camp.transport — migrated from fayna_camp_transport (TZ §16 Phase 6, 2026-04-30).
from . import transport  # noqa: E402,I001

# Reports & analytics — migrated from fayna_camp_reports (TZ §16 Phase 7, 2026-04-30).
# camp.analytics.snapshot + camp.marketing.report wizard.
from . import reports  # noqa: E402,I001

# camp.group — grupa wychowawcza §2 art. 92c (sprint 2026-06-10).
from . import camp_group  # noqa: E402,I001

# §11 Karta Wypadku (16 pkt) + §12 Rejestr Wypadków — TZ_SPRINT_2026-06-10.
from . import incident_card  # noqa: E402,I001

# camp.budget — фінанси табору: BEP + 2 маржі (R8) — TZ_SPRINT §5.
from . import budget  # noqa: E402,I001

# Regulaminy + Teczka KO — sprint 2026-06-10 §4.
from . import regulamin, teczka_ko  # noqa: E402,I001

# Автоштат §2 + вакансії (R13) — sprint 2026-06-10 §6.
from . import staffing  # noqa: E402,I001

# camp.escort — Indywidualna asysta/konwój, міграція супроводу (TZ 2026-06-23 §5).
from . import camp_escort  # noqa: E402,I001

# Фаза B — рекрутація + онбординг виховника (ADR 09-ADR-FAZA-B-build.md).
# camp.staff.application: new→reviewing→accepted→rejected + _ensure_portal_user.
from . import recruitment  # noqa: E402,I001

# RODO art.9 — ORM-level masking of children medical data (read-override +
# ir.attachment scope). MUST import after participant. TZ §6j/6l/6n.
from . import art9_security  # noqa: E402,I001

# Append-only submission log (kadry-forms/campscout + kadry-forms/rodzice —
# статичні форми поза порталом) — доказ IP+час подання (INC-216).
from . import document_submission_log  # noqa: E402,I001

# Rejestr leków — прийом → графік → видача/пропуск + SMS CRITICAL (ТЗ тема 2,
# гейт Fable 2026-08-03). MUST import after participant + admin_access_log.
from . import medication  # noqa: E402,I001

# F-DOC-4 — retention-matrix auto-execution (daily cron flags + logs; real
# erasure is a separate wizard-confirmed step, first deletions 2033).
from . import retention  # noqa: E402,I001
