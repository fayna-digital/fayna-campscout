# Copyright 2026 Fayna Digital — Volodymyr Shevchenko
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Tests — §11 Karta Wypadku (camp.incident.card) + §12 Rejestr Wypadków
(camp.incident.register), TZ_SPRINT_2026-06-10.

Covers:
  * full 16-point card creation (official wzór fields),
  * register auto-aggregation: confirmed-only, chronological, auto Lp.,
  * card freeze after confirmation (write-guard, załączniki/notes exempt),
  * register lock after turnus closing (write/unlink guard, admin unlock).
"""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger
from psycopg2 import IntegrityError


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestIncidentCard(TransactionCase):
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
                "last_name": "Testowy",
                "birth_date": "2015-03-10",
            }
        )
        cls.participant2 = cls.env["camp.participant"].create(
            {
                "first_name": "Anna",
                "last_name": "Testowa",
                "birth_date": "2014-09-21",
            }
        )

    def _card_vals(self, **overrides):
        """Full 16-point Karta Wypadku values (official wzór)."""
        vals = {
            # pkt 1
            "placowka_name": "Obóz CampScout — Ośrodek Testowy (pieczęć)",
            # pkt 2
            "participant_id": self.participant.id,
            "participant_address": "ul. Testowa 1, 63-400 Ostrów Wielkopolski",
            "group_class": "Grupa Młodsza A",
            # linkage
            "event_id": self.event.id,
            # pkt 3
            "czynnosc": "Gra terenowa — bieg po lesie",
            # pkt 4
            "bhp_rodzaj": "Instruktaż wstępny BHP wypoczynku",
            "bhp_kiedy": "2026-07-01",
            "bhp_przez_kogo": "Kierownik wypoczynku",
            "bhp_czas_trwania": "45 minut",
            # pkt 5
            "zbadany_przez_lekarza": "tak",
            "data_ostatniego_badania": "2026-06-15",
            "przeciwwskazania": "nie",
            # pkt 6
            "incident_datetime": "2026-07-05 11:30:00",
            "miejsce": "Polana leśna przy ośrodku",
            # pkt 7
            "uraz_rodzaj": "Skręcenie",
            "uraz_umiejscowienie": "Staw skokowy prawy",
            # pkt 8
            "niezdolny_do_uczestnictwa": "tak",
            "niezdolnosc_czas": "3 dni",
            # pkt 9
            "opis_wypadku": (
                "Podczas gry terenowej dziecko potknęło się o korzeń "
                "i skręciło prawą kostkę. Przyczyna: nierówne podłoże."
            ),
            # pkt 10
            "osoba_nadzoru": "Maria Wychowawczyni",
            # pkt 11
            "nadzor_obecny": "tak",
            # pkt 12
            "pierwsza_pomoc_godzina": "2026-07-05 11:33:00",
            # pkt 13
            "swiadkowie": "Piotr Świadek, ul. Leśna 2, Ostrów Wlkp.",
            # pkt 14
            "srodki_zapobiegawcze": "Oznaczenie trasy gry, dodatkowy obchód terenu",
            # pkt 15
            "komisja_sklad": "Maria Wychowawczyni\nAdam Komisyjny",
            "kierownik_placowki": "Jan Kierowniczy",
            # pkt 16
            "zalaczniki_wykaz": "1. Oświadczenie świadka\n2. Zdjęcia miejsca zdarzenia",
        }
        vals.update(overrides)
        return vals

    # ------------------------------------------------------------------
    # Card — creation with all 16 points
    # ------------------------------------------------------------------

    def test_card_creation_full_16_points(self):
        card = self.env["camp.incident.card"].create(self._card_vals())
        self.assertEqual(card.state, "draft")
        # pkt 2 related birth date comes from the participant
        self.assertEqual(str(card.participant_birth_date), "2015-03-10")
        # all wzór points hold their values
        self.assertTrue(card.placowka_name)  # 1
        self.assertEqual(card.group_class, "Grupa Młodsza A")  # 2
        self.assertIn("Gra terenowa", card.czynnosc)  # 3
        self.assertEqual(card.bhp_przez_kogo, "Kierownik wypoczynku")  # 4
        self.assertEqual(card.zbadany_przez_lekarza, "tak")  # 5
        self.assertEqual(card.przeciwwskazania, "nie")  # 5
        self.assertEqual(card.miejsce, "Polana leśna przy ośrodku")  # 6
        self.assertEqual(card.uraz_umiejscowienie, "Staw skokowy prawy")  # 7
        self.assertEqual(card.niezdolnosc_czas, "3 dni")  # 8
        self.assertIn("korzeń", card.opis_wypadku)  # 9
        self.assertEqual(card.osoba_nadzoru, "Maria Wychowawczyni")  # 10
        self.assertEqual(card.nadzor_obecny, "tak")  # 11
        self.assertTrue(card.pierwsza_pomoc_godzina)  # 12
        self.assertIn("Piotr Świadek", card.swiadkowie)  # 13
        self.assertIn("Oznaczenie trasy", card.srodki_zapobiegawcze)  # 14
        self.assertEqual(card.kierownik_placowki, "Jan Kierowniczy")  # 15
        self.assertIn("Oświadczenie świadka", card.zalaczniki_wykaz)  # 16
        self.assertIn("Jan Testowy", card.display_name)

    def test_card_confirm_requires_opis_and_nadzor(self):
        card = self.env["camp.incident.card"].create(
            self._card_vals(opis_wypadku=False, osoba_nadzoru=False)
        )
        with self.assertRaises(UserError):
            card.action_confirm()
        self.assertEqual(card.state, "draft")

    # ------------------------------------------------------------------
    # Card — freeze after confirmation
    # ------------------------------------------------------------------

    def test_card_frozen_after_confirm(self):
        card = self.env["camp.incident.card"].create(self._card_vals())
        card.action_confirm()
        self.assertEqual(card.state, "confirmed")
        # frozen field → UserError
        with self.assertRaises(UserError):
            card.write({"miejsce": "Inne miejsce"})
        with self.assertRaises(UserError):
            card.write({"opis_wypadku": "Zmieniony opis"})
        # un-confirm via state is also blocked
        with self.assertRaises(UserError):
            card.write({"state": "draft"})
        # załączniki (pkt 16) + notes stay editable
        card.write({"zalaczniki_wykaz": "3. Dokumentacja medyczna"})
        card.write({"notes": "Uwaga wewnętrzna po zatwierdzeniu"})
        self.assertEqual(card.notes, "Uwaga wewnętrzna po zatwierdzeniu")
        # double confirm blocked
        with self.assertRaises(UserError):
            card.action_confirm()
        # confirmed card cannot be deleted
        with self.assertRaises(UserError):
            card.unlink()

    def test_draft_card_unlink_allowed(self):
        card = self.env["camp.incident.card"].create(self._card_vals())
        card.unlink()
        self.assertFalse(card.exists())

    # ------------------------------------------------------------------
    # Register — chronological aggregation + auto Lp.
    # ------------------------------------------------------------------

    def test_register_aggregates_confirmed_chronologically(self):
        Card = self.env["camp.incident.card"]
        # created out of chronological order on purpose
        card_late = Card.create(
            self._card_vals(
                incident_datetime="2026-07-10 16:00:00",
                participant_id=self.participant2.id,
            )
        )
        card_early = Card.create(self._card_vals(incident_datetime="2026-07-03 09:00:00"))
        card_mid = Card.create(
            self._card_vals(
                incident_datetime="2026-07-07 12:00:00",
                participant_id=self.participant2.id,
            )
        )
        card_draft = Card.create(self._card_vals(incident_datetime="2026-07-02 08:00:00"))

        (card_late + card_early + card_mid).action_confirm()
        # card_draft stays draft → must NOT appear in the register

        register = self.env["camp.incident.register"].create({"event_id": self.event.id})
        self.assertEqual(register.line_count, 3)
        self.assertEqual(
            register.line_ids.ids,
            [card_early.id, card_mid.id, card_late.id],
            "Register lines must be chronological by incident_datetime",
        )
        self.assertNotIn(card_draft.id, register.line_ids.ids)
        # auto Lp. follows chronological position (confirmed cards only)
        self.assertEqual(card_early.register_lp, 1)
        self.assertEqual(card_mid.register_lp, 2)
        self.assertEqual(card_late.register_lp, 3)
        self.assertEqual(card_draft.register_lp, 0)
        self.assertIn(self.event.name, register.display_name)

    def test_register_unique_per_event(self):
        self.env["camp.incident.register"].create({"event_id": self.event.id})
        with (
            mute_logger("odoo.sql_db"),
            self.assertRaises(IntegrityError),
            self.env.cr.savepoint(),
        ):
            self.env["camp.incident.register"].create({"event_id": self.event.id})

    # ------------------------------------------------------------------
    # Register — lock after turnus closing
    # ------------------------------------------------------------------

    def test_register_locked_after_event_close(self):
        card = self.env["camp.incident.card"].create(self._card_vals())
        card.action_confirm()
        register = self.env["camp.incident.register"].create({"event_id": self.event.id})

        register.action_lock()
        self.assertTrue(register.locked)

        # locked register is immutable
        other_event = self.env["event.event"].create(
            {
                "name": "Inny turnus",
                "date_begin": "2026-08-01 08:00:00",
                "date_end": "2026-08-14 18:00:00",
            }
        )
        with self.assertRaises(UserError):
            register.write({"event_id": other_event.id})
        # ... and cannot be deleted
        with self.assertRaises(UserError):
            register.unlink()

        # cards keep rendering through the computed lines even when locked
        self.assertEqual(register.line_count, 1)

        # admin (test env user has group_system) may unlock
        register.action_unlock()
        self.assertFalse(register.locked)

    def test_register_unlock_denied_for_non_admin(self):
        register = self.env["camp.incident.register"].create({"event_id": self.event.id})
        register.action_lock()
        kierownik_group = self.env.ref("fayna_camp_portal.group_camp_kierownik")
        kierownik = self.env["res.users"].create(
            {
                "name": "Kierownik Testowy",
                "login": "kierownik_incident@campscout.test",
                "groups_id": [(6, 0, [self.env.ref("base.group_user").id, kierownik_group.id])],
            }
        )
        with self.assertRaises(UserError):
            register.with_user(kierownik).action_unlock()
        self.assertTrue(register.locked)
