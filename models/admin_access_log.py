"""Organizator (admin) impersonation log — RODO art.30 register of processing.

Each entry records when a top-level Organizator (group_camp_organizator) views
the portal/back-office through the eyes of another role (kierownik, wychowawca,
instructor, parent). PL law (RODO art.30 §1.b "categories of processing" and
§2.b "describe purposes") requires we keep a register of who saw what and when.

Records are immutable. Retention: 7 years (PL accounting/oświata combined
retention floor; cron purge handled at platform level — not this module).

TZ §5.1 (six-role design 2026-04-30) + master TZ §Z BP-RODO-001.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError


class CampAdminAccessLog(models.Model):
    """Immutable trail of Organizator impersonation events ('view as <role>').

    Created from the admin controller before a view-as render. Even if the
    subsequent render fails, the access record exists. RODO art.30 register.
    """

    _name = "camp.admin.access.log"
    _description = "Organizator impersonation log (RODO art.30, 7y retention)"
    _order = "accessed_at desc"

    user_id = fields.Many2one(
        "res.users",
        required=True,
        index=True,
        readonly=True,
        ondelete="restrict",
        string=_("Organizator"),
        help=_("System user who triggered the view-as action."),
    )
    impersonated_role = fields.Selection(
        [
            ("kierownik", "Kierownik"),
            ("wychowawca", "Wychowawca"),
            ("instructor", "Instructor"),
            ("parent", "Parent"),
        ],
        required=True,
        readonly=True,
        index=True,
        string=_("Impersonated role"),
        help=_("Which role the Organizator viewed the system as."),
    )
    target_partner_id = fields.Many2one(
        "res.partner",
        readonly=True,
        ondelete="set null",
        index=True,
        string=_("Target parent (partner)"),
        help=_("Parent whose /my portal was rendered (only for as-parent)."),
    )
    target_event_id = fields.Many2one(
        "event.event",
        readonly=True,
        ondelete="set null",
        index=True,
        string=_("Target camp / event"),
        help=_("Camp shift the kierownik viewed (only for as-kierownik)."),
    )
    target_user_id = fields.Many2one(
        "res.users",
        readonly=True,
        ondelete="set null",
        index=True,
        string=_("Target user"),
        help=_("System user whose ACL was applied via with_user()."),
    )
    accessed_at = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        readonly=True,
        index=True,
        string=_("Accessed at"),
    )
    reason = fields.Char(
        readonly=True,
        string=_("Reason"),
        help=_("Optional free-text justification (e.g. 'support ticket #123')."),
    )
    ip_address = fields.Char(
        readonly=True,
        string=_("IP address"),
        help=_("Remote IP captured from request.httprequest.remote_addr."),
    )
    session_id = fields.Char(
        readonly=True,
        string=_("Session id"),
        help=_("Web session identifier (request.session.sid). RODO traceability."),
    )

    # ------------------------------------------------------------------
    # Immutability — RODO art.30 register cannot be edited or deleted.
    # ------------------------------------------------------------------

    def write(self, vals):
        raise UserError(_("Admin access logs are immutable (RODO art.30)."))

    def unlink(self):
        raise UserError(
            _("Admin access logs cannot be deleted (PL law: 7 years retention).")
        )
