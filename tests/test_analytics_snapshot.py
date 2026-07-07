# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Reuse S1 пара 1 — keeper camp.analytics.snapshot несе семантику stats.

S1-4: total_capacity (єдине унікальне поле видаленої camp.stats.snapshot)
зберігається; S1-3: сценарій щоденного снапшота під тестом; write-лок
історичних фактів діє.
"""

import importlib.util
import os
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger
from psycopg2 import IntegrityError


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
    """Reuse S1 пара 4: keeper camp.diet.profile — унікальність на учасника.

    Унікальність — це SQL EXCLUDE-констрейнт (diet_profile_participant_unique),
    успадкований keeper'ом ще ДО цієї пари; видалена camp.participant.diet мала
    той самий інваріант через _sql_constraints UNIQUE(participant_id). Порушення
    EXCLUDE-констрейнту спливає як psycopg2.IntegrityError (не ValidationError) —
    той самий idiom, що й у власних тестах Odoo (test_ir_actions.py).
    """

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
        with (
            self.assertRaises(IntegrityError),
            mute_logger("odoo.sql_db"),
            self.env.cr.savepoint(),
        ):
            Profile.create({"participant_id": child.id})


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestDietProfileMigrationLossless(TransactionCase):
    """Reuse S1 пара 4 — синтетичний lossless-тест реальної міграції.

    camp.participant.diet видалена з реєстру (п.4 рецепта), тому "легасі" рядки
    відтворюються сирим SQL за тією ж схемою, яку Odoo будував для видаленої
    моделі (id/participant_id/dietary_restrictions/notes + m2m-таблиця
    алергенів), а перенесення прогоняється через РЕАЛЬНИЙ файл
    migrations/17.0.4.1.5/post-migrate.py::migrate() — не копію логіки.
    """

    def _load_migrate_module(self):
        path = os.path.join(
            get_module_path("fayna_camp_portal"),
            "migrations",
            "17.0.4.1.5",
            "post-migrate.py",
        )
        spec = importlib.util.spec_from_file_location("s1p4_diet_post_migrate", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _create_legacy_tables(self):
        # INC-215: dietary_restrictions/notes на видаленій camp.participant.diet
        # мали translate=True [ПЕРЕВІРЕНО: git show b8768c0^:models/nutrition.py:664-680]
        # → у реальній БД це jsonb, НЕ text. Тест мусить будувати ту саму схему,
        # яку Odoo реально створював для цієї моделі — інакше зелений тест на
        # синтетичному TEXT ховає READ-бік бага (CONCAT_WS по jsonb дає сирий
        # JSON-рядок замість читабельного тексту).
        cr = self.env.cr
        cr.execute(
            """
            CREATE TABLE camp_participant_diet (
                id SERIAL PRIMARY KEY,
                participant_id INTEGER NOT NULL,
                dietary_restrictions JSONB,
                notes JSONB,
                create_uid INTEGER,
                create_date TIMESTAMP,
                write_uid INTEGER,
                write_date TIMESTAMP
            )
            """
        )
        cr.execute(
            """
            CREATE TABLE camp_participant_diet_allergen_rel (
                diet_id INTEGER NOT NULL,
                allergen_id INTEGER NOT NULL,
                PRIMARY KEY (diet_id, allergen_id)
            )
            """
        )

    def test_migration_moves_rows_1to1_and_is_idempotent(self):
        Participant = self.env["camp.participant"].sudo()
        Allergen = self.env["camp.allergen"].sudo()

        p1 = Participant.create({"first_name": "Legacy1", "last_name": "Dietowa"})
        p2 = Participant.create({"first_name": "Legacy2", "last_name": "Dietowa"})
        gluten = Allergen.create({"name": "QA Gluten S1P4", "code": "qa_s1p4_gluten"})
        milk = Allergen.create({"name": "QA Milk S1P4", "code": "qa_s1p4_milk"})
        # міграція читає camp_participant сирим SQL — ORM-кеш (display_name
        # тощо) мусить бути на диску ДО цього, інакше cr.execute бачить NULL.
        self.env.flush_all()

        p3 = Participant.create({"first_name": "Legacy3", "last_name": "Dietowa"})
        self.env.flush_all()

        self._create_legacy_tables()
        cr = self.env.cr
        uid = self.env.uid
        # p1/p2 — легасі-поля лише en_US (типовий випадок); jsonb_build_object
        # відтворює РІВНО ту форму, яку дає звичайний ORM-запис (не голий текст).
        cr.execute(
            """
            INSERT INTO camp_participant_diet
                (participant_id, dietary_restrictions, notes,
                 create_uid, create_date, write_uid, write_date)
            VALUES (%s, jsonb_build_object('en_US', %s::text),
                    jsonb_build_object('en_US', %s::text), %s, now(), %s, now())
            RETURNING id
            """,
            (p1.id, "vegan, bez wieprzowiny", "silna reakcja na orzechy", uid, uid),
        )
        diet1_id = cr.fetchone()[0]
        cr.execute(
            """
            INSERT INTO camp_participant_diet
                (participant_id, dietary_restrictions, notes,
                 create_uid, create_date, write_uid, write_date)
            VALUES (%s, jsonb_build_object('en_US', %s::text), NULL, %s, now(), %s, now())
            """,
            (p2.id, "bezglutenowa", uid, uid),
        )
        # p3 — обидва поля мають pl_PL, notes НЕ має en_US взагалі (перевіряє
        # COALESCE en_US↔pl_PL фолбек в обидва боки, не лише щасливий шлях).
        cr.execute(
            """
            INSERT INTO camp_participant_diet
                (participant_id, dietary_restrictions, notes,
                 create_uid, create_date, write_uid, write_date)
            VALUES (%s, jsonb_build_object('en_US', %s::text, 'pl_PL', %s::text),
                    jsonb_build_object('pl_PL', %s::text), %s, now(), %s, now())
            """,
            (p3.id, "no pork", "bez wieprzowiny", "silna reakcja", uid, uid),
        )
        cr.execute(
            """
            INSERT INTO camp_participant_diet_allergen_rel (diet_id, allergen_id)
            VALUES (%s, %s), (%s, %s)
            """,
            (diet1_id, gluten.id, diet1_id, milk.id),
        )

        migration = self._load_migrate_module()
        migration.migrate(cr, "17.0.4.1.5")

        Profile = self.env["camp.diet.profile"].sudo()
        profile1 = Profile.search([("participant_id", "=", p1.id)])
        profile2 = Profile.search([("participant_id", "=", p2.id)])
        profile3 = Profile.search([("participant_id", "=", p3.id)])

        # 1:1 — кожен легасі-рядок дав рівно один keeper-профіль
        self.assertEqual(len(profile1), 1, "p1 мусить отримати рівно один профіль")
        self.assertEqual(len(profile2), 1, "p2 мусить отримати рівно один профіль")
        self.assertEqual(len(profile3), 1, "p3 мусить отримати рівно один профіль")

        # lossless — вільний текст обох полів зберігся в notes, БЕЗ jsonb-сміття
        # (INC-215: раніше тут був подвійно загорнутий JSON-рядок)
        self.assertIn("vegan, bez wieprzowiny", profile1.notes)
        self.assertIn("silna reakcja na orzechy", profile1.notes)
        self.assertNotIn("{", profile1.notes, "READ-бік не має лишати сирий JSON у тексті")
        self.assertEqual(profile2.notes, "bezglutenowa")

        # pl_PL-переклад зберігається окремо, не губиться при розпакуванні en_US
        cr.execute(
            "SELECT notes ->> 'en_US', notes ->> 'pl_PL' FROM camp_diet_profile WHERE id = %s",
            (profile3.id,),
        )
        en_val, pl_val = cr.fetchone()
        self.assertEqual(en_val, "no pork\n\nsilna reakcja")
        self.assertEqual(pl_val, "bez wieprzowiny\n\nsilna reakcja")
        self.assertNotIn("{", en_val)
        self.assertNotIn("{", pl_val)

        # алергени перенесені 1:1 через m2m
        self.assertEqual(set(profile1.allergen_ids.ids), {gluten.id, milk.id})
        self.assertFalse(profile2.allergen_ids)

        # display_name перенесений (не NULL після сирого SQL-інсерту)
        self.assertEqual(profile1.display_name, p1.display_name)

        # ідемпотентність: повторний прогін не дублює ні профілі, ні алергени
        migration.migrate(cr, "17.0.4.1.5")
        self.assertEqual(Profile.search_count([("participant_id", "=", p1.id)]), 1)
        self.assertEqual(Profile.search_count([("participant_id", "=", p2.id)]), 1)
        self.assertEqual(Profile.search_count([("participant_id", "=", p3.id)]), 1)
        self.assertEqual(set(profile1.allergen_ids.ids), {gluten.id, milk.id})


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestDietProfileRepairMigration(TransactionCase):
    """INC-215 repair (migrations/17.0.4.1.8) — лагодить camp_diet_profile.notes,
    зіпсовані ОРИГІНАЛЬНОЮ багованою 17.0.4.1.5 (jsonb легасі-колонки
    конкатенувались як сирий текст → подвійно загорнутий JSON). Staging уже
    прогнав багований .5 (INC-215 register) — ця міграція мусить безпечно
    полагодити такий уражений стан, використовуючи ще присутню легасі-таблицю
    як джерело істини."""

    def _load_repair_module(self):
        path = os.path.join(
            get_module_path("fayna_camp_portal"),
            "migrations",
            "17.0.4.1.8",
            "post-migrate.py",
        )
        spec = importlib.util.spec_from_file_location("s1p4_diet_repair", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _create_legacy_table(self):
        cr = self.env.cr
        cr.execute(
            """
            CREATE TABLE camp_participant_diet (
                id SERIAL PRIMARY KEY,
                participant_id INTEGER NOT NULL,
                dietary_restrictions JSONB,
                notes JSONB,
                create_uid INTEGER,
                create_date TIMESTAMP,
                write_uid INTEGER,
                write_date TIMESTAMP
            )
            """
        )

    def test_repair_heals_double_wrapped_json_from_buggy_migration(self):
        Participant = self.env["camp.participant"].sudo()
        Profile = self.env["camp.diet.profile"].sudo()
        cr = self.env.cr
        uid = self.env.uid

        participant = Participant.create({"first_name": "Corrupted", "last_name": "Dietowa"})
        self.env.flush_all()

        self._create_legacy_table()
        cr.execute(
            """
            INSERT INTO camp_participant_diet
                (participant_id, dietary_restrictions, notes,
                 create_uid, create_date, write_uid, write_date)
            VALUES (%s, jsonb_build_object('en_US', %s::text),
                    jsonb_build_object('en_US', %s::text), %s, now(), %s, now())
            """,
            (participant.id, "vegan, bez wieprzowiny", "silna reakcja na orzechy", uid, uid),
        )

        # keeper-профіль УРАЖЕНИЙ старою версією .5 — відтворюємо РІВНО той
        # дефект з INC-215: CONCAT_WS по jsonb дав сирий JSON-рядок, загорнутий
        # ще раз jsonb_build_object на write-боці.
        profile = Profile.create({"participant_id": participant.id})
        corrupted_text = (
            '{"en_US": "vegan, bez wieprzowiny"}\n\n{"en_US": "silna reakcja na orzechy"}'
        )
        cr.execute(
            "UPDATE camp_diet_profile SET notes = jsonb_build_object('en_US', %s::text) WHERE id = %s",
            (corrupted_text, profile.id),
        )
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertIn("{", profile.notes, "фікстура мусить відтворювати САМЕ уражений стан")

        repair = self._load_repair_module()
        repair.migrate(cr, "17.0.4.1.8")
        self.env.invalidate_all()

        self.assertNotIn("{", profile.notes, "repair мусить прибрати подвійне загортання")
        self.assertIn("vegan, bez wieprzowiny", profile.notes)
        self.assertIn("silna reakcja na orzechy", profile.notes)

        # ідемпотентність: повторний прогін на вже полагодженому — без змін
        repair.migrate(cr, "17.0.4.1.8")
        self.env.invalidate_all()
        self.assertNotIn("{", profile.notes)

    def test_repair_skips_healthy_rows_when_legacy_present(self):
        Participant = self.env["camp.participant"].sudo()
        Profile = self.env["camp.diet.profile"].sudo()
        cr = self.env.cr

        participant = Participant.create({"first_name": "Healthy", "last_name": "Dietowa"})
        self.env.flush_all()

        self._create_legacy_table()
        profile = Profile.create({"participant_id": participant.id, "notes": "already fine"})

        repair = self._load_repair_module()
        repair.migrate(cr, "17.0.4.1.8")
        self.env.invalidate_all()

        self.assertEqual(profile.notes, "already fine", "repair не чіпає вже здорові рядки")

    def test_repair_noop_when_legacy_table_absent(self):
        # легасі-таблиці немає в цій транзакції (гіпотетичний прогін на іншій
        # БД) — repair мусить тихо повернутись, без винятку.
        repair = self._load_repair_module()
        repair.migrate(self.env.cr, "17.0.4.1.8")
