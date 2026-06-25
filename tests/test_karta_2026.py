# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — tests for Karta Kwalifikacyjna wzór 2026 (§10 Dz.U. 2026/704)
# + R1 hard block (water/heights) + §13 RSPTS manual verification workflow.
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestKarta2026(TransactionCase):
    """§10 pkt 9 structured fields, wzor versioning, R1 blockade, §13 RSPTS."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(cls.env.context, tracking_disable=True, no_reset_password=True)
        )
        cls.event = cls.env["event.event"].create(
            {
                "name": "Karta Test Camp 2026",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-14 18:00:00",
            }
        )
        cls.child = cls.env["camp.participant"].create(
            {
                "first_name": "Zuzia",
                "last_name": "Karta",
                "birth_date": "2015-05-05",
            }
        )
        cls.admin_user = cls.env.ref("base.user_admin")

    # --- §10 wzór 2026 ------------------------------------------------------

    def test_default_wzor_is_2026(self):
        self.assertEqual(self.child.wzor_version, "2026")

    def test_pkt9_fields_store(self):
        self.child.sudo().write(
            {
                "allergy_insect_venom": True,
                "wears_contact_lenses": True,
                "diet_vegetarian": True,
                "fear_of_heights": True,
                "vacc_tetanus_year": "2023",
            }
        )
        child = self.child.sudo()
        self.assertTrue(child.allergy_insect_venom)
        self.assertTrue(child.wears_contact_lenses)
        self.assertIn("HEIGHTS-BLOCK", child.health_risk_flags)
        self.assertIn("INSECT-VENOM", child.health_risk_flags)

    def test_pkt9_locked_after_signoff(self):
        """pkt 9 is parent-declared → frozen once the card is signed."""
        child = self.child.sudo()
        child.write({"hydrophobia": True})
        child.write({"qualification_signed": True})
        with self.assertRaises(UserError):
            child.write({"hydrophobia": False})

    # --- R1 hard block (water / heights) ------------------------------------

    def _make_dziennik_with_child(self):
        env = self.env["fayna.camp.dziennik"].sudo()
        dziennik = env.create(
            {
                "event_id": self.event.id,
                "group_name": "Grupa R1",
                "participant_ids": [(6, 0, [self.child.id])],
            }
        )
        return dziennik

    def test_r1_water_block(self):
        self.child.sudo().write({"hydrophobia": True})
        dziennik = self._make_dziennik_with_child()
        with self.assertRaises(ValidationError):
            self.env["fayna.camp.dziennik.activity"].sudo().create(
                {
                    "dziennik_id": dziennik.id,
                    "content": "Kąpiel w jeziorze",
                    "risk_water": True,
                }
            )

    def test_r1_heights_block(self):
        self.child.sudo().write({"fear_of_heights": True})
        dziennik = self._make_dziennik_with_child()
        with self.assertRaises(ValidationError):
            self.env["fayna.camp.dziennik.activity"].sudo().create(
                {
                    "dziennik_id": dziennik.id,
                    "content": "Park linowy",
                    "risk_heights": True,
                }
            )

    def test_r1_safe_activity_passes(self):
        self.child.sudo().write({"hydrophobia": True})
        dziennik = self._make_dziennik_with_child()
        activity = (
            self.env["fayna.camp.dziennik.activity"]
            .sudo()
            .create(
                {
                    "dziennik_id": dziennik.id,
                    "content": "Zajęcia plastyczne",
                }
            )
        )
        self.assertTrue(activity)

    # --- §13 RSPTS manual verification ---------------------------------------

    def _make_staff_with_certs(self):
        staff = (
            self.env["camp.staff"]
            .sudo()
            .create(
                {
                    "name": "Jan Wychowawca",
                    "event_id": self.event.id,
                    "role": "wychowawca",
                    "date_from": "2026-07-01",
                    "date_to": "2026-07-14",
                }
            )
        )
        certs = self.env["camp.staff.cert"].sudo()
        for cert_type in ("krk", "rps", "wychowawca_course"):
            certs |= certs.create({"staff_id": staff.id, "cert_type": cert_type})
        return staff, certs

    def test_cert_pending_not_valid(self):
        """Fresh cert = pending → NOT valid until admin accepts (R2)."""
        _staff, certs = self._make_staff_with_certs()
        self.assertTrue(all(c.verification_status == "pending" for c in certs))
        self.assertFalse(any(c.is_valid for c in certs))

    def test_admin_verify_makes_valid_and_eligible(self):
        staff, certs = self._make_staff_with_certs()
        certs.with_user(self.admin_user).action_verify()
        self.assertTrue(all(c.is_valid for c in certs))
        self.assertTrue(staff.is_eligible_for_camp)
        self.assertTrue(all(c.verified_by_id == self.admin_user for c in certs))
        self.assertTrue(all(c.verified_date for c in certs))

    def test_non_admin_cannot_verify(self):
        _staff, certs = self._make_staff_with_certs()
        plain_user = (
            self.env["res.users"]
            .sudo()
            .create(
                {
                    "name": "Plain HR",
                    "login": "plain-hr@campscout.test",
                    "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
                }
            )
        )
        with self.assertRaises(UserError):
            certs.with_user(plain_user).action_verify()
        with self.assertRaises(UserError):
            certs.with_user(plain_user).write({"verification_status": "verified"})

    def test_admission_blocked_without_verification(self):
        """§13 hard gate: confirming staff without verified certs fails."""
        staff, _certs = self._make_staff_with_certs()
        with self.assertRaises(ValidationError):
            staff.sudo().write({"state": "confirmed"})

    def test_admission_passes_after_verification(self):
        staff, certs = self._make_staff_with_certs()
        certs.with_user(self.admin_user).action_verify()
        staff.sudo().write({"state": "confirmed"})
        self.assertEqual(staff.state, "confirmed")
