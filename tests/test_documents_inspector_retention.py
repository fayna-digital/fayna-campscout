# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""F-DOC-3 (send to inspector) + F-DOC-4 (retention-matrix cron).

Requirement (docs/TZ.md):
  [F-DOC-3] WHEN the user selects documents with checkboxes and clicks
  «Надіслати інспектору», THEN the system creates a mail.compose.message with
  the selected attachments and logs the action in the camp chatter.

  [F-DOC-4] WHEN the retention deadline passes, THEN the daily cron flags the
  record as to_erase, pauses when there is an active claim (court case), and
  logs the erasure decision (append-only, RODO art.30). Real deletion is a
  separate wizard-confirmed step (first deletions 2033) — the cron only flags
  and logs, it never deletes.

This test drives the model layer directly (TransactionCase):
  1. F-DOC-3: teczka + event attachments are collected; sending creates a
     mail.compose.message with the selected attachments and logs to chatter;
     attachments outside the teczka are rejected.
  2. F-DOC-4: the retention cron flags an overdue participant, pauses one with
     an active claim, and writes append-only log entries that cannot be deleted.
"""

from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestSendDocumentsToInspector(TransactionCase):
    """F-DOC-3 — «Надіслати інспектору»."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.event = (
            cls.env["event.event"]
            .sudo()
            .create(
                {
                    "name": "QA Inspector Event",
                    "date_begin": "2026-07-10 08:00:00",
                    "date_end": "2026-07-17 18:00:00",
                    "seats_limited": True,
                    "seats_max": 30,
                }
            )
        )
        cls.teczka = cls.env["camp.teczka.ko"].sudo().create({"event_id": cls.event.id})
        # Set the delegatura e-mail so the send action has a recipient.
        cls.teczka.sudo().write({"delegatura_email": "delegatura@kuratorium.test"})

    def _make_attachment(self, name, res_model, res_id):
        return (
            self.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": name,
                    "type": "binary",
                    "datas": "JVBERi0xLjQ=",  # tiny placeholder
                    "mimetype": "application/pdf",
                    "res_model": res_model,
                    "res_id": res_id,
                }
            )
        )

    def test_collect_event_attachments(self):
        """Teczka + event attachments are both collected."""
        teczka_att = self._make_attachment("Teczka Doc.pdf", "camp.teczka.ko", self.teczka.id)
        event_att = self._make_attachment("Event Doc.pdf", "event.event", self.event.id)

        collected = self.teczka._collect_event_attachments()

        self.assertIn(teczka_att, collected)
        self.assertIn(event_att, collected)

    def test_send_creates_compose_and_logs(self):
        """Sending creates a mail.compose.message with attachments + chatter log."""
        att = self._make_attachment("Inspector Doc.pdf", "camp.teczka.ko", self.teczka.id)

        result = self.teczka.action_send_documents_to_inspector([att.id])

        self.assertEqual(result["res_model"], "mail.compose.message")
        compose = self.env["mail.compose.message"].sudo().browse(result["res_id"])
        self.assertTrue(compose, "A mail.compose.message must be created.")
        self.assertIn(att, compose.attachment_ids)
        # The recipient is carried in the compose action context (default_email_to);
        # mail.compose.message has no stored ``email_to`` column in Odoo 17.
        self.assertEqual(
            result["context"]["default_email_to"],
            "delegatura@kuratorium.test",
        )

        # Chatter log written.
        messages = self.teczka.message_ids
        self.assertTrue(
            any("F-DOC-3" in (m.body or "") for m in messages),
            "The send action must be logged in the camp chatter.",
        )

    def test_send_rejects_foreign_attachment(self):
        """Attachments outside this teczka/event are rejected."""
        foreign = self._make_attachment("Foreign.pdf", "event.event", 999999)

        with self.assertRaises(UserError):
            self.teczka.action_send_documents_to_inspector([foreign.id])


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestRetentionCron(TransactionCase):
    """F-DOC-4 — retention-matrix cron (flags + logs, never deletes)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.engine = cls.env["camp.retention.engine"]

    def _make_participant(self, overdue=False):
        """Create a participant.

        ``retention_until`` is a stored computed field (participant.py) that
        resolves to ``max(qualification_signed_date, last event end) + 7 years``.
        To make a participant "overdue" we set ``qualification_signed_date`` to a
        date >7 years in the past so the compute naturally yields a past
        ``retention_until`` — writing the computed field directly would be
        fragile (it is recomputed on dependency change).
        """
        vals = {
            "first_name": "QA Retention",
            "last_name": "Child",
            "birth_date": "2015-01-01",
        }
        if overdue:
            vals["qualification_signed_date"] = str(date.today() - timedelta(days=365 * 8))
        return self.env["camp.participant"].sudo().create(vals)

    def test_cron_flags_overdue_participant(self):
        """An overdue participant is flagged and logged."""
        overdue = self._make_participant(overdue=True)

        count = self.engine._cron_retention_scan()

        self.assertGreaterEqual(count, 1)
        log = (
            self.env["camp.retention.log"]
            .sudo()
            .search(
                [
                    ("res_model", "=", "camp.participant"),
                    ("res_id", "=", overdue.id),
                    ("action", "=", "flagged"),
                ]
            )
        )
        self.assertTrue(log, "An overdue participant must be flagged in the log.")

    def test_cron_pauses_on_active_claim(self):
        """A participant with an active incident card is paused, not flagged."""
        overdue = self._make_participant(overdue=True)
        # Create an active (confirmed) incident card referencing this participant.
        # ``event_id`` is required on the card; it need not be linked to the
        # participant — the pause heuristic matches on participant_id.
        claim_event = (
            self.env["event.event"]
            .sudo()
            .create(
                {
                    "name": "QA Claim Event",
                    "date_begin": "2026-07-10 08:00:00",
                    "date_end": "2026-07-17 18:00:00",
                }
            )
        )
        self.env["camp.incident.card"].sudo().create(
            {
                "event_id": claim_event.id,
                "participant_id": overdue.id,
                "state": "confirmed",
                "incident_datetime": "2026-07-10 10:00:00",
                "miejsce": "Stok narciarski — trasa niebieska",
            }
        )

        self.engine._cron_retention_scan()

        paused = (
            self.env["camp.retention.log"]
            .sudo()
            .search(
                [
                    ("res_model", "=", "camp.participant"),
                    ("res_id", "=", overdue.id),
                    ("action", "=", "paused"),
                ]
            )
        )
        self.assertTrue(
            paused,
            "A participant with an active claim must be paused, not flagged.",
        )

    def test_log_is_append_only(self):
        """Retention log entries cannot be deleted (RODO art.30)."""
        log = (
            self.env["camp.retention.log"]
            .sudo()
            .create(
                {
                    "res_model": "camp.participant",
                    "res_id": 1,
                    "action": "flagged",
                    "category": "participant",
                }
            )
        )
        with self.assertRaises(UserError):
            log.unlink()
