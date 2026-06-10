from . import (  # noqa: I001 — preserve historical order; new imports appended below
    camp,
    campscout_portal,
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
# camp.analytics.snapshot + camp.stats.snapshot + camp.marketing.report wizard.
from . import reports  # noqa: E402,I001

# Vozhatyi training — migrated from fayna_camp_vozhatyi_school (TZ §16 Phase 7).
# Standalone PL-MEN 36h/10h tracker (parallel to slide.channel-based training.py).
from . import training_vozhatyi  # noqa: E402,I001

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
