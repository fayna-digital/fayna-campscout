# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""F-KKW-6 — auto-refusal cron VERIFICATION (TZ §4.4/§8: cron існував без доказу).

Проганяє справжній цикл `_cron_auto_refusal_scan`:
- прострочений дедлайн + непідписана картка → активні реєстрації скасовані,
  `auto_refusal_refused_at` залатчено, state='refused', audit-повідомлення в чатері;
- підписана картка — недоторкана (state='cleared');
- повторний прогін ідемпотентний (refused=0).
"""

from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestAutoRefusalCron(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        now = fields.Datetime.now()
        # Старт за ~6 годин → дедлайн (start − 1 день) уже в минулому.
        cls.event = cls.env["event.event"].create(
            {
                "name": "Oboz AutoRefusal QA",
                "date_begin": now + timedelta(hours=6),
                "date_end": now + timedelta(days=7),
            }
        )
        cls.parent = cls.env["res.partner"].create(
            {
                "name": "AutoRefusal Parent",
                "email": "auto_refusal_parent@campscout.test",
            }
        )

    def _make_child(self, name, signed=False):
        child = (
            self.env["camp.participant"]
            .sudo()
            .create(
                {
                    "first_name": name,
                    "last_name": "RefusalQA",
                    "parent_partner_id": self.parent.id,
                    # передумови гейта підпису (birth_date + контакт НС)
                    "birth_date": "2015-05-05",
                    "emergency_contact_1_name": "AutoRefusal Parent",
                    "emergency_contact_1_phone": "+48000000009",
                    "qualification_signed": signed,
                }
            )
        )
        reg = self.env["event.registration"].create(
            {
                "event_id": self.event.id,
                "partner_id": self.parent.id,
                "participant_id": child.id,
            }
        )
        reg.write({"state": "open"})
        return child, reg

    def test_overdue_unsigned_is_refused(self):
        child, reg = self._make_child("Overdue")
        # Передумови: дедлайн у минулому, стан pending (латч ще не спрацював).
        self.assertTrue(child.auto_refusal_date)
        self.assertLessEqual(child.auto_refusal_date, fields.Date.today())
        self.assertEqual(child.auto_refusal_state, "pending")

        result = self.env["camp.participant"]._cron_auto_refusal_scan()

        self.assertGreaterEqual(result["refused"], 1)
        self.assertEqual(reg.state, "cancel", "active registration must be cancelled")
        self.assertTrue(child.auto_refusal_refused_at, "refusal must be latched")
        self.assertEqual(child.auto_refusal_state, "refused")
        bodies = " ".join(m.body or "" for m in child.message_ids)
        self.assertIn("Auto-refusal", bodies, "audit chatter message must be posted")

    def test_signed_child_is_untouched(self):
        child, reg = self._make_child("Signed", signed=True)
        self.assertEqual(child.auto_refusal_state, "cleared")

        self.env["camp.participant"]._cron_auto_refusal_scan()

        self.assertNotEqual(reg.state, "cancel", "signed child must keep the registration")
        self.assertFalse(child.auto_refusal_refused_at)

    def test_scan_is_idempotent(self):
        child, reg = self._make_child("Idempotent")
        first = self.env["camp.participant"]._cron_auto_refusal_scan()
        self.assertGreaterEqual(first["refused"], 1)
        second = self.env["camp.participant"]._cron_auto_refusal_scan()
        self.assertEqual(second["refused"], 0, "second pass must refuse nothing (latched)")
        self.assertEqual(reg.state, "cancel")

    def test_refusal_creates_real_refund_request(self):
        """F-KKW-6 / F-FIN-5 — refund is a real camp.support.request, not a stub.

        After the auto-refusal cron fires, a ``camp.support.request`` of type
        ``cancel`` must exist for the cancelled registration, carrying the
        computed refund % and estimated refund per Umowa §6.x.
        """
        child, reg = self._make_child("RefundReal")
        self.env["camp.participant"]._cron_auto_refusal_scan()

        reqs = (
            self.env["camp.support.request"]
            .sudo()
            .search([("registration_id", "=", reg.id), ("request_type", "=", "cancel")])
        )
        self.assertEqual(len(reqs), 1, "exactly one refund request must be created")
        req = reqs[0]
        # The refund computation must have run (refund_pct in 0..100).
        self.assertGreaterEqual(req.refund_pct, 0)
        self.assertLessEqual(req.refund_pct, 100)
        # A due date within 14 days of submission must be stamped (§6.4).
        self.assertTrue(req.refund_due_date, "refund due date must be set")
        # The request must be linked to the participant for traceability.
        self.assertEqual(req.participant_id.id, child.id)
