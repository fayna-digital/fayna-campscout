# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Reuse S1 пара 1 — keeper camp.analytics.snapshot несе семантику stats.

S1-4: total_capacity (єдине унікальне поле видаленої camp.stats.snapshot)
зберігається; S1-3: сценарій щоденного снапшота під тестом; write-лок
історичних фактів діє.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestAnalyticsSnapshot(TransactionCase):
    def test_snapshot_stores_capacity_and_locks(self):
        now = fields.Datetime.now()
        event = self.env["event.event"].create(
            {
                "name": "Oboz Snapshot QA",
                "date_begin": now + timedelta(days=3),
                "date_end": now + timedelta(days=10),
                "seats_limited": True,
                "seats_max": 42,
            }
        )
        snap = self.env["camp.analytics.snapshot"]._take_analytics_snapshot(
            event, fields.Date.today()
        )
        self.assertEqual(snap.total_capacity, 42, "seats_max must land in the snapshot")
        # ідемпотентність: повторний виклик того ж дня повертає той самий запис
        again = self.env["camp.analytics.snapshot"]._take_analytics_snapshot(
            event, fields.Date.today()
        )
        self.assertEqual(snap.id, again.id)
        # історичний факт незмінний (чистий browse — recordset із
        # _take_analytics_snapshot несе context snapshot_allow_write=True)
        clean = self.env["camp.analytics.snapshot"].browse(snap.id)
        with self.assertRaises(UserError):
            clean.write({"registered_count": 99})


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestDailyReportArchive(TransactionCase):
    """Reuse S1 пара 2: 7-річний retention-архів денних рапортів.

    У видаленого camp.journal метод був мертвий (без ir.cron); тут cron
    підключений у data/cron.xml, а логіка — під тестом.
    """

    def test_cron_archives_seven_year_old_reports(self):
        now = fields.Datetime.now()
        old_event = self.env["event.event"].create(
            {
                "name": "Oboz Archiwum QA",
                "date_begin": now - timedelta(days=8 * 365),
                "date_end": now - timedelta(days=8 * 365 - 10),
            }
        )
        fresh_event = self.env["event.event"].create(
            {
                "name": "Oboz Swiezy QA",
                "date_begin": now - timedelta(days=10),
                "date_end": now - timedelta(days=3),
            }
        )
        Report = self.env["camp.daily.report"]
        old_report = Report.create(
            {"event_id": old_event.id, "report_date": fields.Date.today() - timedelta(days=8 * 365)}
        )
        fresh_report = Report.create(
            {"event_id": fresh_event.id, "report_date": fields.Date.today() - timedelta(days=5)}
        )
        Report.cron_archive_old_reports()
        self.assertFalse(old_report.active, "8-річний рапорт мусить піти в архів")
        self.assertTrue(fresh_report.active, "свіжий рапорт лишається активним")


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestMenuDayKeeper(TransactionCase):
    """Reuse S1 пара 3: keeper camp.menu.day несе семантику legacy nutrition."""

    def _event(self):
        now = fields.Datetime.now()
        return self.env["event.event"].create(
            {
                "name": "Oboz Jadlospis QA",
                "date_begin": now + timedelta(days=1),
                "date_end": now + timedelta(days=10),
            }
        )

    def test_confirm_flow_and_diet_counts(self):
        event = self._event()
        menu = self.env["camp.menu.day"].create(
            {
                "event_id": event.id,
                "menu_date": fields.Date.today() + timedelta(days=2),
                "breakfast": "Owsianka",
                "vegetarian_count": 3,
            }
        )
        self.assertEqual(menu.state, "draft")
        menu.action_confirm()
        self.assertEqual(menu.state, "confirmed")
        with self.assertRaises(UserError):
            menu.action_confirm()  # повторне підтвердження заборонене
        menu.action_reset_to_draft()
        self.assertEqual(menu.state, "draft")
        with self.assertRaises(UserError):
            menu.vegan_count = -1  # лічильники не бувають від'ємні


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestDietProfileKeeper(TransactionCase):
    """Reuse S1 пара 4: keeper camp.diet.profile — унікальність на учасника."""

    def test_one_profile_per_participant(self):
        child = (
            self.env["camp.participant"]
            .sudo()
            .create(
                {
                    "first_name": "DietQA",
                    "last_name": "Testowa",
                }
            )
        )
        Profile = self.env["camp.diet.profile"].sudo()
        Profile.create({"participant_id": child.id})
        from odoo.exceptions import ValidationError as VErr

        with self.assertRaises(VErr):
            Profile.create({"participant_id": child.id})
