"""Wizard: wychowawca / kierownik broadcast SMS to all children in their group.

Flow:
  1. Open from camp.staff form button.
  2. Wizard recomputes recipients from dziennik group(s) the staff supervises.
  3. RODO filter: only participants with sms_consent=True AND a reachable
     mobile (own child_mobile or parent_partner_id.mobile).
  4. Cost guard: monthly limit per role (100 wychowawca / 300 kierownik)
     read from ir.config_parameter. Camp organizator group bypasses the cap.
  5. Dispatch via fayna.sms.dispatcher (multi-provider routing).
  6. Append-only audit row written to camp.staff.sms.log.

TZ §SMS broadcast (wychowawca → group).
"""

import logging
from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


# Maps camp.staff.role → key in ir.config_parameter for monthly limit.
ROLE_LIMIT_PARAMS = {
    "leader": "fayna_camp_portal.sms_kierownik_monthly_limit",
    "counselor": "fayna_camp_portal.sms_wychowawca_monthly_limit",
}
DEFAULT_LIMIT_BY_ROLE = {"leader": 300, "counselor": 100}


class CampStaffSmsComposer(models.TransientModel):
    _name = "camp.staff.sms.composer"
    _description = "Compose & broadcast SMS to children in a wychowawca's group"

    staff_id = fields.Many2one(
        "camp.staff",
        required=True,
        ondelete="cascade",
        string=_("Sender (staff)"),
        help=_("The wychowawca / kierownik on whose behalf the SMS is dispatched."),
    )
    event_id = fields.Many2one(
        "event.event",
        related="staff_id.event_id",
        store=True,
        readonly=True,
        string=_("Camp shift"),
        help=_("Auto-derived from the staff member's event."),
    )
    template_id = fields.Many2one(
        "sms.template",
        string=_("Template"),
        domain="[('model', '=', 'camp.participant')]",
        help=_("Pick a pre-defined message; you can still edit the body before sending."),
    )
    body = fields.Text(
        required=True,
        string=_("Message body"),
        help=_(
            "Final SMS text. Keep under 70 cyrillic characters to stay in 1 segment."
        ),
    )
    recipient_ids = fields.Many2many(
        "camp.participant",
        "camp_staff_sms_composer_recipient_rel",
        "composer_id",
        "participant_id",
        compute="_compute_recipients",
        store=False,
        string=_("Recipients (preview)"),
        help=_(
            "Children in groups this staff supervises with sms_consent=True "
            "and a reachable mobile (own or parent's)."
        ),
    )
    recipient_count = fields.Integer(
        compute="_compute_recipients",
        store=False,
        string=_("# recipients"),
    )
    cost_estimate_pln = fields.Float(
        compute="_compute_cost_estimate",
        store=False,
        digits=(10, 4),
        string=_("Estimated cost (PLN)"),
    )

    # ------------------------------------------------------------------
    # On-change helpers
    # ------------------------------------------------------------------

    @api.onchange("template_id")
    def _onchange_template_id(self):
        for wiz in self:
            if wiz.template_id and wiz.template_id.body:
                wiz.body = wiz.template_id.body

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------

    @api.depends("staff_id")
    def _compute_recipients(self):
        for wiz in self:
            if not wiz.staff_id:
                wiz.recipient_ids = False
                wiz.recipient_count = 0
                continue
            participants = wiz._resolve_recipients(wiz.staff_id)
            wiz.recipient_ids = participants
            wiz.recipient_count = len(participants)

    @api.depends("recipient_count")
    def _compute_cost_estimate(self):
        cost_per_segment = self._get_cost_per_segment()
        for wiz in self:
            wiz.cost_estimate_pln = (wiz.recipient_count or 0) * cost_per_segment

    # ------------------------------------------------------------------
    # Recipient resolution
    # ------------------------------------------------------------------

    def _resolve_recipients(self, staff):
        """Return camp.participant recordset eligible to receive the broadcast.

        Eligibility rules:
        - participant linked to a fayna.camp.dziennik whose kierownik_id = staff
          OR whose wychowawca_ids contain staff;
        - sms_consent = True;
        - has reachable mobile (child_mobile OR parent_partner_id.mobile).
        """
        Dziennik = self.env.get("fayna.camp.dziennik")
        if Dziennik is None:
            return self.env["camp.participant"].browse()

        dzienniki = Dziennik.search(
            [
                ("event_id", "=", staff.event_id.id),
                "|",
                ("kierownik_id", "=", staff.id),
                ("wychowawca_ids", "in", staff.id),
            ]
        )
        candidates = dzienniki.mapped("participant_ids")
        return candidates.filtered(self._is_recipient_eligible)

    @staticmethod
    def _is_recipient_eligible(participant):
        if not participant.sms_consent:
            return False
        own = (participant.child_mobile or "").strip()
        parent_mobile = ""
        if participant.parent_partner_id:
            parent_mobile = (participant.parent_partner_id.mobile or "").strip()
        return bool(own or parent_mobile)

    @staticmethod
    def _resolve_recipient_phone(participant):
        own = (participant.child_mobile or "").strip()
        if own:
            return own
        if participant.parent_partner_id:
            return (participant.parent_partner_id.mobile or "").strip()
        return ""

    # ------------------------------------------------------------------
    # Cost guard
    # ------------------------------------------------------------------

    def _get_cost_per_segment(self):
        param = self.env["ir.config_parameter"].sudo().get_param(
            "fayna_camp_portal.sms_cost_per_segment_pln", "0.05"
        )
        try:
            return float(param)
        except (TypeError, ValueError):
            return 0.05

    def _get_monthly_limit(self, staff):
        key = ROLE_LIMIT_PARAMS.get(staff.role)
        if not key:
            # Roles outside wychowawca/kierownik default to wychowawca limit.
            key = ROLE_LIMIT_PARAMS["counselor"]
        default = DEFAULT_LIMIT_BY_ROLE.get(staff.role, 100)
        param = self.env["ir.config_parameter"].sudo().get_param(key, str(default))
        try:
            return int(param)
        except (TypeError, ValueError):
            return default

    def _count_sent_this_month(self, staff):
        start_of_month = datetime.utcnow().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        Log = self.env["camp.staff.sms.log"].sudo()
        logs = Log.search(
            [("staff_id", "=", staff.id), ("sent_at", ">=", start_of_month)]
        )
        return sum(log.recipient_count for log in logs)

    def _check_monthly_limit(self, staff, planned_count):
        if self.env.user.has_group("fayna_camp_portal.group_camp_organizator"):
            return  # bypass for organizator
        limit = self._get_monthly_limit(staff)
        already = self._count_sent_this_month(staff)
        if (already + planned_count) > limit:
            raise UserError(
                _(
                    "Monthly SMS limit exceeded for this staff member.\n"
                    "Already sent this month: %(already)s\n"
                    "About to send: %(planned)s\n"
                    "Monthly cap (role=%(role)s): %(limit)s\n"
                    "Ask camp organizator if a higher cap is required."
                )
                % {
                    "already": already,
                    "planned": planned_count,
                    "role": staff.role or "?",
                    "limit": limit,
                }
            )

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    def action_send(self):
        self.ensure_one()
        if not self.staff_id:
            raise UserError(_("Staff member is required."))
        if not self.body or not self.body.strip():
            raise UserError(_("Message body cannot be empty."))

        # Recompute recipients defensively (don't rely on stored cache).
        recipients = self._resolve_recipients(self.staff_id)
        if not recipients:
            raise UserError(
                _(
                    "No eligible recipients. Recipients need sms_consent=True "
                    "and a reachable mobile (child or parent)."
                )
            )

        self._check_monthly_limit(self.staff_id, len(recipients))

        # Send via Odoo native sms.api → routes through configured sms.provider
        # (kw_sms_turbosms / TurboSMS on staging+prod). This avoids requiring
        # a separately configured fayna.sms.provider record.
        sms_api = self.env["sms.api"]
        sent_ok = 0
        sent_err = 0
        batch = []
        for participant in recipients:
            phone = self._resolve_recipient_phone(participant)
            if not phone:
                sent_err += 1
                continue
            batch.append(
                {
                    "res_id": participant.partner_id.id,
                    "number": phone,
                    "content": self.body,
                }
            )
        if batch:
            try:
                results = sms_api._send_sms_batch(batch)
                for res in results:
                    if res.get("state") == "success":
                        sent_ok += 1
                    else:
                        sent_err += 1
            except (UserError, ValidationError) as exc:
                _logger.exception(
                    "camp.staff.sms.composer: batch dispatch failed: %s", exc
                )
                sent_err += len(batch)

        cost_per_segment = self._get_cost_per_segment()
        log = self.env["camp.staff.sms.log"].sudo().create(
            {
                "staff_id": self.staff_id.id,
                "event_id": self.event_id.id,
                "template_id": self.template_id.id or False,
                "body": self.body,
                "recipient_ids": [(6, 0, recipients.ids)],
                "sent_at": fields.Datetime.now(),
                "cost_pln": len(recipients) * cost_per_segment,
                "delivery_sent": sent_ok,
                "delivery_error": sent_err,
            }
        )
        _logger.info(
            "camp.staff.sms.composer: log=%s staff=%s event=%s ok=%s err=%s",
            log.id,
            self.staff_id.id,
            self.event_id.id,
            sent_ok,
            sent_err,
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("SMS broadcast complete"),
                "message": _(
                    "Sent: %(ok)s — Errors: %(err)s — Cost: %(cost).2f PLN"
                )
                % {
                    "ok": sent_ok,
                    "err": sent_err,
                    "cost": len(recipients) * cost_per_segment,
                },
                "type": "success" if sent_err == 0 else "warning",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
