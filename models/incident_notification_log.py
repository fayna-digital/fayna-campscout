# Copyright 2026 Fayna Digital — Volodymyr Shevchenko
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Immutable notification trail for camp.incident.report.

Every dispatched notification (SMS / email / phone / inbox) is logged
here for the Kuratorium Oświaty audit (Ustawa Kamilka 2024). Records
are immutable after creation; only ``delivered_at`` / ``read_at``
delivery-status fields may be updated. Deletion is forbidden — PL law
mandates 7-year retention.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError

# Whitelist of fields writable post-creation (delivery status updates).
_DELIVERY_STATUS_FIELDS = frozenset({"delivered_at", "read_at"})


class CampIncidentNotificationLog(models.Model):
    """Immutable audit trail for incident notifications.

    Reportable to Kuratorium upon request — must survive 7 years
    (PL camp law retention).
    """

    _name = "camp.incident.notification.log"
    _description = (
        "Incident notification trail (immutable, Kuratorium audit)"
    )
    _order = "notified_at desc"

    incident_id = fields.Many2one(
        "camp.incident.report",
        string=_("Incident"),
        required=True,
        index=True,
        ondelete="cascade",
        help=_("Parent incident report this notification belongs to."),
    )
    recipient_partner_id = fields.Many2one(
        "res.partner",
        string=_("Recipient"),
        required=True,
        index=True,
        ondelete="restrict",
        help=_("Partner to whom the notification was dispatched."),
    )
    recipient_role = fields.Selection(
        [
            ("kierownik", _("Kierownik")),
            ("organizator", _("Organizator")),
            ("medical", _("Medical Officer")),
            ("parent", _("Parent")),
            ("backup", _("Backup Contact")),
            ("kuratorium", _("Kuratorium Oświaty")),
        ],
        string=_("Role"),
        required=True,
        help=_("Role under which this partner received the notification."),
    )
    channel = fields.Selection(
        [
            ("sms", _("SMS")),
            ("email", _("Email")),
            ("phone", _("Phone")),
            ("inbox", _("Odoo Inbox")),
        ],
        string=_("Channel"),
        required=True,
        help=_("Delivery channel used."),
    )
    notified_at = fields.Datetime(
        string=_("Notified at"),
        default=fields.Datetime.now,
        required=True,
        readonly=True,
        help=_("When the notification was dispatched (UTC)."),
    )
    delivered_at = fields.Datetime(
        string=_("Delivered at"),
        readonly=True,
        help=_("When the gateway confirmed delivery (DLR / read receipt)."),
    )
    read_at = fields.Datetime(
        string=_("Read at"),
        readonly=True,
        help=_(
            "When recipient acknowledged reading the notification "
            "(SMS gateway DLR with read flag, email open-tracking pixel, "
            "or explicit click on portal CTA)."
        ),
    )
    error = fields.Char(
        string=_("Error"),
        readonly=True,
        help=_("Gateway error message if delivery failed."),
    )

    # ------------------------------------------------------------------
    # Immutability guards.
    # ------------------------------------------------------------------

    def write(self, vals):
        """Reject writes to anything but ``delivered_at`` / ``read_at``."""
        forbidden = set(vals.keys()) - _DELIVERY_STATUS_FIELDS
        if forbidden:
            raise UserError(
                _(
                    "Notification log is immutable except for delivery "
                    "status (delivered_at, read_at). Forbidden fields: %s"
                )
                % ", ".join(sorted(forbidden))
            )
        return super().write(vals)

    def unlink(self):
        """Forbid deletion — 7-year retention mandated by PL law."""
        raise UserError(
            _(
                "Notification log cannot be deleted "
                "(7-year retention — PL camp law / RODO art. 30)."
            )
        )
