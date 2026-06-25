# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — tests for Regulaminy + Teczka KO (TZ_SPRINT_2026-06-10 §4)
# Covers:
#   - camp.regulamin.ack: only the staff member's OWN user can sign (others →
#     UserError), record frozen after signing;
#   - camp.regulamin.action_generate_acks: one ack per staff member, idempotent;
#   - camp.teczka.ko: karty percentage computed correctly from registrations.
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestRegulaminTeczka(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.event = cls.env["event.event"].create(
            {
                "name": "Test Obóz 2026 — turnus T",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-14 18:00:00",
            }
        )

        # Two internal users acting as kadra. Plain employees on purpose —
        # the ACL/record-rule fragments are merged in the integration pass;
        # here we test the METHOD-level gates (action_sign / write guard).
        cls.user_a = cls.env["res.users"].create(
            {
                "name": "Wychowawca A",
                "login": "wych_a@campscout.test",
                "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )
        cls.user_b = cls.env["res.users"].create(
            {
                "name": "Wychowawca B",
                "login": "wych_b@campscout.test",
                "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )

        # Temporary ACLs so the employees can read regulaminy and read/write
        # acks (rolled back with the test transaction; the real ACLs live in
        # security/acl_regulamin_teczka.csv.fragment until merged).
        IrModel = cls.env["ir.model"]
        cls.env["ir.model.access"].create(
            [
                {
                    "name": "test camp.regulamin user read",
                    "model_id": IrModel._get_id("camp.regulamin"),
                    "group_id": cls.env.ref("base.group_user").id,
                    "perm_read": True,
                },
                {
                    "name": "test camp.regulamin.ack user rw",
                    "model_id": IrModel._get_id("camp.regulamin.ack"),
                    "group_id": cls.env.ref("base.group_user").id,
                    "perm_read": True,
                    "perm_write": True,
                },
            ]
        )

        # Kadra (draft state — KRK/RSPTS hard gate fires only on confirm/active).
        cls.staff_a = cls.env["camp.staff"].create(
            {
                "name": "Wychowawca A",
                "event_id": cls.event.id,
                "role": "counselor",
                "user_id": cls.user_a.id,
                "date_from": "2026-07-01",
                "date_to": "2026-07-14",
            }
        )
        cls.staff_b = cls.env["camp.staff"].create(
            {
                "name": "Wychowawca B",
                "event_id": cls.event.id,
                "role": "counselor",
                "user_id": cls.user_b.id,
                "date_from": "2026-07-01",
                "date_to": "2026-07-14",
            }
        )

        cls.regulamin = cls.env["camp.regulamin"].create(
            {
                "name": "Regulamin kąpieli — test",
                "regulamin_type": "kapieli",
                "event_id": cls.event.id,
                "content": "<p>Zakaz kąpieli bez ratownika.</p>",
            }
        )
        cls.regulamin.action_publish()

    # ------------------------------------------------------------------
    # action_generate_acks
    # ------------------------------------------------------------------

    def test_generate_acks_creates_for_whole_kadra(self):
        created = self.regulamin.action_generate_acks()
        self.assertEqual(len(created), 2)
        self.assertEqual(
            set(self.regulamin.ack_ids.mapped("staff_id").ids),
            {self.staff_a.id, self.staff_b.id},
        )
        self.assertEqual(self.regulamin.total_count, 2)
        self.assertEqual(self.regulamin.signed_count, 0)
        self.assertFalse(self.regulamin.all_signed)

    def test_generate_acks_idempotent_and_picks_up_new_staff(self):
        self.regulamin.action_generate_acks()
        # Re-run: no duplicates.
        created_again = self.regulamin.action_generate_acks()
        self.assertEqual(len(created_again), 0)
        self.assertEqual(len(self.regulamin.ack_ids), 2)
        # New staff member joins → re-run creates exactly one new ack.
        staff_c = self.env["camp.staff"].create(
            {
                "name": "Wychowawca C",
                "event_id": self.event.id,
                "role": "counselor",
                "date_from": "2026-07-01",
                "date_to": "2026-07-14",
            }
        )
        created_c = self.regulamin.action_generate_acks()
        self.assertEqual(len(created_c), 1)
        self.assertEqual(created_c.staff_id, staff_c)

    def test_generate_acks_template_requires_event(self):
        template = self.env["camp.regulamin"].create(
            {
                "name": "Szablon ppoż. (wszystkie obozy)",
                "regulamin_type": "ppoz",
            }
        )
        with self.assertRaises(UserError):
            template.action_generate_acks()
        # Explicit event works.
        created = template.action_generate_acks(event=self.event)
        self.assertEqual(len(created), 2)

    # ------------------------------------------------------------------
    # action_sign — owner-only gate
    # ------------------------------------------------------------------

    def _ack_of(self, staff):
        self.regulamin.action_generate_acks()
        return self.regulamin.ack_ids.filtered(lambda a: a.staff_id == staff)

    def test_sign_by_other_user_raises(self):
        ack_a = self._ack_of(self.staff_a)
        with self.assertRaises(UserError):
            ack_a.with_user(self.user_b).action_sign()
        self.assertFalse(ack_a.signed)

    def test_sign_by_other_user_via_write_raises(self):
        """The write()-gate must hold even when bypassing action_sign()."""
        ack_a = self._ack_of(self.staff_a)
        with self.assertRaises(UserError):
            ack_a.with_user(self.user_b).write({"signed": True})
        self.assertFalse(ack_a.signed)

    def test_sign_by_owner_succeeds(self):
        ack_a = self._ack_of(self.staff_a)
        ack_a.with_user(self.user_a).action_sign(ip_address="10.0.0.7")
        self.assertTrue(ack_a.signed)
        self.assertTrue(ack_a.signed_date)
        self.assertEqual(ack_a.signed_ip, "10.0.0.7")
        self.assertEqual(self.regulamin.signed_count, 1)
        # Second signature completes the regulamin.
        ack_b = self._ack_of(self.staff_b)
        ack_b.with_user(self.user_b).action_sign(ip_address="10.0.0.8")
        self.assertTrue(self.regulamin.all_signed)

    def test_sign_without_user_account_raises(self):
        staff_no_user = self.env["camp.staff"].create(
            {
                "name": "Bez konta",
                "event_id": self.event.id,
                "role": "counselor",
                "date_from": "2026-07-01",
                "date_to": "2026-07-14",
            }
        )
        ack = self._ack_of(staff_no_user)
        with self.assertRaises(UserError):
            ack.with_user(self.user_a).action_sign()

    def test_double_sign_raises(self):
        ack_a = self._ack_of(self.staff_a)
        ack_a.with_user(self.user_a).action_sign()
        with self.assertRaises(UserError):
            ack_a.with_user(self.user_a).action_sign()

    # ------------------------------------------------------------------
    # Frozen after signing
    # ------------------------------------------------------------------

    def test_frozen_after_sign(self):
        ack_a = self._ack_of(self.staff_a)
        ack_a.with_user(self.user_a).action_sign()
        # Even the owner cannot touch the record once signed — any field.
        with self.assertRaises(UserError):
            ack_a.with_user(self.user_a).write({"signed_ip": "1.2.3.4"})
        with self.assertRaises(UserError):
            ack_a.with_user(self.user_a).write({"signed": False})

    def test_unsigned_regulamin_count_dashboard(self):
        self.regulamin.action_generate_acks()
        self.assertEqual(self.staff_a.unsigned_regulamin_count, 1)
        ack_a = self.regulamin.ack_ids.filtered(lambda a: a.staff_id == self.staff_a)
        ack_a.with_user(self.user_a).action_sign()
        self.assertEqual(self.staff_a.unsigned_regulamin_count, 0)
        self.assertEqual(self.staff_b.unsigned_regulamin_count, 1)

    def test_check_acks_for_event_returns_unsigned(self):
        self.regulamin.action_generate_acks()
        ack_a = self.regulamin.ack_ids.filtered(lambda a: a.staff_id == self.staff_a)
        ack_a.with_user(self.user_a).action_sign()
        unsigned = self.env["camp.regulamin"].check_acks_for_event(self.event)
        self.assertIn(self.staff_b, unsigned)
        self.assertNotIn(self.staff_a, unsigned)

    # ------------------------------------------------------------------
    # Teczka KO — karty percentage
    # ------------------------------------------------------------------

    def test_teczka_karty_percent(self):
        Participant = self.env["camp.participant"]
        # Emergency contact обов'язковий перед підписом картки
        # (_check_emergency_before_signoff) — INC staging 10.06.
        emergency = {
            "emergency_contact_1_name": "Rodzic Testowy",
            "emergency_contact_1_phone": "+48 600 000 000",
        }
        child_1 = Participant.create(
            {
                "first_name": "Jan",
                "last_name": "Testowy",
                "birth_date": "2015-03-01",
                **emergency,
            }
        )
        child_2 = Participant.create(
            {
                "first_name": "Ola",
                "last_name": "Testowa",
                "birth_date": "2014-09-15",
                **emergency,
            }
        )
        Registration = self.env["event.registration"]
        Registration.create(
            {
                "event_id": self.event.id,
                "participant_id": child_1.id,
                "state": "open",
            }
        )
        Registration.create(
            {
                "event_id": self.event.id,
                "participant_id": child_2.id,
                "state": "open",
            }
        )

        teczka = self.env["camp.teczka.ko"].create({"event_id": self.event.id})
        self.assertEqual(teczka.karty_total, 2)
        self.assertEqual(teczka.karty_signed, 0)
        self.assertEqual(teczka.karty_percent, 0.0)
        self.assertFalse(teczka.karty_ready)
        self.assertFalse(teczka.overall_ready)

        # One card signed → 50%.
        child_1.write({"qualification_signed": True})
        self.env.invalidate_all()
        self.assertEqual(teczka.karty_signed, 1)
        self.assertAlmostEqual(teczka.karty_percent, 50.0)
        self.assertFalse(teczka.karty_ready)

        # Both signed → 100% and ready.
        child_2.write({"qualification_signed": True})
        self.env.invalidate_all()
        self.assertEqual(teczka.karty_signed, 2)
        self.assertAlmostEqual(teczka.karty_percent, 100.0)
        self.assertTrue(teczka.karty_ready)

    def test_teczka_unique_per_event(self):
        self.env["camp.teczka.ko"].create({"event_id": self.event.id})
        with (  # psycopg2 IntegrityError wrapped
            self.assertRaises(Exception),
            self.env.cr.savepoint(),
        ):
            self.env["camp.teczka.ko"].create({"event_id": self.event.id})

    def test_teczka_wypadki_graceful_without_model(self):
        """camp.incident.register is built by a parallel agent — until it is
        in the registry the teczka must degrade gracefully, not crash."""
        teczka = self.env["camp.teczka.ko"].create({"event_id": self.event.id})
        if self.env.get("camp.incident.register") is None:
            self.assertFalse(teczka.wypadki_available)
            self.assertFalse(teczka.wypadki_ready)
            self.assertEqual(teczka.wypadki_count, 0)
        else:
            self.assertTrue(teczka.wypadki_available)

    def test_teczka_regulaminy_section(self):
        teczka = self.env["camp.teczka.ko"].create({"event_id": self.event.id})
        self.assertEqual(teczka.regulamin_total, 1)
        # Staff are draft (not confirmed/active) → no active kadra → not ready.
        self.assertFalse(teczka.regulaminy_ready)
