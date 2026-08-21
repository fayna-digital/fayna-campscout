# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — JS UI tour runner (OCA review).
#
# OCA review flags the absence of JS UI tours. This HttpCase drives the real
# kiosk shell (OWL client action "camp_kiosk", TZ §4) through a headless
# browser via @odoo/tour. The tour itself lives in
# static/src/js/kiosk_tour.js and asserts that:
#   1. the kiosk header renders its title,
#   2. the tile grid loads at least one action tile from /camp/kiosk/layout,
#   3. the PL/UA language switcher is present.
#
# The test user carries group_camp_kierownik so the layout controller returns
# a non-empty tile grid (controllers/kiosk.py:_TILES_BY_GROUP).
from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestKioskUiTour(HttpCase):
    """Run the kiosk UI tour in a real browser session."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.kiosk_user = cls.env["res.users"].create(
            {
                "name": "QA Kiosk Kierownik",
                "login": "qa_kiosk_kierownik@campscout.test",
                "password": "QaKiosk-1234!",
                "groups_id": [
                    (
                        6,
                        0,
                        [cls.env.ref("fayna_camp_portal.group_camp_kierownik").id],
                    )
                ],
            }
        )

    def test_kiosk_tour_runs(self):
        """The kiosk shell renders header, tiles and the PL/UA switcher."""
        self.start_tour(
            "/web#action=fayna_camp_portal.camp_kiosk_action",
            "fayna_camp_portal.kiosk_tour",
            login="qa_kiosk_kierownik@campscout.test",
        )
