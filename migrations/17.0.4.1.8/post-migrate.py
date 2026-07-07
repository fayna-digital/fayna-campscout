# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Repair (INC-215): полагодити camp_diet_profile.notes, зіпсовані першою
редакцією міграції 17.0.4.1.5 (pair 4) на БД, де вона ВЖЕ виконалась
(staging на 17.0.4.1.5).

Дефект: legacy-поля camp.participant.diet.dietary_restrictions/notes мали
translate=True (jsonb у БД), а стара міграція конкатенувала їх як текст —
у keeper notes потрапив подвійно загорнутий JSON:
    {"en_US": "{\"en_US\": \"vegan\"}\n\n{\"en_US\": \"...\"}"}

Ознака ураження: notes ->> 'en_US' LIKE '{%' (читабельний текст дієти не
починається з фігурної дужки). Ремонт: пере-вивести значення з legacy-таблиці
camp_participant_diet (вона НЕ дропалась) тією самою правильною трансформацією,
що тепер у 17.0.4.1.5: розпакувати ->>'en_US' (+ pl_PL, якщо є), склеїти
CONCAT_WS(E'\n\n', ...), загорнути ОДИН раз.

Гарди:
- legacy-таблиці немає → лог + skip (нема з чого відновлювати);
- 0 уражених рядків → 0 UPDATE (WHERE не збігається);
- повторний запуск безпечний: полагоджені рядки більше не матчаться на
  LIKE '{%', а якщо легальний текст сам починається з '{' — UPDATE
  перезапише його тим самим правильним значенням (ідемпотентно по значенню).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("SELECT to_regclass('public.camp_participant_diet')")
    if not cr.fetchone()[0]:
        _logger.info(
            "repair-s1p4: таблиці camp_participant_diet немає — "
            "відновлювати нема з чого, пропускаю"
        )
        return

    cr.execute(
        """
        WITH legacy AS (
            SELECT d.participant_id,
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
        UPDATE camp_diet_profile p
        SET notes = CASE
                WHEN legacy.merged_en IS NULL AND legacy.merged_pl IS NULL THEN NULL
                WHEN legacy.merged_pl IS NULL
                     THEN jsonb_build_object('en_US', legacy.merged_en)
                ELSE jsonb_build_object(
                         'en_US', COALESCE(legacy.merged_en, legacy.merged_pl),
                         'pl_PL', legacy.merged_pl)
            END,
            write_date = (now() AT TIME ZONE 'UTC')
        FROM legacy
        WHERE legacy.participant_id = p.participant_id
          AND p.notes ->> 'en_US' LIKE '{%'
        """
    )
    _logger.info("repair-s1p4: полагоджено %d рядків camp_diet_profile.notes", cr.rowcount)
