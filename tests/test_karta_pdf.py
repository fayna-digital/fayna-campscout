# Fayna CampScout — smoke tests for the Karta Kwalifikacyjna PDF report
# (§10 TZ_SPRINT — wzór 2026 Dz.U. 2026/704 / wzór 2021 Dz.U. 2021/1548).
#
# Renders the QWeb HTML for both wzor_version variants and asserts the
# version-specific pkt 9 wording is present. PDF binary itself is not
# rendered here (wkhtmltopdf is not guaranteed in the test container) —
# QWeb HTML is the layer where template errors surface.
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestKartaPdf(TransactionCase):
    """Smoke: report renders without exceptions for both wzór versions."""

    REPORT_REF = "fayna_camp_portal.report_karta_kwalifikacyjna"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(cls.env.context, tracking_disable=True, no_reset_password=True)
        )
        cls.parent = cls.env["res.partner"].create(
            {
                "name": "Anna Testowa",
                "street": "ul. Kaliska 45",
                "city": "Ostrów Wielkopolski",
                "zip": "63-400",
                "phone": "+48 600 100 200",
            }
        )
        cls.event = cls.env["event.event"].create(
            {
                "name": "Obóz Testowy Lato 2026",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-14 18:00:00",
            }
        )

        # wzór 2026 — structured pkt 9 + confirmed registration (event data path)
        cls.child_2026 = cls.env["camp.participant"].create(
            {
                "first_name": "Zofia",
                "last_name": "PDFowa",
                "birth_date": "2015-03-03",
                "pesel": "15230398765",
                "wzor_version": "2026",
                "parent_partner_id": cls.parent.id,
                "emergency_contact_1_name": "Anna Testowa",
                "emergency_contact_1_phone": "+48 600 100 200",
            }
        )
        cls.child_2026.sudo().write(
            {
                "allergy_insect_venom": True,
                "allergy_food": True,
                "motion_sickness": True,
                "wears_contact_lenses": True,
                "diet_vegetarian": True,
                "fear_of_heights": True,
                "hydrophobia": True,
                "medications": "Ventolin 100 µg — 2x dziennie",
                "chronic_conditions": "Astma oskrzelowa",
                "vacc_tetanus_year": "2023",
                "vacc_diphtheria_year": "2023",
            }
        )
        cls.env["event.registration"].create(
            {
                "event_id": cls.event.id,
                "partner_id": cls.parent.id,
                "participant_id": cls.child_2026.id,
                "state": "open",
            }
        )

        # wzór 2021 — legacy free-text pkt 9, NO registration (graceful path)
        cls.child_2021 = cls.env["camp.participant"].create(
            {
                "first_name": "Janek",
                "last_name": "Legacy",
                "birth_date": "2012-09-09",
                "wzor_version": "2021",
                "parent_partner_id": cls.parent.id,
            }
        )
        cls.child_2021.sudo().write(
            {
                "allergies": "Uczulony na orzechy",
                "medications": "Brak",
                "chronic_conditions": "Brak",
            }
        )

    def _render(self, participant):
        html, report_type = self.env["ir.actions.report"]._render_qweb_html(
            self.REPORT_REF, [participant.id]
        )
        self.assertEqual(report_type, "html")
        return html.decode("utf-8")

    def test_render_2026_smoke(self):
        """Wzór 2026 renders without exceptions and uses the new pkt 9 layout."""
        content = self._render(self.child_2026)
        self.assertIn("KARTA KWALIFIKACYJNA", content)
        # version marker — Dziennik Ustaw of the 2026 wzór
        self.assertIn("Dz.U. 2026 poz. 704", content)
        # new pkt 9 wording exists only in the 2026 variant
        self.assertIn("hydrofobia", content)
        self.assertIn("dieta\n                        niskokaloryczna", content.replace("\r", ""))
        # event data from the open registration made it into Section I
        self.assertIn("Obóz Testowy Lato 2026".split()[0][:3], content)  # 'Obó'
        self.assertIn("01.07.2026", content)
        self.assertIn("14.07.2026", content)
        # checked boxes for the structured flags
        self.assertIn("☒", content)

    def test_render_2021_smoke(self):
        """Wzór 2021 renders without exceptions, legacy pkt 9 text, no event."""
        content = self._render(self.child_2021)
        self.assertIn("KARTA KWALIFIKACYJNA", content)
        # version marker — Dziennik Ustaw of the 2021 wzór
        self.assertIn("Dz.U. 2021 poz. 1548", content)
        # legacy pkt 9 wording (old examples list)
        self.assertIn("jak znosi jazdę samochodem", content)
        # 2026-only wording must NOT leak into the 2021 layout
        self.assertNotIn("hydrofobia", content)
        # free-text medical data is rendered
        self.assertIn("Uczulony na orzechy", content)

    def test_render_both_in_one_batch(self):
        """Both versions in a single docids batch — t-foreach branch per record."""
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            self.REPORT_REF, [self.child_2026.id, self.child_2021.id]
        )
        content = html.decode("utf-8")
        self.assertIn("Dz.U. 2026 poz. 704", content)
        self.assertIn("Dz.U. 2021 poz. 1548", content)
