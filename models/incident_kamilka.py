# Copyright 2026 Fayna Digital — Volodymyr Shevchenko
"""Ustawa Kamilka 2024 overlay for camp.incident.report.

Adds a dedicated ``severity='kamilka'`` value with a CRITICAL_OVERRIDE
notification priority (bypasses ``sms_opt_in`` per GDPR art. 6.1.d
"vital interest" — child life/health threat). Cron escalates to a
backup contact (deputy kierownik or organizator) if the primary
kierownik has not read the SMS within 5 minutes.

Legal basis:
  * Ustawa o przeciwdziałaniu zagrożeniom przestępczością na tle
    seksualnym i ochronie małoletnich (Ustawa Kamilka, sierpień 2024)
  * Art. 162 KK — failure to render aid → criminal liability
  * RODO art. 6 ust. 1 lit. d — vital interest of natural person
"""

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# Priority constants — must mirror sms_notify.py.
PRIORITY_CRITICAL_OVERRIDE = "CRITICAL_OVERRIDE"
PRIORITY_CRITICAL = "CRITICAL"
PRIORITY_IMPORTANT = "IMPORTANT"

# SLA: kierownik has 5 minutes to read SMS before backup is alerted.
KAMILKA_KIEROWNIK_READ_SLA_MIN = 5


class CampIncidentReportKamilka(models.Model):
    """Ustawa Kamilka overlay on camp.incident.report.

    Extends ``severity`` Selection with a legal-critical value that
    forces SMS dispatch regardless of recipient opt-in (vital interest
    override) and triggers the 5-minute escalation cron.
    """

    _inherit = "camp.incident.report"

    severity = fields.Selection(
        selection_add=[("kamilka", "Ustawa Kamilka — vital interest")],
        ondelete={"kamilka": "cascade"},
    )
    backup_notified_at = fields.Datetime(
        string=_("Backup notified at"),
        readonly=True,
        tracking=True,
        help=_(
            "Timestamp when SMS was escalated to backup contact "
            "(deputy kierownik / organizator) because the primary "
            "kierownik did not acknowledge the alert within "
            "5 minutes."
        ),
    )
    kuratorium_notified_at = fields.Datetime(
        string=_("Kuratorium notified at"),
        readonly=True,
        tracking=True,
        help=_(
            "Timestamp when Kuratorium Oświaty was officially "
            "notified about this incident (Ustawa Kamilka audit)."
        ),
    )

    # ------------------------------------------------------------------
    # Notification priority — consumed by sms_notify.py override.
    # ------------------------------------------------------------------

    @property
    def _notify_priority(self):
        """Compute SMS priority based on severity.

        ``CRITICAL_OVERRIDE`` bypasses ``sms_opt_in`` (vital interest);
        ``CRITICAL`` respects opt-in; ``IMPORTANT`` is bell+email only.
        """
        self.ensure_one()
        if self.severity == "kamilka":
            return PRIORITY_CRITICAL_OVERRIDE
        if self.severity in ("severe", "fatal", "mass"):
            return PRIORITY_CRITICAL
        return PRIORITY_IMPORTANT

    # ------------------------------------------------------------------
    # Validation — kamilka requires fully-described incident.
    # ------------------------------------------------------------------

    @api.constrains("severity", "description", "incident_datetime")
    def _check_kamilka_required_fields(self):
        """Reject thin kamilka reports — Kuratorium audit demands detail."""
        for rec in self:
            if rec.severity != "kamilka":
                continue
            missing = []
            if not rec.description or len(rec.description) < 50:
                missing.append(_("description (min 50 chars)"))
            if not rec.incident_datetime:
                missing.append(_("incident_datetime"))
            if missing:
                raise ValidationError(
                    _("Ustawa Kamilka incident requires: %s") % ", ".join(missing)
                )

    # ------------------------------------------------------------------
    # Cron — 5-min escalation to backup contact.
    # ------------------------------------------------------------------

    @api.model
    def _cron_kamilka_escalate(self):
        """Escalate kamilka incidents whose kierownik did not read in 5 min.

        For each open kamilka incident older than 5 minutes where the
        kierownik has no ``read_at`` notification log entry, dispatch
        SMS to the deputy kierownik (preferred) or any organizator
        (fallback) and stamp ``backup_notified_at``.
        """
        cutoff = fields.Datetime.now() - timedelta(minutes=KAMILKA_KIEROWNIK_READ_SLA_MIN)
        incidents = self.search(
            [
                ("severity", "=", "kamilka"),
                ("state", "!=", "closed"),
                ("backup_notified_at", "=", False),
                ("create_date", "<", cutoff),
            ]
        )
        log_model = self.env["camp.incident.notification.log"]
        for inc in incidents:
            # Skip if kierownik already read any notification.
            kierownik_user = inc.event_id.user_id
            if kierownik_user and kierownik_user.partner_id:
                already_read = log_model.search(
                    [
                        ("incident_id", "=", inc.id),
                        (
                            "recipient_partner_id",
                            "=",
                            kierownik_user.partner_id.id,
                        ),
                        ("read_at", "!=", False),
                    ],
                    limit=1,
                )
                if already_read:
                    continue

            backup_partner = self._kamilka_pick_backup_partner(inc)
            if not backup_partner or not backup_partner.mobile:
                continue

            # Dispatch SMS via canonical Odoo 17 helper.
            inc._message_sms_with_template(
                template_xmlid="fayna_camp_portal.sms_template_kamilka",
                partner_ids=[backup_partner.id],
            )
            inc.backup_notified_at = fields.Datetime.now()
            log_model.create(
                {
                    "incident_id": inc.id,
                    "recipient_partner_id": backup_partner.id,
                    "recipient_role": "backup",
                    "channel": "sms",
                }
            )

    @api.model
    def _kamilka_pick_backup_partner(self, incident):
        """Resolve backup partner: deputy_kierownik > organizator group.

        :param incident: ``camp.incident.report`` recordset (single).
        :returns: ``res.partner`` recordset or ``False``.
        """
        deputy = incident.event_id.deputy_kierownik_id
        if deputy and deputy.partner_id:
            return deputy.partner_id

        group = self.env.ref(
            "fayna_camp_portal.group_camp_organizator",
            raise_if_not_found=False,
        )
        if group and group.users:
            return group.users[0].partner_id
        return False
