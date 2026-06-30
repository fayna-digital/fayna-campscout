# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""``res.partner`` extension — SMS opt-in flags (RODO art.7 compliant).

Two independent toggles:

- ``sms_opt_in``           — transactional/critical SMS (default ON; can be flipped
                              by the partner in the portal). Bypassed only for
                              ``CRITICAL_OVERRIDE`` priority (Ustawa Kamilka).
- ``sms_opt_in_marketing`` — promotional SMS (default OFF; explicit opt-in per
                              RODO art.7).

Both fields are stored on the universal ``res.partner`` so they cover both portal
users and back-office contacts. No ``groups=`` restriction is applied — portal
users must be able to manage their own consent (RODO art.7.3 — withdrawal must be
as easy as giving consent).
"""

from odoo import _, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    sms_opt_in = fields.Boolean(
        string=_("Receive SMS notifications"),
        default=True,
        help=_(
            "Receive SMS for critical events (incidents, unsigned cards, "
            "payment overdue). Can be overridden by legal basis (Ustawa "
            "Kamilka, vital interest of the child)."
        ),
    )
    sms_opt_in_marketing = fields.Boolean(
        string=_("Receive marketing SMS"),
        default=False,
        help=_(
            "Marketing/promotional SMS — explicit opt-in required per RODO art.7. Never overridden."
        ),
    )
