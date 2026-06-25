# Copyright 2026 Fayna Digital — Volodymyr Shevchenko
"""event.event extension — deputy kierownik backup contact.

Used by the Ustawa Kamilka escalation cron (5-min SLA) when the
primary kierownik (``event.event.user_id``) does not acknowledge a
critical SMS in time.
"""

from odoo import _, fields, models


class EventEventBackupContact(models.Model):
    """Add ``deputy_kierownik_id`` for legal-critical escalation."""

    _inherit = "event.event"

    deputy_kierownik_id = fields.Many2one(
        "res.users",
        string=_("Deputy Kierownik"),
        index=True,
        ondelete="set null",
        help=_(
            "Backup contact for Ustawa Kamilka escalation if the "
            "primary kierownik (user_id) cannot be reached within "
            "the 5-minute SLA. Falls back to first organizator-group "
            "user when no deputy is set."
        ),
    )
