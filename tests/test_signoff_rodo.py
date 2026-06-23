# Fayna CampScout — REQUIREMENT-DRIVEN tests for qualification-card signoff.
#
# These tests assert the LEGAL requirements of the parent signoff flow, not the
# current implementation shape. Each test is written so that it FAILS if the
# requirement is broken (e.g. signed_by recorded as admin/superuser instead of
# the real parent, immutability bypassed, ownership leaked).
#
# Source of requirements: docs/TZ.md (Karta kwalifikacyjna §5/§10 MEN law,
# RODO art.7 proof of consent, art.30 audit trail) + record_rules.xml
# (rule_portal_participant_own_children).
#
# 1x1 transparent PNG, base64, no "data:image/png;base64," prefix — Odoo Binary
# stores raw bytes (matches sign_qualification docstring contract).
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
class TestSignoffRodo(TransactionCase):
    """Parent signoff = legal proof. signed_by MUST be the real parent."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(cls.env.context, tracking_disable=True, no_reset_password=True)
        )
        # Two independent parents, each a portal user bound to their own partner.
        cls.parent_user = new_test_user(
            cls.env,
            login="parent_signoff@campscout.test",
            name="Parent One",
            groups="base.group_portal",
        )
        cls.parent_partner = cls.parent_user.partner_id

        cls.other_user = new_test_user(
            cls.env,
            login="parent_other@campscout.test",
            name="Parent Two",
            groups="base.group_portal",
        )
        cls.other_partner = cls.other_user.partner_id

        cls.child = cls._make_child(cls.parent_partner)

    @classmethod
    def _make_child(cls, parent_partner):
        # camp.participant _inherits res.partner via partner_id (delegation).
        return cls.env["camp.participant"].create(
            {
                "first_name": "Zuzia",
                "last_name": "Kowalska",
                "birth_date": "2015-05-05",
                "parent_partner_id": parent_partner.id,
                "emergency_contact_1_name": "Babcia Kowalska",
                "emergency_contact_1_phone": "+48500111222",
            }
        )

    # --- REQ 1: signed_by = real parent, NOT superuser/admin -----------------

    def test_signed_by_is_real_parent_not_superuser(self):
        """RODO/legal proof: qualification_signed_by must be the passed parent,
        NOT the sudo/superuser the controller runs the write as.

        Mirrors the production controller flow: ownership is checked, then the
        method is called via sudo() with signed_by_id=<real parent user id>.
        This test FAILS if sign_qualification ever drops signed_by_id and falls
        back to env.user (= admin/superuser under sudo) — the exact gate bug.
        """
        # The controller calls .sudo() (env.user becomes the sudo user / admin),
        # but passes the real parent id explicitly.
        self.child.sudo().sign_qualification(
            ip_address="203.0.113.7",
            signature=_PNG_1x1,
            signer_name="Parent One",
            signed_by_id=self.parent_user.id,
        )
        child = self.child.sudo()
        self.assertTrue(child.qualification_signed)
        self.assertEqual(
            child.qualification_signed_by,
            self.parent_user,
            "qualification_signed_by must be the real parent, not the sudo user",
        )
        self.assertNotEqual(
            child.qualification_signed_by.id,
            self.env.ref("base.user_root").id,
            "signed_by must never be SUPERUSER",
        )
        self.assertNotEqual(
            child.qualification_signed_by.id,
            self.env.ref("base.user_admin").id,
            "signed_by must never be admin",
        )

    def test_signed_records_ip_and_consent(self):
        """art.7 RODO: a signed card stores IP + a linked consent log row."""
        self.child.sudo().sign_qualification(
            ip_address="203.0.113.99",
            signature=_PNG_1x1,
            signed_by_id=self.parent_user.id,
        )
        child = self.child.sudo()
        self.assertEqual(child.qualification_signed_ip, "203.0.113.99")
        self.assertTrue(child.rodo_consent_id, "a RODO consent log must be linked")
        self.assertEqual(
            child.rodo_consent_id.evidence_model,
            "camp.participant",
            "consent evidence must point back at the participant model",
        )
        self.assertEqual(child.rodo_consent_id.evidence_id, child.id)
        self.assertEqual(
            child.rodo_consent_id.partner_id,
            self.parent_partner,
            "consent subject must be the parent partner",
        )

    def test_double_sign_blocked(self):
        """A card can be signed exactly once (legal immutability of the act)."""
        self.child.sudo().sign_qualification(
            signature=_PNG_1x1, signed_by_id=self.parent_user.id
        )
        with self.assertRaises(UserError):
            self.child.sudo().sign_qualification(
                signature=_PNG_1x1, signed_by_id=self.parent_user.id
            )

    # --- REQ 6: birth_date guard --------------------------------------------

    def test_sign_without_birth_date_blocked(self):
        """MEN law: a card without DOB cannot be legally signed."""
        child = self.env["camp.participant"].create(
            {
                "first_name": "Brak",
                "last_name": "Daty",
                "parent_partner_id": self.parent_partner.id,
                "emergency_contact_1_name": "Opiekun",
                "emergency_contact_1_phone": "+48500999888",
            }
        )
        # birth_date empty → constraint must reject the signed state.
        with self.assertRaises(ValidationError):
            child.sudo().sign_qualification(signed_by_id=self.parent_user.id)

    def test_sign_without_emergency_contact_blocked(self):
        """A card without emergency contact 1 cannot be signed."""
        child = self.env["camp.participant"].create(
            {
                "first_name": "Bez",
                "last_name": "Kontaktu",
                "birth_date": "2014-01-01",
                "parent_partner_id": self.parent_partner.id,
            }
        )
        with self.assertRaises(ValidationError):
            child.sudo().sign_qualification(signed_by_id=self.parent_user.id)

    # --- REQ 2: ownership ----------------------------------------------------

    def test_portal_user_cannot_read_other_parents_child(self):
        """record-rule rule_portal_participant_own_children: a portal parent
        only sees children where parent_partner_id == their own partner.

        FAILS if the record rule is removed/loosened (ownership leak).
        """
        # parent_user searches → must NOT find a child owned by other_partner.
        other_child = self._make_child(self.other_partner)
        found = (
            self.env["camp.participant"]
            .with_user(self.parent_user)
            .search([("id", "=", other_child.id)])
        )
        self.assertFalse(
            found, "portal parent must not see another parent's child via search"
        )
        # Direct access must be blocked by the record rule, not silently allowed.
        with self.assertRaises(AccessError):
            other_child.with_user(self.parent_user).check_access_rule("read")

    def test_portal_user_sees_own_child(self):
        """Positive control: a parent DOES see their own child (rule not over-tight)."""
        found = (
            self.env["camp.participant"]
            .with_user(self.parent_user)
            .search([("id", "=", self.child.id)])
        )
        self.assertEqual(found, self.child)

    # --- REQ 3: ACL — portal write=0 on camp.participant ---------------------

    def test_portal_user_cannot_write_participant_directly(self):
        """ACL access_camp_participant_portal: perm_write=0.

        A portal user must NOT be able to write camp.participant without the
        controller's sudo pattern. FAILS if perm_write is flipped to 1.
        """
        with self.assertRaises(AccessError):
            self.child.with_user(self.parent_user).write({"notes": "hack"})

    def test_portal_user_cannot_sign_own_child_without_sudo(self):
        """Even on their OWN child, a portal user cannot drive the signed write
        directly (record-rule write=0 + ACL write=0). The controller must use
        the sudo pattern. FAILS if portal write perms are loosened.
        """
        with self.assertRaises(AccessError):
            self.child.with_user(self.parent_user).sign_qualification(
                signature=_PNG_1x1, signed_by_id=self.parent_user.id
            )

    # --- REQ 4: immutability of protected fields after signoff ---------------

    def test_protected_fields_frozen_after_signoff(self):
        """_PROTECTED_AFTER_SIGNOFF: medical/identity fields freeze after sign.

        Enforced for non-system, non-su users (the realistic Sales/Kierownik
        editing case). FAILS if the write() immutability guard is removed.
        """
        child = self._make_child(self.parent_partner)
        child.sudo().sign_qualification(
            signature=_PNG_1x1, signed_by_id=self.parent_user.id
        )
        # A staff user (group_user, not system) must be blocked from editing
        # protected fields on a signed card.
        staff = new_test_user(
            self.env,
            login="staff_immut@campscout.test",
            name="Staff Editor",
            groups="base.group_user,fayna_camp_portal.group_camp_wychowawca",
        )
        for field, value in (
            ("birth_date", "2010-01-01"),
            ("pesel", "99999999999"),
            ("allergies", "changed"),
        ):
            with self.assertRaises(
                UserError, msg="protected field %s must be frozen after signoff" % field
            ):
                child.with_user(staff).write({field: value})

    def test_signature_fields_were_writable_during_signoff(self):
        """The signature/consent fields themselves are NOT protected — the
        signoff write must succeed and populate them. (Guards against an
        over-broad _PROTECTED_AFTER_SIGNOFF that would self-deadlock signoff.)
        """
        child = self._make_child(self.parent_partner)
        child.sudo().sign_qualification(
            signature=_PNG_1x1,
            signer_name="Parent One",
            signed_by_id=self.parent_user.id,
        )
        child = child.sudo()
        self.assertTrue(child.qualification_signature)
        self.assertEqual(child.qualification_signed_by_name, "Parent One")
        self.assertTrue(child.qualification_signed_date)
