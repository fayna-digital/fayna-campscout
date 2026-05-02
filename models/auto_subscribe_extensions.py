"""Auto-subscribe extensions — relevant followers added on create/write.

Each model below overrides ``_message_auto_subscribe_followers`` to push
the right partners into the chatter so notifications dispatch automatically
without manual subscribe action by staff.

Odoo 17 contract:
- Hook signature: ``_message_auto_subscribe_followers(updated_values, default_subtype_ids)``
- Returns list of 3-tuples: ``(partner_id, subtype_ids, template_xmlid_or_False)``
- Auto-invoked by ``_message_auto_subscribe()`` on create() and on write()
  (the latter only when fields with ``tracking=True`` change).

Resilience rules:
- ``self.env.ref(..., raise_if_not_found=False)`` for group lookups so that a
  yet-to-be-defined group never blocks record creation.
- Skip silently when partner/user is missing — do NOT raise (would block UI).
- ``_inherit``-only — base model files stay untouched (other agents work them).

Note on ``camp.story``:
The model lives in a sibling addon (``fayna_camp_stories``) which is NOT a
hard dependency of this manifest. Adding ``_inherit = "camp.story"`` here
would crash module load whenever the stories addon is absent. The hook for
``camp.story`` therefore lives in that addon (or will be added there as a
follow-up). Documented for traceability.
"""

from odoo import models


# ===========================================================================
# camp.participant — qualification card
# ===========================================================================
class CampParticipantAutoSubscribe(models.Model):
    _inherit = "camp.participant"

    def _message_auto_subscribe_followers(self, updated_values, default_subtype_ids):
        res = super()._message_auto_subscribe_followers(updated_values, default_subtype_ids)
        for rec in self:
            if rec.parent_partner_id:
                res.append((rec.parent_partner_id.id, default_subtype_ids, False))
            # Add kierownik (event responsible) of every event the child is registered to.
            for reg in rec.registration_ids:
                event = reg.event_id
                if event and event.user_id and event.user_id.partner_id:
                    res.append((event.user_id.partner_id.id, default_subtype_ids, False))
        return res


# ===========================================================================
# camp.journal — dziennik (daily activity log)
# ===========================================================================
class CampJournalAutoSubscribe(models.Model):
    _inherit = "camp.journal"

    def _message_auto_subscribe_followers(self, updated_values, default_subtype_ids):
        res = super()._message_auto_subscribe_followers(updated_values, default_subtype_ids)
        for rec in self:
            # Author (wychowawca who wrote the entry). camp.journal uses
            # ``author_id`` (Many2one to res.users), not ``staff_id``.
            if rec.author_id and rec.author_id.partner_id:
                res.append((rec.author_id.partner_id.id, default_subtype_ids, False))
            # Kierownik (event responsible).
            if rec.event_id and rec.event_id.user_id and rec.event_id.user_id.partner_id:
                res.append((rec.event_id.user_id.partner_id.id, default_subtype_ids, False))
        return res


# ===========================================================================
# camp.daily.report
# ===========================================================================
class CampDailyReportAutoSubscribe(models.Model):
    _inherit = "camp.daily.report"

    def _message_auto_subscribe_followers(self, updated_values, default_subtype_ids):
        res = super()._message_auto_subscribe_followers(updated_values, default_subtype_ids)
        organizator_group = self.env.ref(
            "fayna_camp_portal.group_camp_organizator", raise_if_not_found=False
        )
        organizator_partners = (
            organizator_group.users.mapped("partner_id")
            if organizator_group
            else self.env["res.partner"]
        )
        for rec in self:
            # Kierownik (event responsible).
            if rec.event_id and rec.event_id.user_id and rec.event_id.user_id.partner_id:
                res.append((rec.event_id.user_id.partner_id.id, default_subtype_ids, False))
            # All organizators.
            for partner in organizator_partners:
                res.append((partner.id, default_subtype_ids, False))
        return res


# ===========================================================================
# camp.incident.report
# ===========================================================================
class CampIncidentReportAutoSubscribe(models.Model):
    _inherit = "camp.incident.report"

    def _message_auto_subscribe_followers(self, updated_values, default_subtype_ids):
        res = super()._message_auto_subscribe_followers(updated_values, default_subtype_ids)
        organizator_group = self.env.ref(
            "fayna_camp_portal.group_camp_organizator", raise_if_not_found=False
        )
        medical_group = self.env.ref(
            "fayna_camp_portal.group_medical_officer", raise_if_not_found=False
        )
        organizator_partners = (
            organizator_group.users.mapped("partner_id")
            if organizator_group
            else self.env["res.partner"]
        )
        medical_partners = (
            medical_group.users.mapped("partner_id") if medical_group else self.env["res.partner"]
        )
        for rec in self:
            # Kierownik of the camp shift.
            if rec.event_id and rec.event_id.user_id and rec.event_id.user_id.partner_id:
                res.append((rec.event_id.user_id.partner_id.id, default_subtype_ids, False))
            # Reporter (the wychowawca who logged the incident). The model
            # field is ``reporter_id`` (Many2one to res.users).
            if rec.reporter_id and rec.reporter_id.partner_id:
                res.append((rec.reporter_id.partner_id.id, default_subtype_ids, False))
            # All organizators (operations leadership must always know).
            for partner in organizator_partners:
                res.append((partner.id, default_subtype_ids, False))
            # Medical relevance: camp.incident.report ships with no
            # ``medical_relevant`` boolean. We approximate medical relevance
            # via injury_type/severity. Severity 'severe', 'fatal',
            # 'food_poisoning', 'mass' or any injury_type other than
            # 'abuse_suspected' / non-medical types ⇒ medical involvement.
            severity = rec.severity or ""
            injury_type = getattr(rec, "injury_type", "") or ""
            medical_relevant = severity in (
                "moderate",
                "severe",
                "fatal",
                "mass",
                "food_poisoning",
            ) or injury_type not in ("", "abuse_suspected")
            if medical_relevant:
                for partner in medical_partners:
                    res.append((partner.id, default_subtype_ids, False))
            # If a participant is affected, include their parents.
            for participant in rec.participant_ids:
                if participant.parent_partner_id:
                    res.append((participant.parent_partner_id.id, default_subtype_ids, False))
        return res


# ===========================================================================
# camp.support.request — parent-facing tickets
# ===========================================================================
class CampSupportRequestAutoSubscribe(models.Model):
    _inherit = "camp.support.request"

    def _message_auto_subscribe_followers(self, updated_values, default_subtype_ids):
        res = super()._message_auto_subscribe_followers(updated_values, default_subtype_ids)
        sales_group = self.env.ref("fayna_camp_portal.group_camp_sales", raise_if_not_found=False)
        sales_partners = (
            sales_group.users.mapped("partner_id") if sales_group else self.env["res.partner"]
        )
        for rec in self:
            # Author (the parent who opened the request).
            if rec.partner_id:
                res.append((rec.partner_id.id, default_subtype_ids, False))
            # All sales users.
            for partner in sales_partners:
                res.append((partner.id, default_subtype_ids, False))
        return res


# ===========================================================================
# event.event — camp shift
# ===========================================================================
class EventEventAutoSubscribe(models.Model):
    _inherit = "event.event"

    def _message_auto_subscribe_followers(self, updated_values, default_subtype_ids):
        res = super()._message_auto_subscribe_followers(updated_values, default_subtype_ids)
        for rec in self:
            # Kierownik (event responsible).
            if rec.user_id and rec.user_id.partner_id:
                res.append((rec.user_id.partner_id.id, default_subtype_ids, False))
            # All staff assigned to this shift.
            for staff in rec.staff_ids:
                if staff.user_id and staff.user_id.partner_id:
                    res.append((staff.user_id.partner_id.id, default_subtype_ids, False))
        return res
