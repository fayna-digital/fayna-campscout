# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Parent role — Dodatek 4a (Zgoda na wizerunek) image-consent sign flow.

Corrected-TZ acceptance point (audit 2026-07-01): the image-consent signing
flow (RODO wizerunek, purpose=child_photo) had ZERO test coverage. This test
proves the round-trip: parent signs → RODO consent-log row created + state,
IP, timestamp and signature stored on the participant; re-settable (withdraw
produces a NEW log row, immutable audit trail); invalid decision rejected.

Perspective: independent QA engineer verifying the parent cabinet against the
corrected TZ, not the code author.
"""
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestParentImageConsent(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent_partner = cls.env["res.partner"].create(
            {"name": "QA Parent ImgConsent", "email": "qa_imgconsent@campscout.test"}
        )
        child_partner = cls.env["res.partner"].create({"name": "QA Child ImgConsent"})
        cls.participant = cls.env["camp.participant"].create(
            {
                "partner_id": child_partner.id,
                "parent_partner_id": cls.parent_partner.id,
                "first_name": "Zosia",
                "last_name": "ImgConsentTest",
            }
        )

    def _consent_logs(self):
        """All RODO child_photo consent-log rows tied to this participant."""
        return self.env["fayna.rodo.consent.log"].search(
            [
                ("evidence_model", "=", "camp.participant"),
                ("evidence_id", "=", self.participant.id),
                ("purpose", "=", "child_photo"),
            ]
        )

    def test_sign_yes_stores_state_ip_signature_and_rodo_log(self):
        """decision='yes' → state/ip/date/signature on participant + RODO log row."""
        self.participant.sign_image_consent(
            "yes", ip_address="10.0.0.5", signature=b"c2lnbmF0dXJl"
        )
        p = self.participant
        self.assertEqual(p.image_consent_state, "yes")
        self.assertEqual(p.image_consent_signed_ip, "10.0.0.5")
        self.assertTrue(p.image_consent_signed_date, "signed_date must be stamped")
        self.assertTrue(p.image_consent_signature, "signature must be stored")
        self.assertTrue(p.image_consent_rodo_id, "RODO consent-log must be linked")

        log = p.image_consent_rodo_id
        self.assertEqual(log.purpose, "child_photo")
        self.assertTrue(log.consent_given, "yes → consent_given=True")
        self.assertEqual(log.legal_basis, "consent")
        self.assertEqual(log.partner_id, self.parent_partner)
        self.assertEqual(self._consent_logs(), log, "exactly one log row after first sign")

    def test_sign_no_records_withdrawal(self):
        """decision='no' → state='no' and RODO log consent_given=False."""
        self.participant.sign_image_consent("no", ip_address="10.0.0.9")
        self.assertEqual(self.participant.image_consent_state, "no")
        self.assertFalse(self.participant.image_consent_rodo_id.consent_given)

    def test_invalid_decision_raises(self):
        """Anything other than yes/no is rejected — no silent bad state."""
        with self.assertRaises(ValidationError):
            self.participant.sign_image_consent("maybe")

    def test_resettable_appends_new_immutable_log_row(self):
        """Toggling yes→no keeps an immutable trail: 2 log rows, latest wins."""
        self.participant.sign_image_consent("yes", ip_address="10.0.0.5")
        self.participant.sign_image_consent("no", ip_address="10.0.0.5")
        logs = self._consent_logs()
        self.assertEqual(len(logs), 2, "each sign appends a NEW log row (audit trail)")
        self.assertEqual(self.participant.image_consent_state, "no")
        self.assertEqual(
            self.participant.image_consent_rodo_id,
            logs.sorted("id")[-1],
            "participant points at the latest consent-log row",
        )
