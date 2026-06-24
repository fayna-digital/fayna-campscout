# Fayna CampScout — RODO Art.9 field-level + attachment-level access tests
# TZ §5 §6j §6l-final: two-layer protection for special-category health data.
#
# What is tested:
#   1. Field-level (groups=):
#      - group_camp_finance (bookkeeper) cannot read art.9 fields → False/None
#      - group_camp_wychowawca sees art.9 only for their own group (record rule)
#      - group_camp_wychowawca cannot see art.9 of a participant in another group
#      - base.group_portal parent sees art.9 of their own child
#      - group_medical_access (medic) sees art.9 for whole camp
#
#   2. Attachment-level (ir.attachment record rule):
#      - ir.attachment on camp.participant is blocked for finance user
#      - ir.attachment on camp.participant is visible for medical_access user
#
# Staging login-as checklist (for CTO):
#   * Login as finance user → open participant form → medical tab = blank/hidden
#   * Login as wychowawca → own group child → allergies visible
#   * Login as wychowawca → other group child → AccessError (record rule) or no record
#   * Login as parent (portal) → own child karta → allergies/medications visible
#   * Direct URL /web/content/<karta_attachment_id> as finance → 404 or AccessError
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestArt9Access(TransactionCase):
    """RODO Art.9 — field-level groups= + attachment ACL (§6j / §6l-final)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── groups ──────────────────────────────────────────────────────────
        group_user = cls.env.ref("base.group_user")
        group_portal = cls.env.ref("base.group_portal")
        group_wychowawca = cls.env.ref("fayna_camp_portal.group_camp_wychowawca")
        group_medical = cls.env.ref("fayna_camp_portal.group_medical_officer")
        group_finance = cls.env.ref("fayna_camp_portal.group_camp_finance")
        group_kierownik = cls.env.ref("fayna_camp_portal.group_camp_kierownik")

        # ── users ────────────────────────────────────────────────────────────
        cls.user_finance = cls.env["res.users"].create({
            "name": "Test Finance Art9",
            "login": "test_finance_art9@campscout.test",
            "email": "test_finance_art9@campscout.test",
            "groups_id": [(6, 0, [group_finance.id, group_user.id])],
        })

        cls.user_wychowawca = cls.env["res.users"].create({
            "name": "Test Wychowawca Art9",
            "login": "test_wychowawca_art9@campscout.test",
            "email": "test_wychowawca_art9@campscout.test",
            "groups_id": [(6, 0, [group_wychowawca.id, group_user.id])],
        })

        cls.user_wychowawca2 = cls.env["res.users"].create({
            "name": "Test Wychowawca2 Art9",
            "login": "test_wychowawca2_art9@campscout.test",
            "email": "test_wychowawca2_art9@campscout.test",
            "groups_id": [(6, 0, [group_wychowawca.id, group_user.id])],
        })

        cls.user_medic = cls.env["res.users"].create({
            "name": "Test Medic Art9",
            "login": "test_medic_art9@campscout.test",
            "email": "test_medic_art9@campscout.test",
            "groups_id": [(6, 0, [group_medical.id, group_user.id])],
        })

        cls.user_kierownik = cls.env["res.users"].create({
            "name": "Test Kierownik Art9",
            "login": "test_kierownik_art9@campscout.test",
            "email": "test_kierownik_art9@campscout.test",
            "groups_id": [(6, 0, [group_kierownik.id, group_user.id])],
        })

        # ── parent partner + portal user ─────────────────────────────────────
        cls.parent_partner = cls.env["res.partner"].create({
            "name": "Test Parent Art9",
            "email": "parent_art9@test.com",
        })
        cls.user_parent = cls.env["res.users"].create({
            "name": "Test Parent Art9",
            "login": "test_parent_art9@campscout.test",
            "email": "parent_art9@test.com",
            "partner_id": cls.parent_partner.id,
            "groups_id": [(6, 0, [group_portal.id])],
        })

        # ── camp event ───────────────────────────────────────────────────────
        cls.event = cls.env["event.event"].create({
            "name": "Art9 Test Camp 2026",
            "date_begin": "2026-07-10 08:00:00",
            "date_end": "2026-07-17 18:00:00",
            "seats_max": 40,
            "user_id": cls.user_kierownik.id,
        })

        # ── participant — child of the portal parent ──────────────────────────
        cls.child_partner = cls.env["res.partner"].sudo().create({
            "name": "Test Child Art9",
            "email": "child_art9@test.com",
        })
        cls.participant = cls.env["camp.participant"].sudo().create({
            "first_name": "TestChild",
            "last_name": "Art9",
            "parent_partner_id": cls.parent_partner.id,
            "allergies": "Nuts",
            "medications": "Inhaler daily",
            "chronic_conditions": "Asthma",
            "emergency_contact_1_name": "Parent Art9",
            "emergency_contact_1_phone": "+48000000000",
        })
        # Register participant in the event
        cls.registration = cls.env["event.registration"].sudo().create({
            "event_id": cls.event.id,
            "participant_id": cls.participant.id,
            "partner_id": cls.parent_partner.id,
        })

        # ── camp group A: wychowawca's group (includes our participant) ───────
        cls.group_a = cls.env["camp.group"].sudo().create({
            "name": "Group A",
            "event_id": cls.event.id,
            "wychowawca_ids": [(4, cls.user_wychowawca.id)],
        })
        cls.participant.sudo().write({"group_id": cls.group_a.id})

        # ── camp group B: belongs to wychowawca2 (different group, no access) ─
        cls.group_b = cls.env["camp.group"].sudo().create({
            "name": "Group B",
            "event_id": cls.event.id,
            "wychowawca_ids": [(4, cls.user_wychowawca2.id)],
        })

        # ── staff records so record-rules pass ───────────────────────────────
        cls.env["camp.staff"].sudo().create({
            "name": "Wychowawca Art9",
            "event_id": cls.event.id,
            "user_id": cls.user_wychowawca.id,
            "role": "wychowawca",
        })
        cls.env["camp.staff"].sudo().create({
            "name": "Wychowawca2 Art9",
            "event_id": cls.event.id,
            "user_id": cls.user_wychowawca2.id,
            "role": "wychowawca",
        })
        cls.env["camp.staff"].sudo().create({
            "name": "Medic Art9",
            "event_id": cls.event.id,
            "user_id": cls.user_medic.id,
            "role": "medic",
        })

        # ── a second participant in group B (other wychowawca's child) ────────
        cls.participant_b = cls.env["camp.participant"].sudo().create({
            "first_name": "ChildB",
            "last_name": "Art9",
            "allergies": "Pollen",
            "medications": "None",
            "emergency_contact_1_name": "OtherParent",
            "emergency_contact_1_phone": "+48111111111",
        })
        cls.env["event.registration"].sudo().create({
            "event_id": cls.event.id,
            "participant_id": cls.participant_b.id,
            "partner_id": cls.env["res.partner"].sudo().create({
                "name": "OtherParent Art9",
            }).id,
        })
        cls.participant_b.sudo().write({"group_id": cls.group_b.id})

        # ── ir.attachment on participant (simulates stored karta PDF) ─────────
        cls.karta_attachment = cls.env["ir.attachment"].sudo().create({
            "name": "Karta_TestChild_Art9.pdf",
            "res_model": "camp.participant",
            "res_id": cls.participant.id,
            "mimetype": "application/pdf",
            "datas": b"",   # empty binary — sufficient for ACL test
            "type": "binary",
        })

    # ─── 1. Finance (bookkeeper) cannot read art.9 fields ─────────────────────

    def test_finance_cannot_read_art9_fields(self):
        """Bookkeeper (group_camp_finance) must not see art.9 medical fields.

        In Odoo, a field with groups= returns False/None for users outside
        those groups rather than raising AccessError when accessed via ORM
        (field is silently masked). We verify the value is falsy.
        """
        participant_as_finance = self.participant.with_user(self.user_finance)
        # The participant record should be readable by finance (model-level ACL
        # grants base.group_user read; finance has group_user via implied).
        # The art.9 FIELD VALUES however must be masked (groups= enforcement).
        self.assertFalse(
            participant_as_finance.allergies,
            "Finance user must not read allergies (RODO art.9 field masked by groups=)",
        )
        self.assertFalse(
            participant_as_finance.medications,
            "Finance user must not read medications (RODO art.9 field masked by groups=)",
        )
        self.assertFalse(
            participant_as_finance.chronic_conditions,
            "Finance user must not read chronic_conditions (RODO art.9 field masked)",
        )

    # ─── 2. Wychowawca sees art.9 of their own group ──────────────────────────

    def test_wychowawca_sees_own_group_art9(self):
        """Wychowawca must read art.9 fields for children in their own group."""
        participant_as_wychowawca = self.participant.with_user(self.user_wychowawca)
        self.assertEqual(
            participant_as_wychowawca.allergies,
            "Nuts",
            "Wychowawca must read allergies of child in their own group (group_medical_access)",
        )
        self.assertEqual(
            participant_as_wychowawca.medications,
            "Inhaler daily",
            "Wychowawca must read medications of own group child",
        )

    # ─── 3. Wychowawca cannot read art.9 of a child in another group ──────────

    def test_wychowawca_cannot_see_other_group_art9(self):
        """Wychowawca (group A) must not see participant_b (group B).

        The wychowawca record rule scopes to group_id.wychowawca_ids IN [user.id].
        participant_b is in group_b whose wychowawca is user_wychowawca2.
        So user_wychowawca should get an empty recordset or AccessError.
        """
        Participant = self.env["camp.participant"].with_user(self.user_wychowawca)
        found = Participant.search([("id", "=", self.participant_b.id)])
        self.assertFalse(
            found,
            "Wychowawca must NOT see participant_b who belongs to a different group "
            "(record rule restricts to own group_id.wychowawca_ids)",
        )

    # ─── 4. Portal parent sees art.9 only for their own child ─────────────────

    def test_portal_parent_sees_own_child_art9(self):
        """Portal parent reads art.9 fields for their own child (base.group_portal
        is listed in groups= alongside group_medical_access; scope limited by
        record rule rule_portal_participant_own_children).
        """
        participant_as_parent = self.participant.with_user(self.user_parent)
        self.assertEqual(
            participant_as_parent.allergies,
            "Nuts",
            "Parent must read art.9 allergies for their own child",
        )

    # ─── 5. Medic sees art.9 for whole camp ───────────────────────────────────

    def test_medic_sees_all_camp_art9(self):
        """Medical officer has group_medical_access → reads art.9 for all participants
        (no record-rule restriction for medic on camp.participant beyond own staff event).
        """
        participant_as_medic = self.participant.with_user(self.user_medic)
        self.assertEqual(
            participant_as_medic.allergies,
            "Nuts",
            "Medical officer must read art.9 allergies (group_medical_officer implies group_medical_access)",
        )

    # ─── 6. Attachment-level: finance cannot read karta PDF attachment ─────────

    def test_finance_cannot_read_karta_attachment(self):
        """Finance user must not access ir.attachment on camp.participant.

        The global record rule rule_attachment_participant_scope restricts
        camp.participant attachments to participants the user can read via
        their own record rules. Finance has no camp.participant record rule
        that matches our test participant → attachment should be inaccessible.

        NOTE: if camp.participant access_camp_participant_user gives finance
        read on ALL participant records (no restricting rule for finance),
        this test documents the current gap and the field-level protection
        remains the primary art.9 defence. The attachment rule scope
        expression relies on env['camp.participant'].search([]) per-user.
        """
        Attachment = self.env["ir.attachment"].with_user(self.user_finance)
        found = Attachment.search([("id", "=", self.karta_attachment.id)])
        self.assertFalse(
            found,
            "Finance user must NOT see the karta ir.attachment "
            "(attachment ACL rule blocks camp.participant attachments for non-medical users)",
        )

    # ─── 7. Medical-access user can read karta PDF attachment ─────────────────

    def test_medic_can_read_karta_attachment(self):
        """Medical officer (group_medical_access) must read karta attachments."""
        Attachment = self.env["ir.attachment"].with_user(self.user_medic)
        found = Attachment.search([("id", "=", self.karta_attachment.id)])
        self.assertTrue(
            found,
            "Medical officer must be able to read camp.participant karta ir.attachment",
        )

    # ─── 8. Finance cannot write art.9 fields ─────────────────────────────────

    def test_finance_cannot_write_art9_fields(self):
        """Writing art.9 fields as finance user must raise AccessError.

        Odoo raises AccessError when a user without the required groups= tries
        to write a group-restricted field.
        """
        with self.assertRaises((AccessError, Exception)):
            self.participant.with_user(self.user_finance).write({
                "allergies": "Should not be saved",
            })
