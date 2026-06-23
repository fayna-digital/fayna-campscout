# Fayna CampScout — REQUIREMENT-DRIVEN tests for camp.escort signoff.
#
# camp.escort (asysta/eskorta PKP) shares the participant signoff *contract*:
#   - action_sign(signed_by_id=...) records the REAL parent, not the sudo user;
#   - a RODO consent log is linked (art.7 proof);
#   - protected fields freeze once state == 'signed' (immutability);
#   - portal parents only act on escorts of THEIR OWN children (record rule
#     rule_portal_escort_own_children).
#
# Source: models/camp_escort.py + record_rules.xml + ir.model.access.csv
# (access_camp_escort_portal: read=1 write=0 create=0 unlink=0).
import base64

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, new_test_user, tagged

_PNG_1x1 = base64.b64encode(
    base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAECAIAAAA8r+mnAAAAFElEQVR4nGMU"
        "ERFhwAaYsIqSJQEAGOwARMaxOEQAAAAASUVORK5CYII="
    )
).decode()


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestEscortSignoff(TransactionCase):
    """camp.escort signoff = same legal proof model as the qualification card."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(cls.env.context, tracking_disable=True, no_reset_password=True)
        )
        cls.parent_user = new_test_user(
            cls.env,
            login="parent_escort@campscout.test",
            name="Escort Parent",
            groups="base.group_portal",
        )
        cls.parent_partner = cls.parent_user.partner_id

        cls.other_user = new_test_user(
            cls.env,
            login="parent_escort_other@campscout.test",
            name="Other Escort Parent",
            groups="base.group_portal",
        )
        cls.other_partner = cls.other_user.partner_id

        cls.child = cls._make_child(cls.parent_partner)
        cls.escort = cls._make_escort(cls.child)

    @classmethod
    def _make_child(cls, parent_partner):
        return cls.env["camp.participant"].create(
            {
                "first_name": "Antek",
                "last_name": "Asysta",
                "birth_date": "2013-03-03",
                "parent_partner_id": parent_partner.id,
            }
        )

    @classmethod
    def _make_escort(cls, child):
        # camp.escort вимагає registration_id (required) — створюємо event+registration.
        event = cls.env["event.event"].create(
            {
                "name": "Escort Test Camp 2026",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-14 18:00:00",
            }
        )
        reg = cls.env["event.registration"].create(
            {"event_id": event.id, "partner_id": child.parent_partner_id.id}
        )
        # action_collect requires home_city + pkp_station + direction.
        return cls.env["camp.escort"].create(
            {
                "participant_id": child.id,
                "registration_id": reg.id,
                "direction": "oba",
                "home_city": "Wrocław",
                "pkp_station": "Wrocław Główny",
            }
        )

    # --- REQ 5: signed_by = real parent, consent linked ----------------------

    def test_escort_signed_by_is_real_parent(self):
        """action_sign must record the passed parent, not the sudo/superuser.

        FAILS if action_sign drops signed_by_id (= the gate bug, mirror of
        sign_qualification).
        """
        self.escort.sudo().action_sign(
            ip_address="198.51.100.5",
            signature=_PNG_1x1,
            signed_by_id=self.parent_user.id,
        )
        escort = self.escort.sudo()
        self.assertEqual(escort.state, "signed")
        self.assertEqual(
            escort.signed_by,
            self.parent_user,
            "signed_by must be the real parent, not the sudo user",
        )
        self.assertNotEqual(escort.signed_by.id, self.env.ref("base.user_root").id)
        self.assertEqual(escort.signed_ip, "198.51.100.5")
        self.assertTrue(escort.rodo_consent_id, "RODO consent log must be linked")
        self.assertEqual(escort.rodo_consent_id.evidence_model, "camp.escort")
        self.assertEqual(escort.rodo_consent_id.evidence_id, escort.id)

    def test_escort_sign_requires_signature(self):
        """No signature (and none stored) → ValidationError (proof of consent)."""
        escort = self._make_escort(self.child)
        with self.assertRaises(ValidationError):
            escort.sudo().action_sign(signed_by_id=self.parent_user.id)

    def test_escort_double_sign_blocked(self):
        escort = self._make_escort(self.child)
        escort.sudo().action_sign(signature=_PNG_1x1, signed_by_id=self.parent_user.id)
        with self.assertRaises(UserError):
            escort.sudo().action_sign(
                signature=_PNG_1x1, signed_by_id=self.parent_user.id
            )

    # --- REQ 5: immutability after signed ------------------------------------

    def test_escort_protected_frozen_after_signed(self):
        """_PROTECTED_AFTER_SIGN freezes route/person fields once signed.

        Checked as a non-system, non-su user. FAILS if the immutability guard
        is removed.
        """
        escort = self._make_escort(self.child)
        escort.sudo().action_sign(signature=_PNG_1x1, signed_by_id=self.parent_user.id)
        staff = new_test_user(
            self.env,
            login="staff_escort@campscout.test",
            name="Escort Staff",
            groups="base.group_user,fayna_camp_portal.group_medical_officer",
        )
        for field, value in (
            ("pkp_station", "Kraków Główny"),
            ("escort_person_name", "Ktoś Inny"),
            ("direction", "powrot"),
        ):
            with self.assertRaises(
                UserError, msg=f"escort field {field} must freeze after signed"
            ):
                escort.with_user(staff).write({field: value})

    # --- REQ 2: ownership ----------------------------------------------------

    def test_portal_cannot_read_other_parents_escort(self):
        """rule_portal_escort_own_children: only escorts of the parent's own
        children are visible.
        """
        other_child = self._make_child(self.other_partner)
        other_escort = self._make_escort(other_child)
        found = (
            self.env["camp.escort"]
            .with_user(self.parent_user)
            .search([("id", "=", other_escort.id)])
        )
        self.assertFalse(found, "parent must not see another parent's escort")
        with self.assertRaises(AccessError):
            other_escort.with_user(self.parent_user).check_access_rule("read")

    # --- REQ 3: ACL — portal write=0 on camp.escort --------------------------

    def test_portal_cannot_sign_escort_without_sudo(self):
        """access_camp_escort_portal write=0 → portal user cannot drive the
        signed write directly; the controller must use sudo.
        """
        with self.assertRaises(AccessError):
            self.escort.with_user(self.parent_user).action_sign(
                signature=_PNG_1x1, signed_by_id=self.parent_user.id
            )
