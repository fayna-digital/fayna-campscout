# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""F-WIZ-7 — high-risk camps (ski / water → licensed instructor + insurance).

Requirement (docs/TZ.md [F-WIZ-7]):
  WHEN activity-type of event ∈ [ski, water], THEN the system marks the event
  as high-risk, creates an instructor vacancy with required license-cert and
  required insurance attachment, and the event has boolean `is_high_risk` and
  insurance fields.
  IF activity-type ∉ [ski, water], THEN high-risk fields are not needed.
  WHEN a user creates a high-risk event (ski/water), THEN the system requires
  an insurance attachment and a licensed instructor before the event is
  approved; IF insurance or license is missing, THEN approval is blocked.

This test drives the model layer directly (TransactionCase):
  1. A camp program whose activities include a high-risk activity (ski) is
     detected as high-risk; a program without one is not.
  2. Submitting a high-risk camp for approval auto-creates an instructor vacancy.
  3. Approving a high-risk camp WITHOUT insurance + instructor vacancy is blocked.
  4. Approving a high-risk camp WITH insurance + instructor vacancy succeeds.
"""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestHighRiskCamps(TransactionCase):
    """F-WIZ-7: high-risk detection + approval gate."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.organizator = cls.env["res.users"].create(
            {
                "name": "QA HighRisk Organizator",
                "login": "qa_highrisk_org@campscout.test",
                "password": "QaHighRisk-1234!",
                "groups_id": [
                    (
                        6,
                        0,
                        [cls.env.ref("fayna_camp_portal.group_camp_organizator").id],
                    )
                ],
            }
        )
        # High-risk activity (ski) and a normal activity.
        cls.activity_ski = (
            cls.env["camp.activity"].sudo().create({"name": "Narciarstwo", "is_high_risk": True})
        )
        cls.activity_archery = (
            cls.env["camp.activity"].sudo().create({"name": "Łucznictwo", "is_high_risk": False})
        )

    def _make_camp_product(self, name, activities):
        """Create a camp program product linked to the given activities."""
        return (
            self.env["product.template"]
            .sudo()
            .create(
                {
                    "name": name,
                    "is_camp_program": True,
                    "list_price": 0.0,
                    "type": "service",
                    "camp_activities_ids": [(6, 0, activities.ids)],
                }
            )
        )

    def _make_event(self, product, state="draft"):
        """Create an event linked to the given camp program."""
        return (
            self.env["event.event"]
            .sudo()
            .create(
                {
                    "name": f"QA HighRisk Event — {product.name}",
                    "date_begin": "2026-07-10 08:00:00",
                    "date_end": "2026-07-17 18:00:00",
                    "seats_limited": True,
                    "seats_max": 30,
                    "website_published": False,
                    "camp_approval_state": state,
                    "camp_program_id": product.id,
                }
            )
        )

    def test_high_risk_detection(self):
        """A program with a high-risk activity is flagged; one without is not."""
        high_risk_product = self._make_camp_product("QA Ski Camp", self.activity_ski)
        normal_product = self._make_camp_product("QA Archery Camp", self.activity_archery)

        high_risk_event = self._make_event(high_risk_product)
        normal_event = self._make_event(normal_product)

        self.assertTrue(
            high_risk_event.is_high_risk,
            "An event whose program includes a high-risk activity must be high-risk.",
        )
        self.assertTrue(
            high_risk_event.insurance_required,
            "A high-risk event must require insurance.",
        )
        self.assertFalse(
            normal_event.is_high_risk,
            "An event without a high-risk activity must NOT be high-risk.",
        )
        self.assertFalse(
            normal_event.insurance_required,
            "A non-high-risk event must not require insurance.",
        )

    def test_submit_auto_creates_instructor_vacancy(self):
        """Submitting a high-risk camp for approval creates an instructor vacancy."""
        product = self._make_camp_product("QA Ski Camp Submit", self.activity_ski)
        event = self._make_event(product)

        event.action_submit_for_approval()

        instructor_vacancies = event.staff_vacancy_ids.filtered(lambda v: v.role == "instruktor")
        self.assertTrue(
            instructor_vacancies,
            "Submitting a high-risk camp must auto-create an instructor vacancy.",
        )
        self.assertEqual(
            event.camp_approval_state,
            "pending_approval",
            "The event must move to pending_approval after submission.",
        )

    def test_approve_blocked_without_insurance_and_instructor(self):
        """A high-risk camp without insurance + instructor vacancy cannot be approved."""
        product = self._make_camp_product("QA Ski Camp Blocked", self.activity_ski)
        event = self._make_event(product, state="pending_approval")

        with self.assertRaises(UserError):
            event.with_user(self.organizator).action_approve()

        self.assertEqual(
            event.camp_approval_state,
            "pending_approval",
            "Approval must remain blocked while high-risk requirements are unmet.",
        )

    def test_approve_succeeds_with_insurance_and_instructor(self):
        """A high-risk camp with insurance + instructor vacancy can be approved."""
        product = self._make_camp_product("QA Ski Camp Approved", self.activity_ski)
        event = self._make_event(product, state="pending_approval")

        # Add the required insurance attachment.
        insurance = (
            self.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": "QA Insurance Policy.pdf",
                    "datas": "JVBERi0xLjQ=",  # tiny placeholder
                    "mimetype": "application/pdf",
                }
            )
        )
        event.sudo().write({"insurance_attachment_id": insurance.id})
        # Add the required licensed-instructor vacancy.
        self.env["camp.staff.vacancy"].sudo().create(
            {
                "event_id": event.id,
                "role": "instruktor",
                "name": "Wakat instruktor (high-risk)",
                "created_reason": "F-WIZ-7 test",
            }
        )

        event.with_user(self.organizator).action_approve()

        self.assertEqual(
            event.camp_approval_state,
            "approved",
            "A high-risk camp with insurance + instructor vacancy must be approvable.",
        )
        self.assertTrue(
            event.website_published,
            "Approval must publish the high-risk event.",
        )
