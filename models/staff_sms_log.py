# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Immutable audit log for wychowawca SMS broadcasts.

RODO + cost audit. Records every SMS broadcast a staff member sends to
their group. Records are append-only — write/unlink raise UserError so
the 7-year retention required by PL law is enforced at the model layer.

TZ §SMS broadcast (wychowawca → group).
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CampStaffSmsLog(models.Model):
    _name = "camp.staff.sms.log"
    _description = "Wychowawca SMS broadcast log (RODO + cost audit)"
    _order = "sent_at desc"

    staff_id = fields.Many2one(
        "camp.staff",
        required=True,
        index=True,
        ondelete="restrict",
        string=_("Sender (staff)"),
        help=_("Camp staff member (wychowawca / kierownik) who sent the broadcast."),
    )
    event_id = fields.Many2one(
        "event.event",
        required=True,
        index=True,
        ondelete="restrict",
        string=_("Camp shift"),
        help=_("Camp shift (event.event) the broadcast was scoped to."),
    )
    template_id = fields.Many2one(
        "sms.template",
        ondelete="set null",
        string=_("Template used"),
        help=_("Template used as a starting body, if any."),
    )
    body = fields.Text(
        required=True,
        string=_("Message body"),
        help=_("Final SMS text that was dispatched."),
    )
    recipient_ids = fields.Many2many(
        "camp.participant",
        "camp_staff_sms_log_recipient_rel",
        "log_id",
        "participant_id",
        string=_("Recipients"),
        help=_("Participants whose mobile (own or parent) received this SMS."),
    )
    recipient_count = fields.Integer(
        compute="_compute_recipient_count",
        store=True,
        string=_("# recipients"),
        help=_("Number of participants who received this SMS."),
    )
    sent_at = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
        index=True,
        string=_("Sent at"),
        help=_("Timestamp of dispatch (UTC)."),
    )
    cost_pln = fields.Float(
        string=_("Cost (PLN)"),
        digits=(10, 4),
        help=_("Estimated cost in PLN — recipient_count * sms_cost_per_segment."),
    )
    delivery_sent = fields.Integer(
        default=0,
        string=_("# successful"),
        help=_("Number of recipients the gateway accepted as queued/sent."),
    )
    delivery_error = fields.Integer(
        default=0,
        string=_("# errors"),
        help=_("Number of recipients the gateway rejected or that failed locally."),
    )

    @api.depends("recipient_ids")
    def _compute_recipient_count(self):
        for rec in self:
            rec.recipient_count = len(rec.recipient_ids)

    def write(self, vals):
        raise UserError(_("SMS log is immutable (audit retention 7y)."))

    def unlink(self):
        raise UserError(_("SMS log cannot be deleted (PL law)."))
