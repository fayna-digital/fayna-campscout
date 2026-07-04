# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Reuse S1 пара 2: camp.journal → camp.daily.report.

Записи журналу переносяться в kierownik_notes рапорту того ж дня
(рапорт створюється draft, якщо його не було); вкладення журналу
перепідвішуються на рапорт. Чистий SQL (моделі journal у реєстрі немає).
Дані лише staging-тестові (STEP1_TZ, контекст даних)."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("SELECT to_regclass('public.camp_journal')")
    if not cr.fetchone()[0]:
        _logger.info("reuse-s1p2: таблиці camp_journal немає — нічого переносити")
        return

    # 1) рапорти-приймачі (draft) для днів, де їх не було
    cr.execute(
        """
        INSERT INTO camp_daily_report
            (event_id, report_date, author_id, state, active,
             create_uid, create_date, write_uid, write_date)
        SELECT DISTINCT j.event_id, j.date, j.author_id, 'draft', TRUE,
               j.create_uid, j.create_date, j.write_uid, j.write_date
        FROM camp_journal j
        WHERE NOT EXISTS (
            SELECT 1 FROM camp_daily_report r
            WHERE r.event_id = j.event_id AND r.report_date = j.date
        )
        """
    )
    created = cr.rowcount

    # 2) допис записів у kierownik_notes відповідного рапорту
    cr.execute(
        """
        UPDATE camp_daily_report r
        SET kierownik_notes = COALESCE(r.kierownik_notes || E'\n\n', '')
            || '[migracja: dziennik wpisów]' || E'\n' || agg.body
        FROM (
            SELECT j.event_id, j.date,
                   string_agg(
                       '- [' || j.category || '] ' || COALESCE(j.title,'')
                       || ': ' || COALESCE(j.content,''), E'\n'
                       ORDER BY j.date, j.create_date
                   ) AS body
            FROM camp_journal j
            GROUP BY j.event_id, j.date
        ) agg
        WHERE r.event_id = agg.event_id AND r.report_date = agg.date
        """
    )
    updated = cr.rowcount

    # 3) вкладення журналу → на рапорт того ж дня
    cr.execute(
        """
        UPDATE ir_attachment a
        SET res_model = 'camp.daily.report', res_id = r.id
        FROM camp_journal j
        JOIN camp_daily_report r
             ON r.event_id = j.event_id AND r.report_date = j.date
        WHERE a.res_model = 'camp.journal' AND a.res_id = j.id
        """
    )
    moved_att = cr.rowcount
    cr.execute("SELECT count(*) FROM camp_journal")
    total = cr.fetchone()[0]
    _logger.info(
        "reuse-s1p2: journal=%d → рапортів створено %d, доповнено %d, вкладень %d",
        total, created, updated, moved_att,
    )
