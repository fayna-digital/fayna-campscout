# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Reuse S1 пара 5: legacy camp.program (+camp.program.activity) →
camp.program.structured (+camp.program.day +camp.program.activity.line).

Reuse-check note (grep-доказ на ітерації, дозволений STEP1_TZ п."фінальний
вибір"): camp.schedule.entry НЕ входить у це злиття і НЕ видаляється. Це
окрема жива фіча — маркетинговий "типовий день" (Plan A/Plan B) на сторінці
продукту (product.template.schedule_ids), без дат, з живим menuitem
"Harmonogram"; вона НЕ пов'язана з майстром створення обозу й skeleton-
генератором (camp.program.structured._generate_skeleton) і не має жодного
структурного перетину з per-event day-by-day плануванням. Форсоване злиття
двох різних доменів (product-template маркетинг vs event-instance
операційний план) було б вигадкою, не реюзом — тому лишена як є.

Мапінг: кожен рядок camp_program → camp.program.structured (found-or-create
за event_id + is_rain_plan, де is_rain_plan = (plan_variant = 'b') — так
Plan A/B легасі-моделі влучає у вже наявну is_rain_plan-семантику keeper'а
без дублювання поля) → camp.program.day того ж event+дати. Дочірні
camp_program_activity → camp.program.activity.line (responsible_id
res.partner → camp.staff через camp_staff.user_id.partner_id;
activity_type згорнуто в category — meal/rest прямо, sport/creative/
educational/other → activity; ризик-флаги risk_water/risk_heights перенесені
1:1 — розбіжність задокументована в PR).

theme (camp_program) та activity_name/location (camp_program_activity) —
translate=True на легасі-моделях (jsonb-колонка Odoo 16+, psycopg2 віддає
dict); розпаковуємо en_US на читанні. Keeper: theme на camp.program.day теж
translate=True — запаковуємо назад jsonb_build_object('en_US', …) (той
самий прийом, що в пари 4 для notes); title/location на activity.line НЕ
перекладні — пишуться як звичайний varchar.

Ідемпотентність — через мітки в ir_model_data (module=fayna_camp_portal,
name=reuse_s1p5_day_<id> / reuse_s1p5_line_<id>), бо camp_program не мав
природного унікального ключа (event_id, date): могло бути кілька рядків на
день. staff_ids / photo_attachment_ids (M2M) — best-effort за детермінованими
назвами relation-таблиць Odoo (сортована пара model._table + '_rel'),
перевіреними по факту наявних колонок (не лише LIKE-збіг імені — інакше можна
випадково влучити в OWN keeper-таблицю); неуспіх цього блоку не валить решту
міграції.

Дані лише staging-тестові (STEP1_TZ, контекст даних §10 — прод не
встановлений)."""
import logging

_logger = logging.getLogger(__name__)

MODULE = "fayna_camp_portal"

_ACTIVITY_TYPE_TO_CATEGORY = {
    "meal": "meal",
    "rest": "rest",
}


def _table_has_columns(cr, table, columns):
    """Exact existence check: table exists AND carries every expected column.

    Guards against a loose name match picking up an unrelated relation table
    (e.g. the keeper's OWN m2m table also containing the same substring)."""
    cr.execute("SELECT to_regclass(%s)", (f"public.{table}",))
    if not cr.fetchone()[0]:
        return False
    cr.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s",
        (table,),
    )
    existing = {row[0] for row in cr.fetchall()}
    return set(columns) <= existing


def _migrate_m2m_best_effort(cr, day_id_map, legacy_table, legacy_col_a, legacy_col_b,
                              keeper_table, keeper_col_a, keeper_col_b, label):
    if not day_id_map:
        return 0
    # SAVEPOINT: будь-яка несподіванка тут відкочується лише до цієї точки,
    # не «отруюючи» решту транзакції міграції (own try/except, як у 4.1.0).
    try:
        with cr.savepoint():
            if not _table_has_columns(cr, legacy_table, (legacy_col_a, legacy_col_b)):
                return 0
            if not _table_has_columns(cr, keeper_table, (keeper_col_a, keeper_col_b)):
                _logger.info(
                    "reuse-s1p5: keeper-таблиця %s не знайдена — %s пропущено", keeper_table, label
                )
                return 0
            moved = 0
            for old_id, new_id in day_id_map.items():
                # legacy_table/legacy_col_* are hardcoded internal constants
                # passed by migration callers (see migrate() below), never
                # user input; only %s-bound values are actual data.
                cr.execute(
                    f"SELECT {legacy_col_b} FROM {legacy_table} WHERE {legacy_col_a} = %s",  # nosec B608
                    (old_id,),
                )
                for (related_id,) in cr.fetchall():
                    # keeper_table/keeper_col_* are hardcoded internal
                    # constants passed by migration callers, not user input.
                    cr.execute(
                        f"""
                        INSERT INTO {keeper_table} ({keeper_col_a}, {keeper_col_b})
                        SELECT %s, %s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM {keeper_table}
                            WHERE {keeper_col_a} = %s AND {keeper_col_b} = %s
                        )
                        """,  # nosec B608
                        (new_id, related_id, new_id, related_id),
                    )
                    moved += cr.rowcount
            return moved
    except Exception:
        _logger.exception("reuse-s1p5: %s — best-effort блок дав збій, не критично", label)
        return 0


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})

    cr.execute("SELECT to_regclass('public.camp_program')")
    if not cr.fetchone()[0]:
        _logger.info("reuse-s1p5: таблиці camp_program немає — нічого переносити")
        return

    cr.execute(
        """
        SELECT id, event_id, name, date, start_time, end_time, plan_variant,
               description, incidents, participant_count, is_published,
               theme, weather_plan, schedule_entry_id, state,
               create_uid, create_date, write_uid, write_date
        FROM camp_program
        WHERE event_id IS NOT NULL AND date IS NOT NULL
        ORDER BY id
        """
    )
    columns = [d[0] for d in cr.description]
    programs = [dict(zip(columns, row)) for row in cr.fetchall()]

    day_id_map = {}
    structured_cache = {}
    created_structured_ids = []
    created_structured = 0
    created_days = 0
    reused_days = 0

    for p in programs:
        marker = f"reuse_s1p5_day_{p['id']}"
        cr.execute(
            "SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s",
            (MODULE, marker),
        )
        found = cr.fetchone()
        if found:
            day_id_map[p["id"]] = found[0]
            reused_days += 1
            continue

        is_rain = p["plan_variant"] == "b"
        key = (p["event_id"], is_rain)
        structured_id = structured_cache.get(key)
        if structured_id is None:
            cr.execute(
                "SELECT id FROM camp_program_structured WHERE event_id = %s AND is_rain_plan = %s",
                (p["event_id"], is_rain),
            )
            row = cr.fetchone()
            if row:
                structured_id = row[0]
            else:
                cr.execute(
                    """
                    INSERT INTO camp_program_structured
                        (event_id, is_rain_plan, state,
                         create_uid, create_date, write_uid, write_date)
                    VALUES (%s, %s, 'draft', %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        p["event_id"], is_rain,
                        p["create_uid"], p["create_date"], p["write_uid"], p["write_date"],
                    ),
                )
                structured_id = cr.fetchone()[0]
                created_structured += 1
                created_structured_ids.append(structured_id)
            structured_cache[key] = structured_id

        # theme — translate=True на легасі й на keeper'і (jsonb-колонка Odoo
        # 16+); psycopg2 віддає jsonb-колонку як dict, розпаковуємо en_US і
        # запаковуємо назад тим самим jsonb_build_object, що й звичайний ORM-
        # запис при активній мові en_US (той самий прийом, що в пари 4).
        theme_val = p["theme"]
        theme_plain = theme_val.get("en_US") if isinstance(theme_val, dict) else theme_val

        cr.execute(
            """
            INSERT INTO camp_program_day
                (program_id, date, name, theme, exec_start_time, exec_end_time,
                 description, incidents, participant_count, is_published,
                 weather_plan, schedule_entry_id, state,
                 create_uid, create_date, write_uid, write_date)
            VALUES (%s, %s, %s,
                    CASE WHEN %s::text IS NULL THEN NULL ELSE jsonb_build_object('en_US', %s::text) END,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                structured_id, p["date"], p["name"], theme_plain, theme_plain,
                p["start_time"], p["end_time"], p["description"], p["incidents"],
                p["participant_count"], bool(p["is_published"]), p["weather_plan"],
                p["schedule_entry_id"], p["state"] or "draft",
                p["create_uid"], p["create_date"], p["write_uid"], p["write_date"],
            ),
        )
        new_day_id = cr.fetchone()[0]
        day_id_map[p["id"]] = new_day_id
        created_days += 1

        cr.execute(
            """
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
            VALUES (%s, %s, 'camp.program.day', %s, TRUE)
            """,
            (MODULE, marker, new_day_id),
        )

    # ── дочірні рядки: camp_program_activity → camp.program.activity.line ──
    created_lines = 0
    reused_lines = 0
    cr.execute("SELECT to_regclass('public.camp_program_activity')")
    if cr.fetchone()[0]:
        cr.execute(
            """
            SELECT a.id, a.program_id, a.time_start, a.time_end, a.activity_name,
                   a.location, a.responsible_id, a.activity_type, a.risk_water,
                   a.risk_heights, a.notes, a.create_uid, a.create_date,
                   a.write_uid, a.write_date
            FROM camp_program_activity a
            JOIN camp_program p ON p.id = a.program_id
            WHERE p.event_id IS NOT NULL AND p.date IS NOT NULL
            ORDER BY a.id
            """
        )
        acols = [d[0] for d in cr.description]
        activities = [dict(zip(acols, row)) for row in cr.fetchall()]

        for a in activities:
            marker = f"reuse_s1p5_line_{a['id']}"
            cr.execute(
                "SELECT 1 FROM ir_model_data WHERE module = %s AND name = %s",
                (MODULE, marker),
            )
            if cr.fetchone():
                reused_lines += 1
                continue

            day_id = day_id_map.get(a["program_id"])
            if not day_id:
                continue

            responsible_staff_id = None
            if a["responsible_id"]:
                cr.execute(
                    """
                    SELECT st.id FROM camp_staff st
                    JOIN res_users u ON u.id = st.user_id
                    WHERE u.partner_id = %s LIMIT 1
                    """,
                    (a["responsible_id"],),
                )
                row = cr.fetchone()
                responsible_staff_id = row[0] if row else None

            category = _ACTIVITY_TYPE_TO_CATEGORY.get(a["activity_type"], "activity")

            # activity_name / location — translate=True на легасі-моделі
            # (jsonb), keeper-поля title/location НЕ перекладні (plain
            # varchar) — розпаковуємо en_US перед вставкою.
            activity_name_val = a["activity_name"]
            activity_name_plain = (
                activity_name_val.get("en_US") if isinstance(activity_name_val, dict) else activity_name_val
            )
            location_val = a["location"]
            location_plain = location_val.get("en_US") if isinstance(location_val, dict) else location_val

            cr.execute(
                """
                INSERT INTO camp_program_activity_line
                    (day_id, time_from, time_to, title, location, responsible_id,
                     category, risk_water, risk_heights, notes, is_skeleton,
                     is_locked, owner_role,
                     create_uid, create_date, write_uid, write_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, FALSE, FALSE,
                        'kierownik', %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    day_id, a["time_start"], a["time_end"], activity_name_plain,
                    location_plain, responsible_staff_id, category,
                    bool(a["risk_water"]), bool(a["risk_heights"]), a["notes"],
                    a["create_uid"], a["create_date"], a["write_uid"], a["write_date"],
                ),
            )
            new_line_id = cr.fetchone()[0]
            created_lines += 1

            cr.execute(
                """
                INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
                VALUES (%s, %s, 'camp.program.activity.line', %s, TRUE)
                """,
                (MODULE, marker, new_line_id),
            )

    # ── best-effort M2M: staff_ids / photo_attachment_ids ──
    # Точні назви за детермінованим алгоритмом Odoo (Many2many без явної
    # relation-таблиці: '%s_%s_rel' % tuple(sorted([table_a, table_b]))).
    moved_staff = _migrate_m2m_best_effort(
        cr, day_id_map,
        legacy_table="camp_program_camp_staff_rel",
        legacy_col_a="camp_program_id", legacy_col_b="camp_staff_id",
        keeper_table="camp_program_day_camp_staff_rel",
        keeper_col_a="camp_program_day_id", keeper_col_b="camp_staff_id",
        label="staff_ids",
    )
    moved_photos = _migrate_m2m_best_effort(
        cr, day_id_map,
        legacy_table="camp_program_ir_attachment_rel",
        legacy_col_a="camp_program_id", legacy_col_b="ir_attachment_id",
        keeper_table="camp_program_day_ir_attachment_rel",
        keeper_col_a="camp_program_day_id", keeper_col_b="ir_attachment_id",
        label="photo_attachment_ids",
    )

    # ── Backfill stored computes bypassed by raw INSERT (INC-215 fix) ──
    # Рамковий день (wake_time..rest_duration): default=X на полі — це ORM
    # Python-default, НЕ SQL DEFAULT колонки, тож raw INSERT лишає їх NULL.
    # Заповнюємо ЛИШЕ щойно СТВОРЕНИМ цією міграцією structured-записам
    # (вже існуючі не чіпаємо — вони або мають свої значення, або так само
    # NULL і будуть виправлені при першому редагуванні формою — не regression
    # цього фікса).
    if created_structured_ids:
        cr.execute(
            """
            UPDATE camp_program_structured
            SET wake_time = COALESCE(wake_time, 7.0),
                breakfast = COALESCE(breakfast, 8.0),
                lunch = COALESCE(lunch, 13.0),
                afternoon_rest = COALESCE(afternoon_rest, 14.0),
                snack = COALESCE(snack, 16.0),
                dinner = COALESCE(dinner, 18.0),
                lights_out = COALESCE(lights_out, 22.0),
                meal_duration = COALESCE(meal_duration, 0.75),
                rest_duration = COALESCE(rest_duration, 1.0)
            WHERE id = ANY(%s)
            """,
            (created_structured_ids,),
        )

    # name (_rec_name!) + day_count на structured; day_number + display_name
    # (_rec_name!) на day — @api.depends-компьюти, які raw INSERT не рахує.
    # Рахуємо через ORM (не дублюємо compute-логіку SQL-ом) і явно flush-имо
    # (post-migrate може завершитись до природного авто-flush транзакції).
    if structured_cache:
        structured_recs = env["camp.program.structured"].browse(set(structured_cache.values()))
        structured_recs._compute_name()
        structured_recs._compute_day_count()
        structured_recs.flush_recordset(["name", "day_count"])
    if day_id_map:
        day_recs = env["camp.program.day"].browse(set(day_id_map.values()))
        day_recs._compute_day_number()
        day_recs._compute_display_name()
        day_recs.flush_recordset(["day_number", "display_name"])

    cr.execute("SELECT count(*) FROM camp_program")
    total_programs = cr.fetchone()[0]
    _logger.info(
        "reuse-s1p5: programs=%d → structured створено %d, дні створено %d (уже було %d), "
        "лінії створено %d (уже було %d), staff_ids перенесено %d, photos перенесено %d",
        total_programs, created_structured, created_days, reused_days,
        created_lines, reused_lines, moved_staff, moved_photos,
    )
