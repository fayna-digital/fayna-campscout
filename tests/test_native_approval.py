# Fayna CampScout — Native-state approval workflow tests (TZ §6, ADR-13)
#
# Principle §0: approval state lives on event.event — NO mirror model.
# Wizard creates event immediately as unpublished (website_published=False)
# + camp_approval_state='pending_approval'.
# website_published=False is the single gate that blocks website sales.
# Organizator approves → website_published=True; rejects → stays unpublished.
#
# Test coverage:
#   1. After wizard submit: event exists, website_published=False (not on website).
#   2. After action_approve: website_published=True, camp_approval_state='approved'.
#   3. After action_reject (from pending): camp_approval_state='rejected', unpublished.
#   4. Idempotency: double approve raises UserError.
#   5. Non-organizator cannot approve (UserError).
#   6. action_reject requires rejection_reason (UserError if empty).
#   7. action_submit_for_approval: draft → pending_approval.
#   8. Submit from non-draft raises UserError.

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal", "approval")
class TestNativeApproval(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # --- Groups ---
        cls.group_organizator = cls.env.ref("fayna_camp_portal.group_camp_organizator")
        cls.group_kierownik = cls.env.ref("fayna_camp_portal.group_camp_kierownik")

        # --- Organizator user ---
        cls.organizator_user = cls.env["res.users"].create(
            {
                "name": "Test Organizator",
                "login": "test_organizator_approval@campscout.test",
                "groups_id": [(6, 0, [cls.group_organizator.id])],
            }
        )

        # --- Kierownik user ---
        cls.kierownik_user = cls.env["res.users"].create(
            {
                "name": "Test Kierownik",
                "login": "test_kierownik_approval@campscout.test",
                "groups_id": [(6, 0, [cls.group_kierownik.id])],
            }
        )

    def _make_pending_event(self):
        """Create event as wizard would: pending_approval + unpublished."""
        event = self.env["event.event"].sudo().create(
            {
                "name": "Test Turnus Approval 2026",
                "date_begin": "2026-07-10 08:00:00",
                "date_end": "2026-07-24 18:00:00",
                "seats_limited": True,
                "seats_max": 30,
                "website_published": False,
                "camp_approval_state": "pending_approval",
            }
        )
        return event

    # ------------------------------------------------------------------
    # Test 1: wizard output — event exists but is unpublished + pending
    # ------------------------------------------------------------------

    def test_wizard_creates_unpublished_pending_event(self):
        """After wizard submission the event must be unpublished and pending approval.
        website_published=False is the single gate that blocks website sales.
        """
        event = self._make_pending_event()
        self.assertEqual(
            event.camp_approval_state,
            "pending_approval",
            "Event must be in pending_approval state after wizard submit.",
        )
        self.assertFalse(
            event.website_published,
            "Event must NOT be published on website after wizard submit.",
        )

    # ------------------------------------------------------------------
    # Test 2: approve → published
    # ------------------------------------------------------------------

    def test_approve_publishes_event(self):
        """action_approve by organizator must publish the event."""
        event = self._make_pending_event()
        event.with_user(self.organizator_user).action_approve()

        self.assertEqual(event.camp_approval_state, "approved")
        self.assertTrue(
            event.website_published,
            "Event must be website_published=True after approve.",
        )
        self.assertEqual(
            event.approved_by_id,
            self.organizator_user,
            "approved_by_id must be set to the organizator user.",
        )
        self.assertIsNotNone(event.approved_date, "approved_date must be set.")

    # ------------------------------------------------------------------
    # Test 3: reject → rejected + stays unpublished
    # ------------------------------------------------------------------

    def test_reject_keeps_event_unpublished(self):
        """action_reject must set state=rejected and keep event unpublished."""
        event = self._make_pending_event()
        event.write({"rejection_reason": "Brak dokumentacji MEN."})
        event.with_user(self.organizator_user).action_reject()

        self.assertEqual(event.camp_approval_state, "rejected")
        self.assertFalse(
            event.website_published,
            "Rejected event must NOT be published on website.",
        )

    # ------------------------------------------------------------------
    # Test 4: idempotency — double approve raises UserError
    # ------------------------------------------------------------------

    def test_double_approve_raises_user_error(self):
        """Approving an already-approved event must raise UserError."""
        event = self._make_pending_event()
        event.with_user(self.organizator_user).action_approve()
        with self.assertRaises(UserError):
            event.with_user(self.organizator_user).action_approve()

    # ------------------------------------------------------------------
    # Test 5: non-organizator cannot approve
    # ------------------------------------------------------------------

    def test_non_organizator_cannot_approve(self):
        """Kierownik calling action_approve must get UserError."""
        event = self._make_pending_event()
        with self.assertRaises(UserError):
            event.with_user(self.kierownik_user).action_approve()

    # ------------------------------------------------------------------
    # Test 6: reject without reason raises UserError
    # ------------------------------------------------------------------

    def test_reject_without_reason_raises_user_error(self):
        """action_reject without rejection_reason must raise UserError."""
        event = self._make_pending_event()
        # rejection_reason is empty by default
        with self.assertRaises(UserError):
            event.with_user(self.organizator_user).action_reject()

    # ------------------------------------------------------------------
    # Test 7: submit from draft → pending_approval
    # ------------------------------------------------------------------

    def test_submit_for_approval_transitions_state(self):
        """action_submit_for_approval must move state draft→pending_approval."""
        event = self.env["event.event"].sudo().create(
            {
                "name": "Draft Camp Submit Test",
                "date_begin": "2026-08-01 08:00:00",
                "date_end": "2026-08-14 18:00:00",
                "camp_approval_state": "draft",
                "website_published": False,
            }
        )
        event.with_user(self.kierownik_user).action_submit_for_approval()
        self.assertEqual(event.camp_approval_state, "pending_approval")
        self.assertFalse(event.website_published)

    # ------------------------------------------------------------------
    # Test 8: submit from non-draft raises UserError
    # ------------------------------------------------------------------

    def test_submit_from_pending_raises_user_error(self):
        """action_submit_for_approval on pending_approval event must raise UserError."""
        event = self._make_pending_event()
        with self.assertRaises(UserError):
            event.with_user(self.kierownik_user).action_submit_for_approval()
