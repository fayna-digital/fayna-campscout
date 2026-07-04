# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Reuse S1 пара 4: camp.participant.diet → camp.diet.profile.

Рядки стають profile-рядками (participant_id, dietary_restrictions+notes →
notes), алергени переливаються між M2M-таблицями. Upsert-safe за participant.
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
        INSERT INTO camp_diet_profile
            (participant_id, notes, create_uid, create_date, write_uid, write_date)
        SELECT d.participant_id,
               NULLIF(CONCAT_WS(E'\n\n', d.dietary_restrictions, d.notes), ''),
               d.create_uid, d.create_date, d.write_uid, d.write_date
        FROM camp_participant_diet d
        WHERE NOT EXISTS (
            SELECT 1 FROM camp_diet_profile p
            WHERE p.participant_id = d.participant_id
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
        ON CONFLICT DO NOTHING
        """
    )
    moved_all = cr.rowcount
    cr.execute("SELECT count(*) FROM camp_participant_diet")
    total = cr.fetchone()[0]
    _logger.info("reuse-s1p4: diet=%d → профілів %d, алергенів %d", total, inserted, moved_all)
