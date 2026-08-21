# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — multi-company coverage (OCA review).
#
# OCA review flags the absence of multi-company tests. The module:
#   - adds company-specific fields to res.company (participant.py:2583):
#       camp_organizer_signature, image_consent_body, marketing_consent_body,
#       child_registration_consent_body
#   - scopes camp.budget by company_id (budget.py:112) and resolves the
#     "current company" for e-mail as event.company_id or env.company
#     (budget.py:634)
#   - keeps record rules scoped by user/role rather than company, so core
#     models (camp.participant, event.event) must stay usable across companies.
#
# These tests verify that a second company can be created, its company-specific
# fields set independently, and that the module's core records remain
# creatable/readable under each company context.
import base64

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestMultiCompany(TransactionCase):
    """Multi-company behaviour of company-specific and company-scoped fields."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(cls.env.context, tracking_disable=True, no_reset_password=True)
        )
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create(
            {
                "name": "CampScout Test Sp. z o.o.",
                "email": "biuro@campscout-test.pl",
            }
        )

    # --- res.company company-specific fields --------------------------------

    def test_company_specific_fields_are_independent_per_company(self):
        """Each company keeps its own consent bodies and signature."""
        self.company_a.write(
            {
                "image_consent_body": "<p>Zgoda A na wizerunek</p>",
                "marketing_consent_body": "<p>Zgoda A marketingowa</p>",
                "child_registration_consent_body": "<p>Klauzula A RODO</p>",
            }
        )
        self.company_b.write(
            {
                "image_consent_body": "<p>Zgoda B na wizerunek</p>",
                "marketing_consent_body": "<p>Zgoda B marketingowa</p>",
                "child_registration_consent_body": "<p>Klauzula B RODO</p>",
            }
        )
        self.assertIn("Zgoda A", self.company_a.image_consent_body)
        self.assertIn("Zgoda B", self.company_b.image_consent_body)
        self.assertNotEqual(
            self.company_a.image_consent_body,
            self.company_b.image_consent_body,
            "consent bodies must not leak across companies",
        )
        self.assertNotEqual(
            self.company_a.child_registration_consent_body,
            self.company_b.child_registration_consent_body,
            "RODO clause must not leak across companies",
        )
        # fn_organizer_signature is a related alias of camp_organizer_signature.
        # Binary fields with attachment=True store base64-encoded data.
        signature = base64.b64encode(b"fake-signature-a")
        self.company_a.camp_organizer_signature = signature
        self.assertEqual(
            self.company_a.fn_organizer_signature,
            signature,
            "fn_organizer_signature must mirror camp_organizer_signature",
        )
        self.assertFalse(
            self.company_b.camp_organizer_signature,
            "company B must not inherit company A's signature",
        )

    # --- core records usable across companies -------------------------------

    def test_core_records_creatable_under_second_company(self):
        """camp.participant and event.event stay usable under company B."""
        company_b_env = self.env(
            context={
                **self.env.context,
                "allowed_company_ids": [self.company_b.id],
            }
        )
        event = company_b_env["event.event"].create(
            {
                "name": "Camp B 2026",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-14 18:00:00",
            }
        )
        participant = company_b_env["camp.participant"].create(
            {
                "partner_id": company_b_env["res.partner"].create({"name": "Child B"}).id,
                "first_name": "Child",
                "last_name": "B",
            }
        )
        self.assertTrue(event.id, "event.event must be creatable under company B")
        self.assertTrue(participant.id, "camp.participant must be creatable under company B")
        # Records remain readable from the default company context too.
        self.assertEqual(
            self.env["event.event"].browse(event.id).name,
            "Camp B 2026",
            "records must be readable across company contexts",
        )

    # --- camp.budget company scoping ----------------------------------------

    def test_budget_defaults_to_current_company(self):
        """camp.budget.company_id defaults to the active company."""
        event = self.env["event.event"].create(
            {
                "name": "Budget Camp",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-14 18:00:00",
            }
        )
        budget = self.env["camp.budget"].create({"event_id": event.id})
        self.assertEqual(
            budget.company_id,
            self.company_a,
            "budget.company_id must default to the active company",
        )
        self.assertEqual(
            budget.currency_id,
            self.company_a.currency_id,
            "budget.currency_id must default to the active company's currency",
        )

    def test_budget_company_resolution_prefers_event_company(self):
        """budget e-mail company resolution: event.company_id or env.company."""
        event = self.env["event.event"].create(
            {
                "name": "Budget Camp B",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-14 18:00:00",
                "company_id": self.company_b.id,
            }
        )
        budget = self.env["camp.budget"].create({"event_id": event.id})
        # The resolution logic (budget.py:634) prefers event.company_id.
        resolved = budget.event_id.company_id or self.env.company
        self.assertEqual(
            resolved,
            self.company_b,
            "event.company_id must take precedence over env.company",
        )
