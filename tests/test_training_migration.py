# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Reuse S1 пара 6 — lossless synthetic test for the three-way training-record
merge: vozhatyi.training.record ⇄ fayna.vozhatyi.training(+module+certificate)
→ camp.staff.training.record (keeper, extends native slide.channel).

Docker-харнес завжди робить свіжий ``-i`` install (легасі-таблиці не існують —
моделі видалені з коду), тому migrations/17.0.4.1.5/post-migrate.py НІКОЛИ
природно не запускається тут (post-migrate виконується лише на реальному
``-u`` апгрейді існуючої інсталяції). Щоб довести коректність міграції без
живих staging-даних (ssh на staging заблоковано), цей тест:

1. СТВОРЮЄ ad-hoc "легасі" таблиці (``vozhatyi_training_record``,
   ``fayna_vozhatyi_training``, ``fayna_vozhatyi_training_module``,
   ``fayna_vozhatyi_certificate``) через сирий SQL — так, як вони існували б
   на реальній БД до цього PR (DDL транзакційний — зникає з rollback тесту).
2. Вставляє синтетичні рядки, що імітують історичні записи з ОБОХ легасі-
   систем (одна детальна fayna.vozhatyi.training з модулями+сертифікатом,
   один флет vozhatyi.training.record).
3. Імпортує ТОЙ САМИЙ файл migrations/17.0.4.1.5/post-migrate.py (importlib)
   і викликає migrate(cr, "17.0.4.1.5") напряму через реальний cr — без
   sudo-обходу, без мокання ORM.
4. Доводить: keeper отримав обидва записи 1:1 (S1-4), повторний виклик
   migrate() НЕ дублює рядки (unique_partner_channel + ir_model_data мітки),
   і перенесена здатність (новий expiry-cron, раніше відсутній на keeper)
   реально працює.
"""

import importlib.util
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged


def _load_migrate():
    """Load migrate(cr, version) straight from migrations/17.0.4.1.5/post-migrate.py."""
    module_path = get_module_path("fayna_camp_portal")
    script_path = f"{module_path}/migrations/17.0.4.1.5/post-migrate.py"
    spec = importlib.util.spec_from_file_location("reuse_s1p6_post_migrate", script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.migrate


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestTrainingRecordKeeperCron(TransactionCase):
    """Reuse S1 пара 6: keeper's own (new) behaviour, no migration involved.

    FIX found while merging: camp.staff.training.record has always had an
    `expired` state and a manual action_expire() button, but nothing flipped
    it automatically — unlike both legacy trackers it absorbs, which each had
    a working expiry cron. This proves the newly-wired cron closes that gap.
    """

    def _channel(self, course_type="wychowawca", required_hours=36.0):
        return self.env["slide.channel"].create(
            {
                "name": "Kurs QA",
                "camp_course_type": course_type,
                "required_hours": required_hours,
                "is_men_course": True,
            }
        )

    def test_cron_expires_only_past_due_certified_records(self):
        channel = self._channel()
        partner_old = self.env["res.partner"].create({"name": "Wychowawca Stary QA"})
        partner_fresh = self.env["res.partner"].create({"name": "Wychowawca Świeży QA"})
        Record = self.env["camp.staff.training.record"]

        old_rec = Record.create(
            {
                "partner_id": partner_old.id,
                "channel_id": channel.id,
                "hours_completed": 36.0,
                "state": "certified",
                "certificate_number": "CAMP-WYC-OLDQA",
                "issue_date": fields.Date.today() - timedelta(days=6 * 365),
            }
        )
        fresh_rec = Record.create(
            {
                "partner_id": partner_fresh.id,
                "channel_id": channel.id,
                "hours_completed": 36.0,
                "state": "certified",
                "certificate_number": "CAMP-WYC-FRESHQA",
                "issue_date": fields.Date.today() - timedelta(days=30),
            }
        )
        self.assertTrue(old_rec.expiry_date < fields.Date.today())
        self.assertTrue(fresh_rec.expiry_date > fields.Date.today())

        Record._cron_expire_training_records()

        self.assertEqual(old_rec.state, "expired", "5-річний сертифікат мусить прострочитись")
        self.assertEqual(fresh_rec.state, "certified", "свіжий сертифікат лишається чинним")

    def test_print_certificate_requires_certified_state(self):
        channel = self._channel()
        partner = self.env["res.partner"].create({"name": "Wychowawca Enrolled QA"})
        rec = self.env["camp.staff.training.record"].create(
            {"partner_id": partner.id, "channel_id": channel.id, "state": "enrolled"}
        )
        with self.assertRaises(UserError):
            rec.action_print_certificate()

        rec.write(
            {
                "state": "certified",
                "certificate_number": "CAMP-WYC-PRINTQA",
                "issue_date": fields.Date.today(),
            }
        )
        # action_print_certificate() no longer raises now that state=certified
        # (guard already proven above); its report_action() return SHAPE
        # depends on admin/company-logo context (may wrap into a "configure
        # external layout" act_window on a fresh test company) — not what
        # this test is about. What matters (like test_dziennik_pdf's
        # test_report_action_exists/test_render_qweb_html_smoke pattern):
        # the xmlid resolves to a real qweb-pdf report AND it actually renders.
        action = rec.action_print_certificate()
        self.assertTrue(action)
        report = self.env.ref(
            "fayna_camp_portal.camp_staff_training_record_certificate_report_action"
        )
        self.assertEqual(report._name, "ir.actions.report")
        self.assertEqual(report.model, "camp.staff.training.record")
        self.assertEqual(report.report_type, "qweb-pdf")
        html, render_type = self.env["ir.actions.report"]._render_qweb_html(
            "fayna_camp_portal.camp_staff_training_record_certificate_report_action", rec.ids
        )
        self.assertEqual(render_type, "html")
        content = html.decode("utf-8")
        self.assertIn("CAMP-WYC-PRINTQA", content)
        self.assertIn(partner.name, content)


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestLegacyTrainingMigration(TransactionCase):
    """Reuse S1 пара 6: lossless + idempotent migration from BOTH legacy sources."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migrate = staticmethod(_load_migrate())
        cls.wychowawca = cls.env["res.partner"].create({"name": "Instruktor Kursu QA"})
        cls.trainee_b = cls.env["res.partner"].create({"name": "Uczestnik Programu QA"})
        cls.trainee_a = cls.env["res.partner"].create({"name": "Uczestnik Płaski QA"})
        cls.admin_user = cls.env.ref("base.user_admin")

    def _create_legacy_schema(self):
        cr = self.env.cr
        cr.execute(
            """
            CREATE TABLE fayna_vozhatyi_training (
                id serial PRIMARY KEY,
                name varchar,
                participant_id integer,
                training_type varchar,
                start_date date,
                end_date date,
                location varchar,
                instructor_id integer,
                state varchar,
                total_hours double precision,
                certificate_date date,
                certificate_number varchar,
                certificate_id integer,
                create_uid integer,
                create_date timestamp,
                write_uid integer,
                write_date timestamp
            )
            """
        )
        cr.execute(
            """
            CREATE TABLE fayna_vozhatyi_training_module (
                id serial PRIMARY KEY,
                training_id integer,
                name varchar,
                sequence integer,
                hours double precision,
                completed boolean,
                completion_date date
            )
            """
        )
        cr.execute(
            """
            CREATE TABLE fayna_vozhatyi_certificate (
                id serial PRIMARY KEY,
                training_id integer,
                issue_date date,
                valid_until date,
                certificate_number varchar
            )
            """
        )
        cr.execute(
            """
            CREATE TABLE vozhatyi_training_record (
                id serial PRIMARY KEY,
                partner_id integer,
                training_type varchar,
                completion_date date,
                certificate_number varchar,
                valid_until date,
                notes text,
                state varchar,
                create_uid integer,
                create_date timestamp,
                write_uid integer,
                write_date timestamp
            )
            """
        )

    def _insert_legacy_data(self):
        cr = self.env.cr
        uid = self.env.uid

        # ── Source B: detailed program with modules + issued certificate ──
        cr.execute(
            """
            INSERT INTO fayna_vozhatyi_training
                (name, participant_id, training_type, start_date, end_date,
                 location, instructor_id, state, total_hours, certificate_date,
                 certificate_number, certificate_id, create_uid, create_date,
                 write_uid, write_date)
            VALUES (%s, %s, 'wychowawca_36h', '2026-05-01', '2026-05-10',
                    'Ośrodek Szkoleniowy QA', %s, 'certified', 36.0, '2026-05-11',
                    'FAYNA-WYC-LEGACY1', NULL, %s, now(), %s, now())
            RETURNING id
            """,
            (
                "Kurs Wychowawcy QA maj 2026",
                self.trainee_b.id,
                self.wychowawca.id,
                uid,
                uid,
            ),
        )
        training_id = cr.fetchone()[0]

        cr.execute(
            """
            INSERT INTO fayna_vozhatyi_certificate
                (training_id, issue_date, valid_until, certificate_number)
            VALUES (%s, '2026-05-11', '2031-05-11', 'FAYNA-WYC-CERT1')
            RETURNING id
            """,
            (training_id,),
        )
        cert_id = cr.fetchone()[0]
        cr.execute(
            "UPDATE fayna_vozhatyi_training SET certificate_id = %s WHERE id = %s",
            (cert_id, training_id),
        )

        cr.execute(
            """
            INSERT INTO fayna_vozhatyi_training_module
                (training_id, name, sequence, hours, completed, completion_date)
            VALUES
                (%s, 'Group Dynamics', 10, 4.0, TRUE, '2026-05-02'),
                (%s, 'First Aid (BLS/AED)', 20, 6.0, TRUE, '2026-05-03')
            """,
            (training_id, training_id),
        )

        # ── Source A: flat record, no linked program ──
        cr.execute(
            """
            INSERT INTO vozhatyi_training_record
                (partner_id, training_type, completion_date, certificate_number,
                 valid_until, notes, state, create_uid, create_date, write_uid, write_date)
            VALUES (%s, 'first_aid', '2026-04-01', 'FAYNA-FA-LEGACY2',
                    '2031-04-01', 'Ukończono na platformie zewnętrznej', 'completed',
                    %s, now(), %s, now())
            RETURNING id
            """,
            (self.trainee_a.id, uid, uid),
        )
        record_id = cr.fetchone()[0]
        return training_id, record_id

    def test_migration_lossless_and_idempotent(self):
        self._create_legacy_schema()
        training_id, record_id = self._insert_legacy_data()

        # ── 1st run ──
        self.migrate(self.env.cr, "17.0.4.1.5")

        Keeper = self.env["camp.staff.training.record"]
        rec_b = Keeper.search([("partner_id", "=", self.trainee_b.id)])
        rec_a = Keeper.search([("partner_id", "=", self.trainee_a.id)])
        self.assertEqual(len(rec_b), 1, "детальна легасі-програма → 1 keeper-запис")
        self.assertEqual(len(rec_a), 1, "флет легасі-запис → 1 keeper-запис")

        # S1-4: унікальна семантика fayna.vozhatyi.training перенесена 1:1
        self.assertEqual(rec_b.channel_id.camp_course_type, "wychowawca")
        self.assertEqual(rec_b.hours_completed, 36.0)
        self.assertEqual(rec_b.state, "certified")
        self.assertEqual(
            rec_b.certificate_number, "FAYNA-WYC-CERT1", "сертифікат дочірньої моделі має пріоритет"
        )
        self.assertEqual(str(rec_b.issue_date), "2026-05-11")
        self.assertEqual(
            str(rec_b.expiry_date), "2031-05-11", "valid_until перенесено 1:1, не перераховано"
        )
        self.assertEqual(str(rec_b.session_start_date), "2026-05-01")
        self.assertEqual(str(rec_b.session_end_date), "2026-05-10")
        self.assertEqual(rec_b.session_location, "Ośrodek Szkoleniowy QA")
        self.assertEqual(rec_b.instructor_id, self.wychowawca)

        # module_ids granularity → chatter provenance note
        b_messages = rec_b.message_ids.filtered(
            lambda m: "migracja fayna.vozhatyi.training" in (m.body or "")
        )
        self.assertTrue(b_messages, "деталі модулів мають бути в chatter-нотатці")
        self.assertIn("Group Dynamics", b_messages[0].body)
        self.assertIn("First Aid", b_messages[0].body)

        # S1-4: унікальна семантика vozhatyi.training.record перенесена 1:1
        self.assertEqual(rec_a.channel_id.camp_course_type, "first_aid")
        self.assertEqual(
            rec_a.state, "certified", "completed+certificate_number → certified на keeper'і"
        )
        self.assertEqual(rec_a.certificate_number, "FAYNA-FA-LEGACY2")
        self.assertEqual(str(rec_a.issue_date), "2026-04-01")
        self.assertEqual(str(rec_a.expiry_date), "2031-04-01")
        a_messages = rec_a.message_ids.filtered(
            lambda m: "migracja vozhatyi.training.record" in (m.body or "")
        )
        self.assertTrue(a_messages, "notes мають бути в chatter-нотатці")
        self.assertIn("Ukończono na platformie zewnętrznej", a_messages[0].body)

        # ── ідемпотентність: 2-й прогін НЕ дублює жодного рядка ──
        self.migrate(self.env.cr, "17.0.4.1.5")
        self.assertEqual(
            Keeper.search_count([("partner_id", "in", [self.trainee_a.id, self.trainee_b.id])]),
            2,
            "повторний migrate() не має плодити нові camp.staff.training.record",
        )

        # ── перенесена здатність (новий expiry-cron) реально працює ──
        rec_b.write({"issue_date": fields.Date.today() - timedelta(days=6 * 365)})
        self.assertEqual(rec_b.state, "certified")
        Keeper._cron_expire_training_records()
        self.assertEqual(
            rec_b.state, "expired", "перенесений запис підпадає під живий expiry-cron keeper'а"
        )
