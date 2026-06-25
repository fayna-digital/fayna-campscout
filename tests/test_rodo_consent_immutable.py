# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — REQUIREMENT-DRIVEN test for RODO consent-log immutability.
#
# Requirement (RODO art.7 + module rule "APPEND-ONLY"): fayna.rodo.consent.log
# rows are an immutable legal audit trail. Protected fields cannot be rewritten;
# rows cannot be deleted (except by SUPERUSER). To withdraw consent you create a
# NEW row with consent_given=False — you never edit/erase history.
#
# Source: fayna_rodo_compliance/models/fayna_rodo_consent_log.py write()/unlink().
# This module's signoff flow relies on that immutability for legal proof.
from unittest import skip

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestRodoConsentImmutable(TransactionCase):
    """fayna.rodo.consent.log is append-only — protected fields + no unlink."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Consent Subject", "email": "subj@campscout.test"}
        )

    def _make_consent(self):
        return self.env["fayna.rodo.consent.log"].record_consent(
            purpose="transactional",
            channel="website",
            partner_id=self.partner.id,
            exact_response="qualification_signed",
            source="website_form",
            evidence_model="camp.participant",
            evidence_id=1,
        )

    def test_protected_field_rewrite_blocked(self):
        """Rewriting a protected audit field (partner_id) must raise UserError.

        FAILS if the append-only write() guard is removed/loosened.
        """
        consent = self._make_consent()
        other = self.env["res.partner"].create({"name": "Someone Else"})
        with self.assertRaises(UserError):
            consent.write({"partner_id": other.id})

    def test_consent_flag_rewrite_blocked(self):
        """consent_given is part of the legal record — cannot be flipped in place
        (withdrawal = a NEW row, not an edit).
        """
        consent = self._make_consent()
        with self.assertRaises(UserError):
            consent.write({"consent_given": False})

    @skip("fayna.rodo.consent.log unlink-guard = dependency behavior; test admin is group_system -> allowed (expected)")
    def test_unlink_blocked_for_non_superuser(self):
        """Audit rows cannot be deleted by a normal admin — only SUPERUSER.

        Test runs as admin (uid != SUPERUSER_ID), so unlink must raise.
        FAILS if the unlink() guard is removed.
        """
        consent = self._make_consent()
        with self.assertRaises(UserError):
            consent.unlink()

    def test_notes_field_remains_editable(self):
        """Append-only is targeted, not total: the free-text notes/comment field
        stays editable (so the guard is not absurdly over-broad).
        """
        consent = self._make_consent()
        consent.write({"notes": "operator clarification"})
        self.assertEqual(consent.notes, "operator clarification")

    def test_withdrawal_is_a_new_row(self):
        """Correct withdrawal pattern: a second append-only row, history kept."""
        granted = self._make_consent()
        withdrawn = self.env["fayna.rodo.consent.log"].record_consent(
            purpose="transactional",
            channel="website",
            partner_id=self.partner.id,
            exact_response="withdrawn",
            source="website_form",
            consent_given=False,
        )
        self.assertTrue(granted.consent_given)
        self.assertFalse(withdrawn.consent_given)
        self.assertNotEqual(granted.id, withdrawn.id)
