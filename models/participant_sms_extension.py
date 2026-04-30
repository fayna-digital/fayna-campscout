"""Extension of camp.participant for staff-broadcast SMS feature.

Adds two RODO-aware fields:
- child_mobile: child's own mobile (older children) — optional. If empty,
  broadcast SMS routes to parent_partner_id.mobile.
- sms_consent: explicit consent flag (RODO art.7) collected during
  qualification card signing. Required for any SMS dispatch.

TZ §SMS broadcast (wychowawca → group).
"""

from odoo import _, fields, models


class CampParticipantSms(models.Model):
    _inherit = "camp.participant"

    child_mobile = fields.Char(
        string=_("Дитячий мобільний"),
        help=_(
            "Personal mobile of the child (older children). "
            "If empty, SMS routes to parent_partner_id.mobile."
        ),
    )
    sms_consent = fields.Boolean(
        string=_("SMS до дитини — згода батька"),
        default=False,
        tracking=True,
        help=_(
            "RODO art.7 explicit consent. Collected during qualification "
            "card signing. Required for staff broadcast SMS."
        ),
    )
