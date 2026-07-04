# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Reuse S1 пара 1: camp.stats.snapshot → camp.analytics.snapshot.

Переносить історичні снапшоти у keeper (upsert-safe за (event, date)),
вимикає осиротілий cron. Чистий SQL: моделі stats у реєстрі вже немає.
Прод модуля не має; це best-effort для staging (STEP1_TZ, контекст даних).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("SELECT to_regclass('public.camp_stats_snapshot')")
    if not cr.fetchone()[0]:
        _logger.info("reuse-s1p1: таблиці camp_stats_snapshot немає — нічого переносити")
        return

    cr.execute(
        """
        INSERT INTO camp_analytics_snapshot
            (event_id, snapshot_date, registered_count, occupancy_rate,
             revenue_total, total_capacity, currency_id, display_name,
             create_uid, create_date, write_uid, write_date)
        SELECT s.event_id, s.snapshot_date, s.total_registered, s.occupancy_pct,
               s.total_revenue, s.total_capacity, s.currency_id,
               COALESCE(e.name->>'en_US', '?') || ' / ' || s.snapshot_date::text,
               s.create_uid, s.create_date, s.write_uid, s.write_date
        FROM camp_stats_snapshot s
        JOIN event_event e ON e.id = s.event_id
        WHERE NOT EXISTS (
            SELECT 1 FROM camp_analytics_snapshot a
            WHERE a.event_id = s.event_id AND a.snapshot_date = s.snapshot_date
        )
        """
    )
    moved = cr.rowcount
    cr.execute("SELECT count(*) FROM camp_stats_snapshot")
    total = cr.fetchone()[0]

    cr.execute(
        """
        DELETE FROM ir_cron c USING ir_model_data d
        WHERE d.model = 'ir.cron' AND d.res_id = c.id
          AND d.module = 'fayna_camp_portal' AND d.name = 'ir_cron_camp_stats_snapshot'
        """
    )
    _logger.info(
        "reuse-s1p1: перенесено %d/%d снапшотів у analytics; stats-cron видалено (%d)",
        moved, total, cr.rowcount,
    )
