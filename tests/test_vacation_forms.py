# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""F-WIZ-6 (R6) — full MEN catalogue of wypoczynek forms.

Dz.U. wypoczynek forms the organizer must be able to declare: kolonia,
obóz, biwak, zimowisko, półkolonia, zielona szkoła (+ 'inne' escape hatch).
The wizard and camp.kuratorium.notification (Zgłoszenie Wypoczynku,
Załącznik 1 MEN) both declare this catalogue; they describe the same legal
classification, so the two selections must not drift apart. NB: as of R6
the wizard value is not yet carried into the notification on create —
tracked as R6.1 in TZ §8.
"""

from odoo.tests.common import TransactionCase, tagged

MEN_FORMS = {
    "kolonia",
    "oboz",
    "biwak",
    "zimowisko",
    "polkolonia",
    "zielona_szkola",
    "inne",
}


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestVacationForms(TransactionCase):
    def _keys(self, model):
        return {key for key, _label in self.env[model]._fields["vacation_form"].selection}

    def test_men_catalogue_complete(self):
        """WHEN the organizer opens 'Forma wypoczynku' THEN all MEN forms
        (incl. półkolonia and zielona szkoła) are selectable."""
        model_keys = self._keys("camp.kuratorium.notification")
        self.assertTrue(
            model_keys >= MEN_FORMS,
            f"kuratorium notification vacation_form misses: {MEN_FORMS - model_keys}",
        )

    def test_wizard_and_model_selections_in_sync(self):
        """Wizard and kuratorium-notification catalogues must be identical —
        same legal MEN classification, drift would let the two forms tell
        the organizer different stories."""
        self.assertEqual(
            self._keys("camp.create.wizard"),
            self._keys("camp.kuratorium.notification"),
            "vacation_form selections drifted between wizard and kuratorium notification",
        )
