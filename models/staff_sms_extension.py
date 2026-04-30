"""Extend camp.staff with the action that opens the SMS broadcast wizard.

Used by the form-view button '📨 Send SMS to my group'. The wizard pre-fills
the staff_id from `self`, then resolves the recipient set from the dziennik
groups this staff member supervises.

TZ §SMS broadcast (wychowawca → group).
"""

from odoo import _, models


class CampStaffSmsExtension(models.Model):
    _inherit = "camp.staff"

    def action_open_sms_composer(self):
        """Open the camp.staff.sms.composer wizard pre-filled with this staff member."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Send SMS to my group"),
            "res_model": "camp.staff.sms.composer",
            "view_mode": "form",
            "target": "new",
            "context": {"default_staff_id": self.id},
        }
