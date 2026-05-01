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
