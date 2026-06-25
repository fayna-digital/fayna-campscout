# Copyright 2026 Fayna Digital — Volodymyr Shevchenko
"""Tests — Dziennik Zajęć PDF report (Załącznik 5 Rozp. MEN 30.03.2016).

Smoke test: the report action referenced by FaynaCampDziennik.action_submit
(``fayna_camp_portal.action_report_dziennik``) exists and renders QWeb HTML
without exceptions, with all 4 wzór sections populated.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestDziennikPdf(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.event = cls.env["event.event"].create(
            {
                "name": "Obóz Testowy — Turnus I 2026",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-14 18:00:00",
            }
        )
        cls.participant = cls.env["camp.participant"].create(
            {
                "first_name": "Jan",
                "last_name": "Dziennikowy",
                "birth_date": "2015-03-10",
            }
        )
        cls.kierownik = cls.env["camp.staff"].create(
            {
                "event_id": cls.event.id,
                "name": "Adam Kierowniczy",
                "role": "leader",
                "date_from": "2026-07-01",
                "date_to": "2026-07-14",
            }
        )
        cls.wychowawca = cls.env["camp.staff"].create(
            {
                "event_id": cls.event.id,
                "name": "Maria Wychowawcza",
                "role": "counselor",
                "date_from": "2026-07-01",
                "date_to": "2026-07-14",
            }
        )
        cls.dziennik = cls.env["fayna.camp.dziennik"].create(
            {
                "event_id": cls.event.id,
                "group_name": "A",
                "date_start": "2026-07-01",
                "date_end": "2026-07-14",
                "kierownik_id": cls.kierownik.id,
                "wychowawca_ids": [(6, 0, [cls.wychowawca.id])],
                "participant_ids": [(6, 0, [cls.participant.id])],
            }
        )
        # Section 2 — weekly plan line
        cls.env["fayna.camp.dziennik.plan.line"].create(
            {
                "dziennik_id": cls.dziennik.id,
                "week_number": 1,
                "task": "Zorganizować grę terenową",
                "deadline": "2026-07-05",
                "responsible_id": cls.wychowawca.id,
                "completion_note": "Wykonano zgodnie z planem",
            }
        )
        # Section 3 — activity entry
        cls.env["fayna.camp.dziennik.activity"].create(
            {
                "dziennik_id": cls.dziennik.id,
                "datetime": "2026-07-02 10:00:00",
                "content": "Gra terenowa w lesie — orientacja w terenie",
                "notes": "Dzieci aktywne, brak trudności",
            }
        )
        # Section 4 — note
        cls.env["fayna.camp.dziennik.note"].create(
            {
                "dziennik_id": cls.dziennik.id,
                "date": "2026-07-03",
                "content": "Zalecenie: więcej przerw na wodę w upalne dni",
            }
        )

    def test_report_action_exists(self):
        """The xml id used by action_submit must resolve to a qweb-pdf action."""
        report = self.env.ref("fayna_camp_portal.action_report_dziennik")
        self.assertEqual(report._name, "ir.actions.report")
        self.assertEqual(report.model, "fayna.camp.dziennik")
        self.assertEqual(report.report_type, "qweb-pdf")
        self.assertEqual(report.report_name, "fayna_camp_portal.report_dziennik")

    def test_render_qweb_html_smoke(self):
        """Render the dziennik report HTML without exceptions; check content."""
        html, render_type = self.env["ir.actions.report"]._render_qweb_html(
            "fayna_camp_portal.action_report_dziennik", self.dziennik.ids
        )
        self.assertEqual(render_type, "html")
        content = html.decode("utf-8")
        # title of the official form
        self.assertIn("DZIENNIK ZAJĘĆ", content)
        # Section 1 — participant surname + birth year
        self.assertIn("Dziennikowy", content)
        self.assertIn("2015", content)
        # nagłówek — kierownik / wychowawca / grupa
        self.assertIn("Adam Kierowniczy", content)
        self.assertIn("Maria Wychowawcza", content)
        # Section 2 — plan line
        self.assertIn("Zorganizować grę terenową", content)
        # Section 3 — activity content
        self.assertIn("Gra terenowa w lesie", content)
        # Section 4 — note
        self.assertIn("więcej przerw na wodę", content)
        # dd-mm-rrrr header dates
        self.assertIn("01-07-2026", content)
        self.assertIn("14-07-2026", content)
