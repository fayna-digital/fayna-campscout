# -*- coding: utf-8 -*-
"""Portal mixin extensions — `portal.message_thread` chatter integration.

Adds the standard Odoo 17 `portal.mixin` to a small set of camp models so
parent-facing portal pages can render the built-in `portal.message_thread`
chatter (with `is_internal` toggle to hide staff-only notes from parents).

Models extended (all defined in this module's `models/`):

* ``camp.participant`` — qualification card detail page (`/my/participants/<id>`).
* ``camp.support.request`` — support ticket detail page (`/my/support/<id>`).
* ``camp.loyalty.participant`` — loyalty page (`/my/loyalty`, single record).

NOTE on ``camp.story``: lives in a separate module (``fayna_camp_stories``)
which is **not** in this module's manifest ``depends`` list, so we cannot
inherit it from here. The chatter on `/my/stories/<id>` should be wired up
in that module by adding ``portal.mixin`` to ``camp.story`` and a matching
``_compute_access_url`` returning ``/my/stories/<id>``. The XML inheritance
in ``templates/portal_chatter.xml`` for stories is conditional and tolerant
of a missing ``portal.mixin``: it only renders when the controller passes
the ``story`` record explicitly.

Token-based access: the inherited ``portal.mixin`` already provides
``_portal_ensure_token`` which generates a 32-char URL token used by
``portal.message_thread`` to allow chatter actions for guardian users
without an Odoo account (e.g. parent reading a card via signed link).
"""

from odoo import models


class CampParticipantPortal(models.Model):
    _name = "camp.participant"
    _inherit = ["camp.participant", "portal.mixin"]

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = f"/my/participants/{rec.id}"


class CampSupportRequestPortal(models.Model):
    _name = "camp.support.request"
    _inherit = ["camp.support.request", "portal.mixin"]

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = f"/my/support/{rec.id}"


class CampLoyaltyParticipantPortal(models.Model):
    _name = "camp.loyalty.participant"
    _inherit = ["camp.loyalty.participant", "portal.mixin"]

    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            # Loyalty page is partner-scoped (single record per parent),
            # not id-scoped — but `portal.message_thread` still requires
            # a stable URL. Keep `/my/loyalty` for both UX and chatter
            # action redirects after post.
            rec.access_url = "/my/loyalty"
