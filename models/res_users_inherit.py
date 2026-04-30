"""Send Organizators to the admin dashboard on login.

When a user with group_camp_organizator logs in, _get_login_action() is the
entry point Odoo uses to choose what to render. We override to point them at
the URL action that opens /admin/dashboard (a server-rendered QWeb page).

Plain users / portal users keep Odoo's default behaviour.
"""

from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _get_login_action(self):
        """Return the act_url action for Organizators, otherwise default."""
        self.ensure_one()
        if self.has_group("fayna_camp_portal.group_camp_organizator"):
            action = self.env.ref(
                "fayna_camp_portal.action_admin_dashboard",
                raise_if_not_found=False,
            )
            if action:
                return action.sudo().read()[0]
        return super()._get_login_action()
