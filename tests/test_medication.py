# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — тести реєстру ліків (ТЗ тема 2, гейт Fable 2026-08-03)
#
# What is tested (T1-K…T6-K + kejs Tsybulko):
#   1. Reception constraints: bad dose scheme is rejected (порожній прийом).
#   2. Consent gate: no signed canvas consent → no activation (art. 9(2)(a));
#      signature is immutable evidence once signed.
#   3. Grid generation: 2×/day × 7 days → 14 schedule rows (T2-K).
#   4. Kejs Tsybulko: critical psychiatric medication handed over, никогда not
#      issued → cron marks missed + mail.activity for kierownik + SMS CRITICAL
#      via fayna.sms.dispatcher (mocked). SMS body carries NO medication name.
#   5. Non-critical miss → activity only, no SMS.
#   6. 24h unconfirmed miss → ESKALACJA repeat alert; confirmed → closed quietly.
#   7. Scheme change regenerates pending rows only; issued rows are evidence.
#   8. ACL/record rules: medic + kierownik of own camp read/write; wychowawca
#      has no model access at all (AccessError); other-camp medic sees nothing.
#
# Style: tests/test_staffing.py (setUpClass factory helpers) +
# tests/test_art9_access.py (role users + camp.staff rows for record rules).
import base64
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged

SIGNATURE_PNG = base64.b64encode(b"canvas-signature-png-bytes")


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestMedication(TransactionCase):
    """camp.medication.registry / .schedule — grafik, alerty, SMS CRITICAL."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        group_user = cls.env.ref("base.group_user")
        group_medical = cls.env.ref("fayna_camp_portal.group_medical_officer")
        group_kierownik = cls.env.ref("fayna_camp_portal.group_camp_kierownik")
        group_wychowawca = cls.env.ref("fayna_camp_portal.group_camp_wychowawca")

        cls.user_kierownik = cls.env["res.users"].create(
            {
                "name": "Test Kierownik Leki",
                "login": "test_kierownik_leki@campscout.test",
                "email": "test_kierownik_leki@campscout.test",
                "groups_id": [(6, 0, [group_kierownik.id, group_user.id])],
            }
        )
        # SMS CRITICAL target — kierownik must have a phone on the partner.
        cls.user_kierownik.partner_id.write({"mobile": "+48500100200"})

        cls.user_medic = cls.env["res.users"].create(
            {
                "name": "Test Medic Leki",
                "login": "test_medic_leki@campscout.test",
                "email": "test_medic_leki@campscout.test",
                "groups_id": [(6, 0, [group_medical.id, group_user.id])],
            }
        )
        cls.user_medic_other = cls.env["res.users"].create(
            {
                "name": "Test Medic Other Camp",
                "login": "test_medic_other_leki@campscout.test",
                "email": "test_medic_other_leki@campscout.test",
                "groups_id": [(6, 0, [group_medical.id, group_user.id])],
            }
        )
        cls.user_wychowawca = cls.env["res.users"].create(
            {
                "name": "Test Wychowawca Leki",
                "login": "test_wychowawca_leki@campscout.test",
                "email": "test_wychowawca_leki@campscout.test",
                "groups_id": [(6, 0, [group_wychowawca.id, group_user.id])],
            }
        )

        cls.event = cls.env["event.event"].create(
            {
                "name": "Leki Test Camp 2026",
                "date_begin": "2026-07-20 08:00:00",
                "date_end": "2026-08-02 18:00:00",
                "user_id": cls.user_kierownik.id,
            }
        )
        cls.event_other = cls.env["event.event"].create(
            {
                "name": "Leki Other Camp 2026",
                "date_begin": "2026-07-20 08:00:00",
                "date_end": "2026-08-02 18:00:00",
            }
        )
        # camp.staff rows drive the record rules (own-camp scoping).
        cls.env["camp.staff"].create(
            {
                "name": "Medic Leki",
                "event_id": cls.event.id,
                "user_id": cls.user_medic.id,
                "role": "ratownik",
                "date_from": "2026-07-20",
                "date_to": "2026-08-02",
            }
        )
        cls.env["camp.staff"].create(
            {
                "name": "Medic Other Leki",
                "event_id": cls.event_other.id,
                "user_id": cls.user_medic_other.id,
                "role": "ratownik",
                "date_from": "2026-07-20",
                "date_to": "2026-08-02",
            }
        )

        cls.parent = cls.env["res.partner"].create(
            {"name": "Leki Test Parent", "email": "leki-parent@campscout.test"}
        )
        cls.child = cls.env["camp.participant"].create(
            {
                "first_name": "Dmytro",
                "last_name": "Tsybulko",
                "birth_date": "2013-05-01",
                "parent_partner_id": cls.parent.id,
            }
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @classmethod
    def _make_registry(cls, **overrides):
        vals = {
            "participant_id": cls.child.id,
            "event_id": cls.event.id,
            "medication_name": "Sertralina 50mg",
            "quantity": 20,
            "unit": "tab",
            "dosage_frequency": 2,
            "dosage_duration": 7,
            "dosage_times": "08:00, 20:00",
            "received_date": "2026-07-21 07:30:00",
            "handed_by": cls.parent.id,
        }
        vals.update(overrides)
        return cls.env["camp.medication.registry"].create(vals)

    def _sign_and_activate(self, registry):
        registry.action_sign(ip_address="127.0.0.1", signature=SIGNATURE_PNG)
        registry.action_activate()
        return registry

    def _mock_sms(self):
        """Patch fayna.sms.dispatcher.send — SMS never leaves the test."""
        return patch.object(
            self.env.registry["fayna.sms.dispatcher"],
            "send",
            autospec=True,
            return_value={"success": True, "error": None, "provider": "mock"},
        )

    def _missed_alerts(self, registry):
        return registry.activity_ids.filtered(
            lambda a: (a.summary or "").startswith("Pominięto wydanie leku")
        )

    def _escalation_alerts(self, registry):
        return registry.activity_ids.filtered(lambda a: (a.summary or "").startswith("ESKALACJA"))

    # ------------------------------------------------------------------
    # 1. Reception constraints — порожній/битий прийом (T1-K)
    # ------------------------------------------------------------------

    def test_bad_dose_scheme_rejected(self):
        with self.assertRaises(ValidationError):
            self._make_registry(dosage_frequency=0)
        with self.assertRaises(ValidationError):
            self._make_registry(dosage_duration=0)
        with self.assertRaises(ValidationError):
            # 2 doses/day declared but 3 explicit times — mismatch.
            self._make_registry(dosage_times="08:00, 14:00, 20:00")
        with self.assertRaises(ValidationError):
            self._make_registry(dosage_times="ośma rano, 20:00")

    def test_sign_requires_signature(self):
        """Непідписаний прийом: канвас порожній → ValidationError, не consent."""
        registry = self._make_registry()
        with self.assertRaises(ValidationError):
            registry.action_sign(ip_address="127.0.0.1", signature=None)
        self.assertFalse(registry.rodo_consent_id)

    # ------------------------------------------------------------------
    # 2. Consent gate + signature immutability (T1-K, art. 9(2)(a))
    # ------------------------------------------------------------------

    def test_activate_without_consent_blocked(self):
        registry = self._make_registry()
        with self.assertRaises(UserError):
            registry.action_activate()
        self.assertEqual(registry.state, "draft")
        self.assertFalse(registry.schedule_ids)

    def test_sign_records_consent_and_is_immutable(self):
        registry = self._make_registry()
        registry.action_sign(ip_address="10.0.0.7", signature=SIGNATURE_PNG)
        self.assertTrue(registry.signed_date)
        self.assertEqual(registry.signed_ip, "10.0.0.7")
        self.assertTrue(registry.rodo_consent_id)
        self.assertEqual(registry.rodo_consent_id.evidence_model, "camp.medication.registry")
        # Second sign attempt — consent is already recorded.
        with self.assertRaises(UserError):
            registry.action_sign(ip_address="10.0.0.7", signature=SIGNATURE_PNG)
        # Signed PNG is legal evidence — non-system user cannot replace it.
        with self.assertRaises(UserError):
            registry.with_user(self.user_medic).write({"parent_signature": SIGNATURE_PNG})

    # ------------------------------------------------------------------
    # 3. Grid generation (T2-K): 2×/day × 7 days → 14 rows
    # ------------------------------------------------------------------

    def test_activation_generates_full_grid(self):
        registry = self._sign_and_activate(self._make_registry())
        self.assertEqual(registry.state, "active")
        self.assertEqual(len(registry.schedule_ids), 14)
        self.assertTrue(all(s.status == "pending" for s in registry.schedule_ids))
        first_day = registry.schedule_ids.sorted("scheduled_time")[:2]
        self.assertEqual(
            [fields.Datetime.to_string(s.scheduled_time) for s in first_day],
            ["2026-07-21 08:00:00", "2026-07-21 20:00:00"],
        )

    # ------------------------------------------------------------------
    # 4. Kejs Tsybulko — critical course never issued → alert + SMS
    # ------------------------------------------------------------------

    def test_tsybulko_missed_critical_activity_and_sms(self):
        """Психіатричні ліки здано 21.07, 10 днів не видано → missed +
        mail.activity керівнику + SMS CRITICAL (без назви препарату)."""
        registry = self._sign_and_activate(
            self._make_registry(
                is_critical=True,
                dosage_frequency=1,
                dosage_duration=10,
                dosage_times="08:00",
            )
        )
        self.assertEqual(len(registry.schedule_ids), 10)

        with self._mock_sms() as mock_send:
            self.env["camp.medication.schedule"]._cron_mark_missed_and_alert()

        # All overdue doses flipped to missed and stamped alerted_at.
        self.assertTrue(all(s.status == "missed" for s in registry.schedule_ids))
        self.assertTrue(all(s.alerted_at for s in registry.schedule_ids))

        # ONE grouped activity thread for the kierownik (not 10 activities).
        alerts = self._missed_alerts(registry)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts.user_id, self.user_kierownik)

        # ONE SMS CRITICAL to the kierownik's mobile, art.9-clean body.
        self.assertEqual(mock_send.call_count, 1)
        call_kwargs = mock_send.call_args.kwargs
        self.assertEqual(call_kwargs["phone"], "+48500100200")
        self.assertEqual(call_kwargs["partner_id"], self.user_kierownik.partner_id.id)
        self.assertIn("Tsybulko", call_kwargs["body"])
        self.assertNotIn("Sertralina", call_kwargs["body"])

        # RODO art. 30: processing trail exists for this registry.
        trail = self.env["camp.admin.access.log"].search(
            [("medication_registry_id", "=", registry.id)]
        )
        self.assertTrue(trail)
        self.assertTrue(all(log.impersonated_role == "medication" for log in trail))

    def test_missed_noncritical_no_sms(self):
        registry = self._sign_and_activate(self._make_registry(is_critical=False))
        with self._mock_sms() as mock_send:
            self.env["camp.medication.schedule"]._cron_mark_missed_and_alert()
        self.assertTrue(self._missed_alerts(registry))
        mock_send.assert_not_called()

    def test_grace_hour_keeps_recent_dose_pending(self):
        """Доза, прострочена < MISSED_GRACE_HOURS, ще не missed."""
        registry = self._sign_and_activate(
            self._make_registry(received_date=fields.Datetime.now() + timedelta(days=1))
        )
        now = fields.Datetime.now()
        rows = registry.schedule_ids.sorted("scheduled_time")
        recent, overdue = rows[0], rows[1]
        recent.write({"scheduled_time": now - timedelta(minutes=30)})
        overdue.write({"scheduled_time": now - timedelta(hours=2)})
        with self._mock_sms():
            self.env["camp.medication.schedule"]._cron_mark_missed_and_alert()
        self.assertEqual(recent.status, "pending")
        self.assertEqual(overdue.status, "missed")

    # ------------------------------------------------------------------
    # 5. 24h escalation (T4-K)
    # ------------------------------------------------------------------

    def test_escalation_after_24h_unconfirmed(self):
        registry = self._sign_and_activate(self._make_registry(is_critical=False))
        with self._mock_sms():
            self.env["camp.medication.schedule"]._cron_mark_missed_and_alert()
        self.assertTrue(self._missed_alerts(registry))
        # Kierownik ignores the alert for >24h.
        registry.schedule_ids.write({"alerted_at": fields.Datetime.now() - timedelta(hours=25)})
        with self._mock_sms():
            self.env["camp.medication.schedule"]._cron_mark_missed_and_alert()
        self.assertTrue(all(s.escalated_at for s in registry.schedule_ids))
        escalations = self._escalation_alerts(registry)
        self.assertEqual(len(escalations), 1)
        self.assertEqual(escalations.user_id, self.user_kierownik)

    def test_no_escalation_when_kierownik_confirmed(self):
        registry = self._sign_and_activate(self._make_registry(is_critical=False))
        with self._mock_sms():
            self.env["camp.medication.schedule"]._cron_mark_missed_and_alert()
        # Kierownik confirms: the missed-dose activity is marked done (gone).
        self._missed_alerts(registry).unlink()
        registry.schedule_ids.write({"alerted_at": fields.Datetime.now() - timedelta(hours=25)})
        with self._mock_sms():
            self.env["camp.medication.schedule"]._cron_mark_missed_and_alert()
        # Escalation window is closed without a repeat alert.
        self.assertTrue(all(s.escalated_at for s in registry.schedule_ids))
        self.assertFalse(self._escalation_alerts(registry))

    # ------------------------------------------------------------------
    # 6. Scheme change (T2-K): pending regenerated, issued untouched
    # ------------------------------------------------------------------

    def test_scheme_change_regenerates_pending_keeps_issued(self):
        registry = self._sign_and_activate(
            self._make_registry(received_date=fields.Datetime.now() + timedelta(days=1))
        )
        self.assertEqual(len(registry.schedule_ids), 14)
        first = registry.schedule_ids.sorted("scheduled_time")[0]
        first.with_user(self.user_medic).action_issue()
        self.assertEqual(first.status, "issued")
        self.assertTrue(first.issued_time)

        # Medic changes the scheme 2 → 3 doses/day.
        registry.write({"dosage_frequency": 3, "dosage_times": "08:00, 14:00, 20:00"})

        # Issued row survived untouched — it is legal evidence.
        self.assertIn(first, registry.schedule_ids)
        self.assertEqual(first.status, "issued")
        # New grid: 7 days × 3 doses = 21 slots, minus the slot at-or-before
        # the issued cutoff (day 1, 08:00) → 20 pending + 1 issued.
        pending = registry.schedule_ids.filtered(lambda s: s.status == "pending")
        self.assertEqual(len(pending), 20)
        self.assertEqual(len(registry.schedule_ids), 21)
        self.assertTrue(
            all(s.scheduled_time > first.scheduled_time for s in pending),
            "Regenerated pending rows must all be after the issued cutoff",
        )
        day1_pending_hours = sorted(
            s.scheduled_time.hour
            for s in pending
            if s.scheduled_time.date() == first.scheduled_time.date()
        )
        self.assertEqual(day1_pending_hours, [14, 20])

    def test_issued_rows_cannot_be_deleted(self):
        registry = self._sign_and_activate(self._make_registry())
        first = registry.schedule_ids.sorted("scheduled_time")[0]
        first.with_user(self.user_medic).action_issue()
        with self.assertRaises(UserError):
            first.with_user(self.user_medic).unlink()

    # ------------------------------------------------------------------
    # 7. ACL + record rules (T6-K)
    # ------------------------------------------------------------------

    def test_acl_wychowawca_has_no_access(self):
        """Wychowawca: жодного ACL-рядка на обидві моделі → AccessError."""
        self._sign_and_activate(self._make_registry())
        Registry = self.env["camp.medication.registry"].with_user(self.user_wychowawca)
        Schedule = self.env["camp.medication.schedule"].with_user(self.user_wychowawca)
        with self.assertRaises(AccessError):
            Registry.search([])
        with self.assertRaises(AccessError):
            Schedule.search([])
        with self.assertRaises(AccessError):
            Registry.create(
                {
                    "participant_id": self.child.id,
                    "event_id": self.event.id,
                    "medication_name": "Should not be saved",
                }
            )

    def test_acl_medic_reads_and_writes_own_camp(self):
        registry = self._sign_and_activate(self._make_registry())
        found = (
            self.env["camp.medication.registry"]
            .with_user(self.user_medic)
            .search([("id", "=", registry.id)])
        )
        self.assertEqual(found, registry, "Medic must see the registry of own camp")
        self.assertEqual(
            found.medication_name,
            "Sertralina 50mg",
            "Medic holds group_medical_access → art.9 fields readable",
        )
        dose = registry.schedule_ids.sorted("scheduled_time")[0]
        dose.with_user(self.user_medic).write({"notes": "wydano przy śniadaniu"})
        self.assertEqual(dose.notes, "wydano przy śniadaniu")

    def test_record_rule_other_camp_medic_sees_nothing(self):
        self._sign_and_activate(self._make_registry())
        Registry = self.env["camp.medication.registry"].with_user(self.user_medic_other)
        Schedule = self.env["camp.medication.schedule"].with_user(self.user_medic_other)
        self.assertFalse(Registry.search([]), "Other-camp medic must see no registries")
        self.assertFalse(Schedule.search([]), "Other-camp medic must see no schedule rows")

    def test_kierownik_sees_own_camp_registry(self):
        registry = self._sign_and_activate(self._make_registry())
        found = (
            self.env["camp.medication.registry"]
            .with_user(self.user_kierownik)
            .search([("id", "=", registry.id)])
        )
        self.assertEqual(found, registry, "Kierownik (event.user_id) must see the registry")
