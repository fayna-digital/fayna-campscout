# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Reuse S1 пара 3: camp.nutrition (legacy) → camp.menu.day.

Мапінг: breakfast/lunch/dinner прямо; snacks → afternoon_snack;
allergy_notes/diet-лічильники/state/prepared_by — у нові поля keeper'а;
nutrition.notes дописується в keeper.notes. Upsert-safe за (event, date).
Дані staging-тестові (STEP1_TZ)."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("SELECT to_regclass('public.camp_nutrition')")
    if not cr.fetchone()[0]:
        _logger.info("reuse-s1p3: таблиці camp_nutrition немає — нічого переносити")
        return

    cr.execute(
        """
        INSERT INTO camp_menu_day
            (event_id, menu_date, breakfast, lunch, dinner, afternoon_snack,
             allergy_notes, vegetarian_count, vegan_count, gluten_free_count,
             lactose_free_count, state, prepared_by, notes,
             create_uid, create_date, write_uid, write_date)
        SELECT n.event_id, n.menu_date, n.breakfast, n.lunch, n.dinner, n.snacks,
               n.allergy_notes, n.vegetarian_count, n.vegan_count, n.gluten_free_count,
               n.lactose_free_count, COALESCE(n.state, 'draft'), n.prepared_by, n.notes,
               n.create_uid, n.create_date, n.write_uid, n.write_date
        FROM camp_nutrition n
        WHERE NOT EXISTS (
            SELECT 1 FROM camp_menu_day m
            WHERE m.event_id = n.event_id AND m.menu_date = n.menu_date
        )
        """
    )
    inserted = cr.rowcount

    cr.execute(
        """
        UPDATE camp_menu_day m
        SET vegetarian_count = n.vegetarian_count,
            vegan_count = n.vegan_count,
            gluten_free_count = n.gluten_free_count,
            lactose_free_count = n.lactose_free_count,
            allergy_notes = COALESCE(m.allergy_notes, n.allergy_notes),
            notes = COALESCE(m.notes || E'\n\n', '') || COALESCE(n.notes, '')
        FROM camp_nutrition n
        WHERE m.event_id = n.event_id AND m.menu_date = n.menu_date
          AND n.notes IS NOT NULL
        """
    )
    merged = cr.rowcount
    cr.execute("SELECT count(*) FROM camp_nutrition")
    total = cr.fetchone()[0]
    _logger.info("reuse-s1p3: nutrition=%d → вставлено %d, злито в існуючі %d", total, inserted, merged)
