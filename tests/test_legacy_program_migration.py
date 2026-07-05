# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Reuse S1 пара 5 — lossless synthetic test for the legacy camp.program
(+camp.program.activity) → camp.program.structured (+day+activity.line)
migration.

Docker-харнес завжди робить свіжий ``-i`` install (немає ``camp_program``
таблиці взагалі — модель видалена з коду), тому migrations/17.0.4.1.5/
post-migrate.py НІКОЛИ природно не запускається тут (post-migrate виконується
лише на реальному ``-u`` апгрейді існуючої інсталяції). Щоб довести коректність
міграції без живих staging-даних (ssh заблоковано), цей тест:

1. СТВОРЮЄ ad-hoc "легасі" таблиці (``camp_program``, ``camp_program_activity``)
   через сирий SQL — так, як вони існували б на реальній БД до цього PR
   (DDL у Postgres транзакційний, тому таблиці зникають разом з rollback'ом
   транзакції тесту — жодного сліду не лишається).
2. Вставляє синтетичні рядки, що імітують дві історичні "програми" (Plan A
   і Plan B) з дочірньою активністю кожна.
3. Імпортує ТОЙ САМИЙ файл, що лежить у migrations/17.0.4.1.5/post-migrate.py
   (через importlib — ім'я теки з крапками не є валідним Python-пакетом),
   і викликає migrate(cr, "17.0.4.1.5") напряму через реальний cr — без
   sudo-обходу, без мокання ORM.
4. Доводить: keeper (camp.program.structured/day/activity.line) отримав усі
   поля 1:1 (S1-4); повторний виклик migrate() НЕ дублює рядки (ir_model_data
   мітки); і transplant-спроможність (state-machine на дні) реально працює.
"""

import importlib.util
from datetime import timedelta

from odoo import fields
from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged


def _load_migrate():
    """Load migrate(cr, version) straight from migrations/17.0.4.1.5/post-migrate.py."""
    module_path = get_module_path("fayna_camp_portal")
    script_path = f"{module_path}/migrations/17.0.4.1.5/post-migrate.py"
    spec = importlib.util.spec_from_file_location("reuse_s1p5_post_migrate", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.migrate


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestLegacyProgramMigration(TransactionCase):
    """Reuse S1 пара 5: lossless + idempotent migration + transplanted behavior."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.event = cls.env["event.event"].create(
            {
                "name": "Obóz Migracja QA",
                "date_begin": "2026-08-01 08:00:00",
                "date_end": "2026-08-05 18:00:00",
                "seats_max": 20,
            }
        )
        cls.admin_user = cls.env.ref("base.user_admin")
        cls.staff = cls.env["camp.staff"].create(
            {
                "event_id": cls.event.id,
                "name": "Instruktor QA",
                "role": "instruktor",
                "user_id": cls.admin_user.id,
                "date_from": "2026-08-01",
                "date_to": "2026-08-05",
            }
        )
        cls.migrate = staticmethod(_load_migrate())

    def _create_legacy_schema(self):
        cr = self.env.cr
        cr.execute(
            """
            CREATE TABLE camp_program (
                id serial PRIMARY KEY,
                event_id integer,
                name varchar,
                date date,
                start_time double precision,
                end_time double precision,
                plan_variant varchar,
                description text,
                incidents text,
                participant_count integer,
                is_published boolean,
                theme jsonb,
                weather_plan varchar,
                schedule_entry_id integer,
                state varchar,
                create_uid integer,
                create_date timestamp,
                write_uid integer,
                write_date timestamp
            )
            """
        )
        cr.execute(
            """
            CREATE TABLE camp_program_activity (
                id serial PRIMARY KEY,
                program_id integer,
                time_start double precision,
                time_end double precision,
                activity_name jsonb,
                location jsonb,
                responsible_id integer,
                activity_type varchar,
                risk_water boolean,
                risk_heights boolean,
                notes text,
                create_uid integer,
                create_date timestamp,
                write_uid integer,
                write_date timestamp
            )
            """
        )

    def _insert_legacy_program(self, plan_variant, day_offset, theme, activity):
        cr = self.env.cr
        uid = self.env.uid
        cr.execute(
            """
            INSERT INTO camp_program
                (event_id, name, date, start_time, end_time, plan_variant,
                 description, incidents, participant_count, is_published,
                 theme, weather_plan, schedule_entry_id, state,
                 create_uid, create_date, write_uid, write_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    jsonb_build_object('en_US', %s::text), %s, NULL, %s,
                    %s, now(), %s, now())
            RETURNING id
            """,
            (
                self.event.id,
                f"Dzień QA {plan_variant}",
                fields.Date.to_date("2026-08-01") + timedelta(days=day_offset),
                9.0,
                18.0,
                plan_variant,
                "<p>Opis wykonania QA</p>",
                "Brak incydentów",
                15,
                True,
                theme,
                "sun" if plan_variant == "a" else "rain",
                "draft",
                uid,
                uid,
            ),
        )
        program_id = cr.fetchone()[0]

        cr.execute(
            """
            INSERT INTO camp_program_activity
                (program_id, time_start, time_end, activity_name, location,
                 responsible_id, activity_type, risk_water, risk_heights, notes,
                 create_uid, create_date, write_uid, write_date)
            VALUES (%s, %s, %s,
                    jsonb_build_object('en_US', %s::text),
                    jsonb_build_object('en_US', %s::text),
                    %s, %s, %s, %s, %s, %s, now(), %s, now())
            RETURNING id
            """,
            (
                program_id,
                activity["time_start"],
                activity["time_end"],
                activity["name"],
                activity["location"],
                self.admin_user.partner_id.id,
                activity["activity_type"],
                activity["risk_water"],
                activity["risk_heights"],
                activity["notes"],
                uid,
                uid,
            ),
        )
        activity_id = cr.fetchone()[0]
        return program_id, activity_id

    def test_migration_lossless_and_idempotent(self):
        self._create_legacy_schema()
        prog_a_id, act_a_id = self._insert_legacy_program(
            "a",
            0,
            "Piratów",
            {
                "time_start": 10.0,
                "time_end": 11.5,
                "name": "Kąpiel w jeziorze",
                "location": "Jezioro",
                "activity_type": "sport",
                "risk_water": True,
                "risk_heights": False,
                "notes": "Uwaga na dzieci",
            },
        )
        prog_b_id, act_b_id = self._insert_legacy_program(
            "b",
            0,
            "Piratów (deszcz)",
            {
                "time_start": 10.0,
                "time_end": 11.0,
                "name": "Gry planszowe",
                "location": "Świetlica",
                "activity_type": "rest",
                "risk_water": False,
                "risk_heights": False,
                "notes": "Sala B",
            },
        )

        # ── 1st run: migrate() перетворює легасі-рядки на keeper ──
        self.migrate(self.env.cr, "17.0.4.1.5")

        Structured = self.env["camp.program.structured"]
        sunny = Structured.search([("event_id", "=", self.event.id), ("is_rain_plan", "=", False)])
        rainy = Structured.search([("event_id", "=", self.event.id), ("is_rain_plan", "=", True)])
        self.assertEqual(len(sunny), 1, "Plan A мусить піти в is_rain_plan=False відро")
        self.assertEqual(len(rainy), 1, "Plan B мусить піти в is_rain_plan=True відро")

        day_a = sunny.day_ids
        day_b = rainy.day_ids
        self.assertEqual(len(day_a), 1)
        self.assertEqual(len(day_b), 1)

        # S1-4: унікальні поля legacy camp.program перенесені 1:1
        self.assertEqual(day_a.name, "Dzień QA a")
        self.assertEqual(day_a.theme, "Piratów")
        self.assertEqual(day_a.exec_start_time, 9.0)
        self.assertEqual(day_a.exec_end_time, 18.0)
        self.assertEqual(day_a.participant_count, 15)
        self.assertTrue(day_a.is_published)
        self.assertEqual(day_a.weather_plan, "sun")
        self.assertIn("Opis wykonania QA", day_a.description or "")
        self.assertEqual(day_a.incidents, "Brak incydentów")
        self.assertEqual(day_a.state, "draft")

        line_a = day_a.activity_line_ids
        self.assertEqual(len(line_a), 1)
        self.assertEqual(line_a.time_from, 10.0)
        self.assertEqual(line_a.time_to, 11.5)
        self.assertEqual(line_a.title, "Kąpiel w jeziorze")
        self.assertEqual(line_a.location, "Jezioro")
        self.assertTrue(line_a.risk_water)
        self.assertFalse(line_a.risk_heights)
        # activity_type 'sport' згорнуто в category 'activity' (документована втрата гранулярності)
        self.assertEqual(line_a.category, "activity")
        # responsible_id: res.partner (legacy) → camp.staff через user_id.partner_id
        self.assertEqual(line_a.responsible_id, self.staff)

        line_b = day_b.activity_line_ids
        self.assertEqual(line_b.category, "rest")
        self.assertEqual(line_b.title, "Gry planszowe")

        # ── ідемпотентність: 2-й прогін НЕ дублює жодного рядка ──
        self.migrate(self.env.cr, "17.0.4.1.5")
        self.assertEqual(
            Structured.search_count([("event_id", "=", self.event.id)]),
            2,
            "повторний migrate() не має плодити нові camp.program.structured",
        )
        self.assertEqual(len(sunny.day_ids), 1, "повторний migrate() не дублює дні")
        self.assertEqual(
            len(sunny.day_ids.activity_line_ids), 1, "повторний migrate() не дублює лінії"
        )

        # ── перенесена здатність (state-machine) реально працює на keeper ──
        self.assertEqual(day_a.state, "draft")
        day_a.action_approve()
        self.assertEqual(day_a.state, "approved")
        day_a.action_schedule()
        self.assertEqual(day_a.state, "scheduled")
        day_a.action_start()
        self.assertEqual(day_a.state, "ongoing")
        day_a.action_complete()
        self.assertEqual(day_a.state, "completed")
