"""Auto-create staff ``discuss.channel`` for each ``event.event`` (camp shift).

When a camp shift is created (or its kierownik / staff line-up changes),
sync a private group chat in Discuss containing the kierownik plus every
staff member assigned to the shift. Used as the operational channel for
the team running that заїзд.

Odoo 17 specifics:
- ``mail.channel`` was renamed to ``discuss.channel`` in Odoo 17.
- ``channel_type='group'`` = private multi-user chat (right fit for an
  internal staff team). ``'channel'`` is a public/broadcast room,
  ``'chat'`` is a 1:1 DM, ``'livechat'`` is the public website widget.
- Membership is written via ``add_members(partner_ids=[...])`` rather
  than ``channel_partner_ids`` write commands; the v17 API channels
  membership through ``discuss.channel.member`` records.
- ``with_context(mail_create_nosubscribe=True)`` on the create call
  prevents Odoo from auto-subscribing the creator twice (once via the
  member relation, once via mail.thread).
"""

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


# ===========================================================================
# discuss.channel — link back to the camp shift
# ===========================================================================
class DiscussChannelCamp(models.Model):
    _inherit = "discuss.channel"

    camp_event_id = fields.Many2one(
        "event.event",
        string="Camp Shift",
        index=True,
        ondelete="set null",
        help=(
            "Auto-linked event.event when this channel is the staff group "
            "chat for a specific camp shift."
        ),
    )


# ===========================================================================
# event.event — auto-create channel on create / sync members on write
# ===========================================================================
class EventEventChannel(models.Model):
    _inherit = "event.event"

    def _camp_channel_partner_ids(self):
        """Collect partner ids of (kierownik + staff) for one shift.

        Returns deduplicated list. Skips staff members without a linked
        ``user_id`` (no login = nobody to notify).
        """
        self.ensure_one()
        partner_ids = []
        if self.user_id and self.user_id.partner_id:
            partner_ids.append(self.user_id.partner_id.id)
        for staff in self.staff_ids:
            if staff.user_id and staff.user_id.partner_id:
                partner_ids.append(staff.user_id.partner_id.id)
        # Deduplicate while preserving order.
        seen = set()
        result = []
        for pid in partner_ids:
            if pid not in seen:
                seen.add(pid)
                result.append(pid)
        return result

    def _create_camp_discuss_channel(self):
        """Create one ``discuss.channel`` per event missing one.

        - Skips events without a kierownik (``user_id``); creation is deferred
          until the kierownik is assigned (handled by ``write`` sync below).
        - Idempotent: if a channel already references this event via
          ``camp_event_id``, do nothing.
        """
        channel_model = self.env["discuss.channel"]
        for event in self:
            if not event.user_id:
                continue
            existing = channel_model.search([("camp_event_id", "=", event.id)], limit=1)
            if existing:
                continue
            partner_ids = event._camp_channel_partner_ids()
            if not partner_ids:
                # No real recipients yet — nothing to subscribe.
                continue
            channel = channel_model.with_context(mail_create_nosubscribe=True).create(
                {
                    "name": event.name,
                    "channel_type": "group",
                    "camp_event_id": event.id,
                    "description": _("Operational chat for camp shift %s. Auto-created.")
                    % event.name,
                }
            )
            channel.add_members(partner_ids=partner_ids)

    def _sync_camp_discuss_channel_members(self):
        """Sync channel members with current (kierownik + staff) line-up.

        Called from ``write`` whenever ``user_id`` or ``staff_ids`` change.
        Adds new partners; does NOT remove dropped staff to preserve audit
        trail of past conversations (departed staff lose access via groups,
        not via channel pruning).
        """
        channel_model = self.env["discuss.channel"]
        for event in self:
            channel = channel_model.search([("camp_event_id", "=", event.id)], limit=1)
            if not channel:
                # Channel may not exist yet (kierownik just being assigned).
                # Create on the fly.
                event._create_camp_discuss_channel()
                continue
            target_partner_ids = event._camp_channel_partner_ids()
            if not target_partner_ids:
                continue
            current_partner_ids = set(channel.channel_partner_ids.ids)
            to_add = [pid for pid in target_partner_ids if pid not in current_partner_ids]
            if to_add:
                channel.add_members(partner_ids=to_add)

    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)
        try:
            events._create_camp_discuss_channel()
        except Exception:  # noqa: BLE001 — never block event creation on channel issue
            _logger.exception(
                "Failed to auto-create discuss.channel for event(s) %s",
                events.ids,
            )
        return events

    def write(self, vals):
        res = super().write(vals)
        if "user_id" in vals or "staff_ids" in vals:
            try:
                self._sync_camp_discuss_channel_members()
            except Exception:  # noqa: BLE001 — never block event write on channel issue
                _logger.exception(
                    "Failed to sync discuss.channel members for event(s) %s",
                    self.ids,
                )
        return res
