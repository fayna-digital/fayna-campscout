# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Photo-story publish gate — RODO wizerunek (Dodatek 4a) enforcement.

Corrected-TZ acceptance point (audit 2026-07-01): publishing a story that
tags a child MUST be blocked unless that child has signed image consent
('yes'). Prevents a child's image reaching parents' portals without consent
(RODO art. 6/9 + prawo do wizerunku, art. 81 pr. aut.).

Perspective: independent QA engineer, not the code author.
"""

import datetime

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestStoryPhotoConsentGate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.event = cls.env["event.event"].create(
            {
                "name": "QA PhotoGate Camp",
                "date_begin": datetime.datetime(2026, 7, 1, 9, 0),
                "date_end": datetime.datetime(2026, 7, 10, 18, 0),
                "date_tz": "Europe/Warsaw",
            }
        )
        cls.parent = cls.env["res.partner"].create({"name": "QA PhotoGate Parent"})
        child = cls.env["res.partner"].create({"name": "QA PhotoGate Child"})
        cls.participant = cls.env["camp.participant"].create(
            {
                "partner_id": child.id,
                "parent_partner_id": cls.parent.id,
                "first_name": "Ola",
                "last_name": "PhotoGate",
            }
        )

    def _make_story(self, tagged=True, public=True):
        return self.env["camp.story"].create(
            {
                "event_id": self.event.id,
                "date": datetime.date(2026, 7, 5),
                "title": "Dzień 5 — wycieczka",
                "content": "<p>Great day at camp.</p>",
                "public": public,
                "tagged_participant_ids": [(6, 0, [self.participant.id] if tagged else [])],
            }
        )

    def test_publish_blocked_when_tagged_child_has_no_consent(self):
        """Default image_consent_state='pending' → publish must raise + stay draft."""
        story = self._make_story()
        with self.assertRaises(ValidationError):
            story.action_publish()
        self.assertEqual(story.state, "draft", "blocked story must remain draft")

    def test_publish_allowed_after_consent_signed(self):
        story = self._make_story()
        self.participant.sign_image_consent("yes", ip_address="1.2.3.4")
        story.action_publish()
        self.assertEqual(story.state, "published")

    def test_publish_blocked_if_consent_withdrawn(self):
        story = self._make_story()
        self.participant.sign_image_consent("no", ip_address="1.2.3.4")
        with self.assertRaises(ValidationError):
            story.action_publish()

    def test_non_public_story_bypasses_gate(self):
        """Non-public story is not shown to parents → no image publication."""
        story = self._make_story(public=False)
        story.action_publish()
        self.assertEqual(story.state, "published")

    def test_untagged_story_publishes(self):
        """No tagged children → nothing to consent-check → publishes."""
        story = self._make_story(tagged=False)
        story.action_publish()
        self.assertEqual(story.state, "published")
