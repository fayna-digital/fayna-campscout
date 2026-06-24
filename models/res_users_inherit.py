"""Home action routing per role on login (TZ §4).

Priority order:
  1. group_camp_organizator  → /admin/dashboard (QWeb, existing behaviour)
  2. group_camp_kierownik    → camp_kiosk_action (OWL fullscreen kiosk)
  3. group_camp_wychowawca   → camp_kiosk_action (OWL fullscreen kiosk)
  4. group_camp_instructor   → camp_kiosk_action (OWL fullscreen kiosk)
  5. (others)                → Odoo default

The kiosk roles also have a "Kiosk" menuitem (kiosk_views.xml) so they can
re-enter the kiosk from a regular browser tab.  The _get_login_action override
only fires on the first page load / login redirect.
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)

_KIOSK_GROUPS = [
    "fayna_camp_portal.group_camp_kierownik",
    "fayna_camp_portal.group_camp_wychowawca",
    "fayna_camp_portal.group_camp_instructor",
]


class ResUsers(models.Model):
    _inherit = "res.users"

    def _get_login_action(self):
        """Return home action based on the user's camp role.

        Organizator → admin dashboard URL action (existing).
        Kiosk roles  → camp_kiosk_action (ir.actions.client, fullscreen OWL).
        Others       → Odoo default.
        """
        self.ensure_one()

        # 1. Organizator → server-rendered /admin/dashboard
        if self.has_group("fayna_camp_portal.group_camp_organizator"):
            action = self.env.ref(
                "fayna_camp_portal.action_admin_dashboard",
                raise_if_not_found=False,
            )
            if action:
                return action.sudo().read()[0]

        # 2. Kiosk roles → OWL fullscreen kiosk
        for group in _KIOSK_GROUPS:
            if self.has_group(group):
                kiosk_action = self.env.ref(
                    "fayna_camp_portal.camp_kiosk_action",
                    raise_if_not_found=False,
                )
                if kiosk_action:
                    return kiosk_action.sudo().read()[0]
                # Graceful skip: if action record somehow missing, fall through
                _logger.warning(
                    "camp kiosk: camp_kiosk_action not found for user %s (%d), "
                    "falling back to default home",
                    self.login,
                    self.id,
                )
                break

        return super()._get_login_action()
