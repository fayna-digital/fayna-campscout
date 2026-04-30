"""SMS notification layer for CampScout — priority-aware mail.thread integration.

Three priority levels (declared on each model via class attribute ``_notify_priority``):

- ``CRITICAL``           — bell + email + push + SMS (incidents, unsigned card <3d)
- ``IMPORTANT``          — bell + email + push (journal comments, daily reports)
- ``INFO``               — bell + push (stories, marketing)
- ``CRITICAL_OVERRIDE``  — Ustawa Kamilka legal override (GDPR art. 6.1.d / vital interest):
                           SMS dispatched **regardless** of recipient ``sms_opt_in``.

Implementation notes
--------------------
We override ``mail.thread._notify_thread_by_sms`` (the canonical Odoo 17 hook) instead
of calling ``sms.api._send_sms_batch()`` directly — the latter bypasses
``mail.notification`` tracking, which we need for audit-trail (RODO art.30).

Per-partner opt-in is stored on ``res.partner.sms_opt_in`` (universal — works for
portal users) and is RODO art.7 compliant. The ``CRITICAL_OVERRIDE`` priority is the
only mechanism that ignores opt-in, and it is documented as legal-basis override
(vital interest of the child — Ustawa o ochronie maloletnich, "Ustawa Kamilka").

TZ §SMS-NOTIFY (FAYNA_CAMPSCOUT_TZ §11.x).
"""

import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Priority constants — used as values for ``cls._notify_priority`` on models.
# ---------------------------------------------------------------------------

PRIORITY_INFO = "INFO"
PRIORITY_IMPORTANT = "IMPORTANT"
PRIORITY_CRITICAL = "CRITICAL"
PRIORITY_CRITICAL_OVERRIDE = "CRITICAL_OVERRIDE"

#: Priorities that trigger SMS dispatch (in addition to bell/email/push).
SMS_DISPATCH_PRIORITIES = frozenset(
    {PRIORITY_CRITICAL, PRIORITY_CRITICAL_OVERRIDE}
)

#: Priorities that bypass per-partner ``sms_opt_in`` (legal-basis overrides).
SMS_BYPASS_OPT_IN_PRIORITIES = frozenset({PRIORITY_CRITICAL_OVERRIDE})


class MailThreadSmsNotify(models.AbstractModel):
    """Override ``mail.thread`` to add CampScout priority-aware SMS dispatch.

    The override is conservative: if the model on which the message is posted does
    **not** declare a ``_notify_priority`` class attribute, behaviour falls back to
    the stock Odoo implementation (no behaviour change for unrelated models).
    """

    _inherit = "mail.thread"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _campscout_notify_priority(self):
        """Return the model's declared priority or ``None`` if not set.

        Models opt in by declaring ``_notify_priority = "CRITICAL"`` (or one of the
        other constants above) at class level.
        """
        return getattr(type(self), "_notify_priority", None)

    def _campscout_filter_sms_recipients(self, partners, priority):
        """Filter recipients by ``sms_opt_in`` unless priority is an override.

        :param partners: ``res.partner`` recordset of candidate recipients.
        :param priority: One of the priority constants above.
        :returns: Filtered ``res.partner`` recordset.
        """
        if not partners:
            return partners
        if priority in SMS_BYPASS_OPT_IN_PRIORITIES:
            _logger.info(
                "fayna_camp_portal.sms_notify: priority=%s — bypassing sms_opt_in "
                "for %d partner(s) (legal override, GDPR art.6.1.d)",
                priority,
                len(partners),
            )
            return partners
        return partners.filtered(lambda p: p.sms_opt_in)

    # ------------------------------------------------------------------
    # Overrides — Odoo 17 hooks
    # ------------------------------------------------------------------

    def _notify_thread_by_sms(
        self,
        message,
        recipients_data,
        msg_vals=False,
        sms_numbers=None,
        resend_existing=False,
        sms_pid_to_number=None,
        check_existing=False,
        put_in_queue=False,
        **kwargs,
    ):
        """Filter SMS recipients by ``sms_opt_in`` before delegating to super.

        :param message: ``mail.message`` being broadcast.
        :param recipients_data: list[dict] — Odoo 17 recipient descriptors with
            ``id`` (partner id) and ``notif`` keys. We mutate this list in-place
            to drop opted-out partners (unless legal override).
        """
        priority = self._campscout_notify_priority()

        # No priority declared — stock behaviour (no filtering).
        if priority is None:
            return super()._notify_thread_by_sms(
                message,
                recipients_data,
                msg_vals=msg_vals,
                sms_numbers=sms_numbers,
                resend_existing=resend_existing,
                sms_pid_to_number=sms_pid_to_number,
                check_existing=check_existing,
                put_in_queue=put_in_queue,
                **kwargs,
            )

        # Priority below CRITICAL — drop ALL SMS recipients (bell+email+push only).
        if priority not in SMS_DISPATCH_PRIORITIES:
            _logger.debug(
                "fayna_camp_portal.sms_notify: priority=%s on model=%s — "
                "skipping SMS dispatch (bell/email/push only)",
                priority,
                self._name,
            )
            return True

        # CRITICAL or CRITICAL_OVERRIDE — apply opt-in filter.
        if priority not in SMS_BYPASS_OPT_IN_PRIORITIES and recipients_data:
            partner_ids = [r["id"] for r in recipients_data if r.get("id")]
            partners = self.env["res.partner"].browse(partner_ids)
            allowed = set(
                self._campscout_filter_sms_recipients(partners, priority).ids
            )
            dropped = len(recipients_data) - len(allowed)
            recipients_data = [r for r in recipients_data if r.get("id") in allowed]
            if dropped:
                _logger.info(
                    "fayna_camp_portal.sms_notify: priority=%s — dropped %d "
                    "opted-out recipient(s) on model=%s",
                    priority,
                    dropped,
                    self._name,
                )

        if not recipients_data:
            _logger.debug(
                "fayna_camp_portal.sms_notify: no recipients after opt-in filter "
                "(model=%s, priority=%s)",
                self._name,
                priority,
            )
            return True

        return super()._notify_thread_by_sms(
            message,
            recipients_data,
            msg_vals=msg_vals,
            sms_numbers=sms_numbers,
            resend_existing=resend_existing,
            sms_pid_to_number=sms_pid_to_number,
            check_existing=check_existing,
            put_in_queue=put_in_queue,
            **kwargs,
        )

    def _notify_thread(self, message, msg_vals=False, **kwargs):
        """Dispatch SMS via ``_message_sms_with_template`` for high-priority msgs.

        Stock Odoo only sends SMS when ``message.message_type == 'sms'`` or when
        SMS recipients are explicitly added. We add an extra dispatch path: if the
        model declares ``_notify_priority`` of CRITICAL (or higher) and the
        message is NOT already an SMS, we trigger the SMS template separately.

        ``mail.notification`` rows are created automatically by
        ``_message_sms_with_template`` (Odoo 17 built-in tracking).
        """
        result = super()._notify_thread(message, msg_vals=msg_vals, **kwargs)

        priority = self._campscout_notify_priority()
        if priority not in SMS_DISPATCH_PRIORITIES:
            return result

        # Skip if this message IS already an SMS — _notify_thread_by_sms handled it.
        message_type = (msg_vals or {}).get("message_type") or message.message_type
        if message_type == "sms":
            return result

        # Resolve recipients from msg_vals / message.partner_ids.
        partner_ids = (msg_vals or {}).get("partner_ids") or message.partner_ids.ids
        if not partner_ids:
            return result

        partners = self.env["res.partner"].browse(partner_ids)
        partners = self._campscout_filter_sms_recipients(partners, priority)
        if not partners:
            _logger.debug(
                "fayna_camp_portal.sms_notify: priority=%s but 0 partners after "
                "opt-in filter — no SMS dispatched",
                priority,
            )
            return result

        # Pick the appropriate default template (overridable per-call by callers
        # who invoke ``_message_sms_with_template`` themselves).
        template_xmlid = self._campscout_default_sms_template(priority)
        if not template_xmlid:
            return result

        try:
            self._message_sms_with_template(
                template_xmlid=template_xmlid,
                partner_ids=partners.ids,
            )
            _logger.info(
                "fayna_camp_portal.sms_notify: dispatched SMS template=%s to "
                "%d partner(s) (priority=%s, model=%s)",
                template_xmlid,
                len(partners),
                priority,
                self._name,
            )
        except ValueError as exc:
            # Template missing or malformed — log loudly so audit catches it.
            _logger.error(
                "fayna_camp_portal.sms_notify: SMS template %s missing or "
                "invalid — priority=%s, model=%s, err=%s",
                template_xmlid,
                priority,
                self._name,
                exc,
            )
        return result

    # ------------------------------------------------------------------
    # Template selection — overridable per-model.
    # ------------------------------------------------------------------

    def _campscout_default_sms_template(self, priority):
        """Return the default SMS template XML id for the given priority.

        Override in concrete models for incident-specific templates (e.g.
        ``sms_template_kamilka`` for Ustawa Kamilka events).

        :param priority: Priority constant.
        :returns: XML id string or ``None`` to skip dispatch.
        """
        if priority == PRIORITY_CRITICAL_OVERRIDE:
            return "fayna_camp_portal.sms_template_kamilka"
        if priority == PRIORITY_CRITICAL:
            return "fayna_camp_portal.sms_template_default_critical"
        return None

    def _campscout_log_sms_skip(self, reason):
        """Helper for callers that want to record why SMS was skipped.

        Posts an internal note (``message_type='comment'``, no recipients) — gives
        admins a paper trail per RODO art.30 without leaking PII.
        """
        self.ensure_one()
        self.message_post(
            body=_("SMS dispatch skipped: %s") % reason,
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
