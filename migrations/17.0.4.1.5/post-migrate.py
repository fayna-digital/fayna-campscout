# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Reuse S1 пара 4: camp.participant.diet → camp.diet.profile.

Рядки стають profile-рядками (participant_id, dietary_restrictions+notes →
notes), алергени переливаються між M2M-таблицями. Upsert-safe за participant.

READ-бік (INC-215): legacy dietary_restrictions і notes мали translate=True
(звірено з models/nutrition.py на b8768c0^) — у реальній БД це jsonb-колонки,
тому їх НЕ МОЖНА конкатенувати як текст (вийшов би сирий JSON-рядок).
Розпаковуємо ->>'en_US' (COALESCE на pl_PL, якщо en відсутній); якщо джерело
має ключ pl_PL — зберігаємо обидві мови.

WRITE-бік: notes на keeper — теж translate=True (jsonb-колонка від Odoo 16+),
тому текст пишеться як jsonb_build_object('en_US', ..., ['pl_PL', ...]) — та
сама форма, яку дає звичайний ORM-запис (fields.py _String.convert_to_column).
Дані staging-тестові (STEP1_TZ)."""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("SELECT to_regclass('public.camp_participant_diet')")
    if not cr.fetchone()[0]:
        _logger.info("reuse-s1p4: таблиці camp_participant_diet немає — нічого переносити")
        return

    cr.execute(
        """
        WITH legacy AS (
            SELECT d.*,
                   NULLIF(CONCAT_WS(E'\n\n',
                                    COALESCE(d.dietary_restrictions ->> 'en_US',
                                             d.dietary_restrictions ->> 'pl_PL'),
                                    COALESCE(d.notes ->> 'en_US',
                                             d.notes ->> 'pl_PL')), '') AS merged_en,
                   CASE WHEN (d.dietary_restrictions ? 'pl_PL' OR d.notes ? 'pl_PL')
                        THEN NULLIF(CONCAT_WS(E'\n\n',
                                              COALESCE(d.dietary_restrictions ->> 'pl_PL',
                                                       d.dietary_restrictions ->> 'en_US'),
                                              COALESCE(d.notes ->> 'pl_PL',
                                                       d.notes ->> 'en_US')), '')
                        ELSE NULL
                   END AS merged_pl
            FROM camp_participant_diet d
        )
        INSERT INTO camp_diet_profile
            (participant_id, notes, display_name, create_uid, create_date, write_uid, write_date)
        SELECT legacy.participant_id,
               CASE WHEN legacy.merged_en IS NULL AND legacy.merged_pl IS NULL THEN NULL
                    WHEN legacy.merged_pl IS NULL
                         THEN jsonb_build_object('en_US', legacy.merged_en)
                    ELSE jsonb_build_object(
                             'en_US', COALESCE(legacy.merged_en, legacy.merged_pl),
                             'pl_PL', legacy.merged_pl)
               END,
               COALESCE(pt.display_name, 'Unknown'),
               legacy.create_uid, legacy.create_date, legacy.write_uid, legacy.write_date
        FROM legacy
        JOIN camp_participant pt ON pt.id = legacy.participant_id
        WHERE NOT EXISTS (
            SELECT 1 FROM camp_diet_profile p
            WHERE p.participant_id = legacy.participant_id
        )
        """
    )
    inserted = cr.rowcount

    cr.execute(
        """
        INSERT INTO camp_diet_profile_allergen_rel (profile_id, allergen_id)
        SELECT p.id, rel.allergen_id
        FROM camp_participant_diet_allergen_rel rel
        JOIN camp_participant_diet d ON d.id = rel.diet_id
        JOIN camp_diet_profile p ON p.participant_id = d.participant_id
        ON CONFLICT (profile_id, allergen_id) DO NOTHING
        """
    )
    moved_all = cr.rowcount
    cr.execute("SELECT count(*) FROM camp_participant_diet")
    total = cr.fetchone()[0]
    _logger.info("reuse-s1p4: diet=%d → профілів %d, алергенів %d", total, inserted, moved_all)
