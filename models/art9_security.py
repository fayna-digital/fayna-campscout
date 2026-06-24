# RODO art.9 — reliable ORM-level masking of children's medical data.
#
# WHY: field-level `groups=` hides a field in VIEWS, but the VALUE is still
# returned by ORM read() for any user with model read-access (e.g. бухгалтер
# /Finance). That leaked art.9 (allergies/medications/...). This module masks
# the values at read() level and hides participant attachments (karta PDF) from
# users who are NOT allowed to see the card (TZ §6j/§6l/§6n).
#
# WHO may see art.9: group_medical_access (медик + виховник + керівник +
# продавець + організатор via implied chain) + base.group_portal (батько —
# scoped to own child by record-rule). Masked for: бухгалтер (group_camp_finance),
# молода кадра, інші ролі без medical-access.

from odoo import models

_ART9_FIELDS = (
    "allergies", "medications", "chronic_conditions", "doctor_notes",
    "allergy_meds", "allergy_pollen", "allergy_food", "allergy_insect_venom",
    "motion_sickness", "orthodontic_appliance", "wears_glasses",
    "wears_contact_lenses", "diet_low_calorie", "diet_vegetarian",
    "emotional_expression_issues", "group_functioning_issues",
    "psycho_behavioral_notes", "vacc_other", "health_risk_flags",
    "iii_health_events", "iii_medication_given",
)


def _art9_visible(env):
    """True if the current user may see children's art.9 medical data."""
    u = env.user
    return bool(
        u._is_superuser()
        or u._is_system()
        or u.has_group("fayna_camp_portal.group_medical_access")
        or u.has_group("base.group_portal")
    )


class CampParticipantArt9(models.Model):
    _inherit = "camp.participant"

    def read(self, fields=None, load="_classic_read"):
        # Mask in the public read() path (RPC / explicit .read([...])).
        res = super().read(fields=fields, load=load)
        if _art9_visible(self.env):
            return res
        mask = set(_ART9_FIELDS)
        for rec in res:
            for fname in mask.intersection(rec):
                rec[fname] = False
        return res

    def _read(self, fields):
        # Mask attribute access (record.allergies) too — that path goes through
        # _read → ORM cache, bypassing the public read(). We overwrite the cache
        # for art.9 fields with False for non-medical users. Cache is per-env, so
        # a medical user's env (separate) still sees the real values.
        super()._read(fields)
        if _art9_visible(self.env):
            return
        for fname in set(fields) & set(_ART9_FIELDS):
            field = self._fields.get(fname)
            if field is not None:
                self.env.cache.update(self, field, [False] * len(self))


class IrAttachmentArt9(models.Model):
    _inherit = "ir.attachment"

    def _search(self, domain, offset=0, limit=None, order=None,
                access_rights_uid=None):
        # Hide camp.participant attachments (karta PDF with medical data) from
        # users who may not see the card. Native attachment-check alone leaks
        # them because Finance can read the participant record itself.
        if not _art9_visible(self.env):
            domain = ["&", "!", ("res_model", "=", "camp.participant")] + list(
                domain or []
            )
        return super()._search(
            domain, offset=offset, limit=limit, order=order,
            access_rights_uid=access_rights_uid,
        )
