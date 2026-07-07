# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Reuse S1 пара 6: три системи обліку тренінгів кадри → одна.

vozhatyi.training.record ⇄ fayna.vozhatyi.training(+module+certificate) →
camp.staff.training.record (keeper, extends native slide.channel — ADR-001,
website_slides вже depends). Обидві легасі-моделі видалені з реєстру.

Keeper вимагає channel_id (slide.channel, required): для кожного зустрінутого
camp_course_type-відра ("wychowawca", "kierownik_improvement", "first_aid",
"online_platform", "specialty") get-or-create ОДИН slide.channel через ORM
(жодних обов'язкових/jsonb-полів у сирому SQL не чіпаємо — required_hours 36/10
виставляються по типу; курси позначені is_men_course=True); ir_model_data-мітка
на кожен канал.

Мапінг Source A (vozhatyi.training.record, флет):
  training_type → відро курсу; state enrolled/completed(+cert→certified)/expired;
  hours_completed = required_hours каналу, якщо стан завершений, інакше 0;
  certificate_number/valid_until — 1:1 (історичний номер НЕ перенумеровується);
  notes → chatter (message_post), якщо були.

Мапінг Source B (fayna.vozhatyi.training +module +certificate):
  training_type → відро курсу (лише wychowawca_36h/kierownik_10h);
  hours_completed = total_hours (вже агрегат по завершених модулях);
  сертифікат: пріоритет дочірньої fayna.vozhatyi.certificate (issue_date/
  valid_until/certificate_number), fallback на власні поля training;
  instructor_id/location/start_date/end_date → нові session_* поля keeper'а
  (той самий тип res.partner — прямий перенос без пошуку);
  модулі (module_ids) → chatter-запис зі списком (назва/години/дата) —
  документована втрата гранулярності: keeper НЕ будує окрему модель "модуль",
  бо це вже нативно покриває slide.channel/slide.slide (сильніший reuse).

ДЕДУПЛІКАЦІЯ (INC-215 fix, 2026-07-06): keeper має UNIQUE(partner_id,
channel_id), а ЖОДНА легасі-модель такої унікальності не мала — легальні
дублікати цілком можливі (MEN 5-річний цикл поновлення: одна людина законно
має і старий протермінований запис, і новий сертифікований). Попередня версія
цієї міграції вставляла Source B, потім Source A по ORDER BY id з ON CONFLICT
DO NOTHING — при колізії (в межах ОДНОГО джерела чи між джерелами) виживав
запис, вставлений ПЕРШИМ, незалежно від того, який з них справді новіший чи
"сильніший" за станом; загублений запис до того ж отримував ir_model_data-
мітку на ЧУЖИЙ рядок (виглядало як "мігровано", хоча дані згублено).

Тепер: усі кандидати з ОБОХ джерел спершу ЗБИРАЮТЬСЯ в пам'яті й ГРУПУЮТЬСЯ за
(partner_id, course-відро); у кожній групі виграє один кандидат за явним
пріоритетом — стан (certified > completed > expired > in_progress > enrolled),
далі свіжіший issue_date, далі Source B (детальніша) над Source A, далі вищий
legacy id (детермінований останній tie-break). Програні дублікати НЕ гинуть
мовчки: кожен отримує ir_model_data-мітку, що вказує на РЕАЛЬНИЙ (виграний)
рядок (ідемпотентність при повторному прогоні коректна для будь-якого джерела-
дубля), і на виграний рядок дописується chatter-нотатка з ідентифікуючими
полями кожного програного запису (джерело/id/стан/сертифікат/дата) — втрата
гранулярності документована й трасована, не тиха.

theme (camp_program) та activity_name/location (camp_program_activity) —
translate=True на легасі-моделях (jsonb-колонка Odoo 16+, psycopg2 віддає
dict); розпаковуємо en_US на читанні. Дані лише staging-тестові (STEP1_TZ,
контекст даних §10 — прод модуля не встановлений).
"""
import logging
from datetime import date

_logger = logging.getLogger(__name__)

MODULE = "fayna_camp_portal"

# course_type bucket → (channel name, required_hours)
_CHANNEL_SPEC = {
    "wychowawca": ("Kurs wychowawcy (36h) — MEN", 36.0),
    "kierownik_improvement": ("Doskonalenie kierownika — MEN", 10.0),
    "first_aid": ("Pierwsza pomoc / BLS", 0.0),
    "online_platform": ("Szkolenie na platformie online (§2.15)", 0.0),
    "specialty": ("Kurs specjalistyczny (migracja)", 0.0),
}

# legacy training_type (both sources use overlapping vocab) → course_type bucket
_TRAINING_TYPE_TO_BUCKET = {
    "wychowawca_36h": "wychowawca",
    "kierownik_10h": "kierownik_improvement",
    "first_aid": "first_aid",
    "online_platform": "online_platform",
    "other": "specialty",
}

# Пріоритет стану при дедуплікації (вищий число = сильніший/виграє групу).
# certified найсильніший (сертифікат чинний); completed/expired — курс
# пройдено, лише сертифікат протермінований чи ще не виданий; in_progress/
# enrolled — курс ще не завершено.
_STATE_RANK = {
    "certified": 5,
    "completed": 4,
    "expired": 3,
    "in_progress": 2,
    "enrolled": 1,
}


def _candidate_sort_key(c):
    """Найкращий кандидат групи (partner, bucket) — сортування за спаданням:
    (1) сила стану, (2) свіжіший issue_date (None = найстаріше), (3) Source B
    над Source A (документована перевага — B детальніша), (4) вищий legacy id
    як останній детермінований tie-break."""
    rank = _STATE_RANK.get(c["state"], 0)
    date_key = c["issue_date"] or date.min
    source_key = 1 if c["source"] == "B" else 0
    return (rank, date_key, source_key, c["legacy_id"])


def _get_or_create_channel(env, bucket):
    """Get-or-create the single slide.channel that represents this course
    bucket, tracked by an ir.model.data marker for idempotency. ORM (not raw
    SQL) here on purpose: slide.channel carries several required/derived
    fields (channel_type, enroll, visibility, translate=True name) that the
    ORM already defaults/encodes correctly — hand-rolling that in SQL would
    be brittle for a one-off provisioning step of at most 5 rows."""
    xmlid_name = f"reuse_s1p6_channel_{bucket}"
    channel = env.ref(f"{MODULE}.{xmlid_name}", raise_if_not_found=False)
    if channel:
        return channel
    name, required_hours = _CHANNEL_SPEC[bucket]
    channel = env["slide.channel"].create(
        {
            "name": name,
            "camp_course_type": bucket,
            "required_hours": required_hours,
            "is_men_course": True,
        }
    )
    env["ir.model.data"].create(
        {
            "module": MODULE,
            "name": xmlid_name,
            "model": "slide.channel",
            "res_id": channel.id,
            "noupdate": True,
        }
    )
    return channel


def _insert_keeper_row(cr, partner_id, channel, hours_completed, state,
                        certificate_number, issue_date, expiry_date,
                        session_start_date, session_end_date, session_location,
                        instructor_id, create_uid, create_date, write_uid, write_date):
    """Raw-SQL insert into camp_staff_training_record, manually filling every
    compute(store=True) field the ORM would normally derive (display_name,
    completion_pct, course_type/required_hours mirrors) since a raw INSERT
    bypasses @api.depends. Групи (partner, bucket) вже дедупльовано перед
    викликом цієї функції, тому ON CONFLICT тут — лише захист від НЕЗАЛЕЖНО
    існуючого рядка (напр. вручну створеного адміном), не від дублів у межах
    цієї міграції. Returns (new_id_or_existing_id)."""
    cr.execute("SELECT name FROM res_partner WHERE id = %s", (partner_id,))
    row = cr.fetchone()
    partner_name = row[0] if row else "?"
    display_name = f"{partner_name} — {channel.name}"
    required_hours = channel.required_hours or 0.0
    completion_pct = min(100.0, (hours_completed / required_hours * 100.0) if required_hours else 0.0)

    cr.execute(
        """
        INSERT INTO camp_staff_training_record
            (partner_id, channel_id, display_name, hours_completed, slides_completed,
             completion_pct, state, certificate_number, issue_date, expiry_date,
             course_type, required_hours,
             session_start_date, session_end_date, session_location, instructor_id,
             create_uid, create_date, write_uid, write_date)
        VALUES (%s, %s, %s, %s, 0,
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s)
        ON CONFLICT ON CONSTRAINT camp_staff_training_record_unique_partner_channel
        DO NOTHING
        RETURNING id
        """,
        (
            partner_id, channel.id, display_name, hours_completed,
            completion_pct, state, certificate_number, issue_date, expiry_date,
            channel.camp_course_type, required_hours,
            session_start_date, session_end_date, session_location, instructor_id,
            create_uid, create_date, write_uid, write_date,
        ),
    )
    row = cr.fetchone()
    if row:
        return row[0]
    # Незалежний рядок уже існує (не з цієї міграції) — приєднуємось до нього.
    cr.execute(
        "SELECT id FROM camp_staff_training_record WHERE partner_id = %s AND channel_id = %s",
        (partner_id, channel.id),
    )
    row = cr.fetchone()
    return row[0] if row else None


def _collect_source_b(cr):
    """Зчитує fayna.vozhatyi.training (+module+certificate) у список
    кандидатів (dict), пропускаючи вже мігровані (marker є). Не чіпає
    ir_model_data/INSERT — лише READ, вставка відбувається пізніше централі-
    зовано після дедуплікації."""
    cr.execute("SELECT to_regclass('public.fayna_vozhatyi_training')")
    if not cr.fetchone()[0]:
        return [], 0, 0

    cr.execute(
        """
        SELECT id, name, participant_id, training_type, start_date, end_date,
               location, instructor_id, state, total_hours, certificate_date,
               certificate_number, certificate_id,
               create_uid, create_date, write_uid, write_date
        FROM fayna_vozhatyi_training
        WHERE participant_id IS NOT NULL
        ORDER BY id
        """
    )
    columns = [d[0] for d in cr.description]
    trainings = [dict(zip(columns, row)) for row in cr.fetchall()]

    candidates = []
    reused_b = 0
    for t in trainings:
        marker = f"reuse_s1p6_recB_{t['id']}"
        cr.execute(
            "SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s",
            (MODULE, marker),
        )
        if cr.fetchone():
            reused_b += 1
            continue

        bucket = _TRAINING_TYPE_TO_BUCKET.get(t["training_type"], "specialty")

        issue_date = t["certificate_date"]
        valid_until = None
        certificate_number = t["certificate_number"]
        if t["certificate_id"]:
            cr.execute(
                "SELECT issue_date, valid_until, certificate_number FROM fayna_vozhatyi_certificate WHERE id = %s",
                (t["certificate_id"],),
            )
            cert_row = cr.fetchone()
            if cert_row:
                issue_date = cert_row[0] or issue_date
                valid_until = cert_row[1]
                certificate_number = cert_row[2] or certificate_number

        if t["state"] == "certified":
            new_state = "certified"
        elif t["state"] == "completed":
            new_state = "certified" if certificate_number else "completed"
        elif t["state"] == "in_progress":
            new_state = "in_progress"
        else:
            new_state = "enrolled"

        hours_completed = t["total_hours"] or 0.0

        # module_ids — provenance для WINNER-нотатки (documented granularity
        # loss: keeper не будує окрему модель "модуль").
        cr.execute(
            """
            SELECT name, hours, completed, completion_date
            FROM fayna_vozhatyi_training_module
            WHERE training_id = %s ORDER BY sequence, id
            """,
            (t["id"],),
        )
        modules = cr.fetchall()
        provenance_note = None
        if modules:
            lines = [
                f"{m_name} ({m_hours}h, {'ukończono ' + str(m_date) if m_done else 'nieukończono'})"
                for m_name, m_hours, m_done, m_date in modules
            ]
            provenance_note = "[migracja fayna.vozhatyi.training #%d] Moduły:<br/>%s" % (
                t["id"], "<br/>".join(lines)
            )

        candidates.append(
            {
                "source": "B",
                "legacy_id": t["id"],
                "partner_id": t["participant_id"],
                "bucket": bucket,
                "state": new_state,
                "certificate_number": certificate_number,
                "issue_date": issue_date,
                "expiry_date": valid_until,
                "hours_completed": hours_completed,
                "session_start_date": t["start_date"],
                "session_end_date": t["end_date"],
                "session_location": t["location"],
                "instructor_id": t["instructor_id"],
                "create_uid": t["create_uid"],
                "create_date": t["create_date"],
                "write_uid": t["write_uid"],
                "write_date": t["write_date"],
                "provenance_note": provenance_note,
            }
        )
    return candidates, reused_b, len(trainings)


def _collect_source_a(cr):
    """Зчитує vozhatyi.training.record (флет) у список кандидатів, пропускаючи
    вже мігровані. Аналогічно _collect_source_b — лише READ."""
    cr.execute("SELECT to_regclass('public.vozhatyi_training_record')")
    if not cr.fetchone()[0]:
        return [], 0, 0

    cr.execute(
        """
        SELECT id, partner_id, training_type, completion_date, certificate_number,
               valid_until, notes, state,
               create_uid, create_date, write_uid, write_date
        FROM vozhatyi_training_record
        WHERE partner_id IS NOT NULL
        ORDER BY id
        """
    )
    columns = [d[0] for d in cr.description]
    records = [dict(zip(columns, row)) for row in cr.fetchall()]

    candidates = []
    reused_a = 0
    for r in records:
        marker = f"reuse_s1p6_recA_{r['id']}"
        cr.execute(
            "SELECT res_id FROM ir_model_data WHERE module = %s AND name = %s",
            (MODULE, marker),
        )
        if cr.fetchone():
            reused_a += 1
            continue

        bucket = _TRAINING_TYPE_TO_BUCKET.get(r["training_type"], "specialty")

        if r["state"] == "expired":
            new_state = "expired"
        elif r["state"] == "completed":
            new_state = "certified" if r["certificate_number"] else "completed"
        else:
            new_state = "enrolled"

        required_hours = _CHANNEL_SPEC[bucket][1]
        hours_completed = required_hours if new_state in ("completed", "certified", "expired") else 0.0

        provenance_note = None
        if r["notes"]:
            provenance_note = "[migracja vozhatyi.training.record #%d] %s" % (r["id"], r["notes"])

        candidates.append(
            {
                "source": "A",
                "legacy_id": r["id"],
                "partner_id": r["partner_id"],
                "bucket": bucket,
                "state": new_state,
                "certificate_number": r["certificate_number"],
                "issue_date": r["completion_date"],
                "expiry_date": r["valid_until"],
                "hours_completed": hours_completed,
                "session_start_date": None,
                "session_end_date": None,
                "session_location": None,
                "instructor_id": None,
                "create_uid": r["create_uid"],
                "create_date": r["create_date"],
                "write_uid": r["write_uid"],
                "write_date": r["write_date"],
                "provenance_note": provenance_note,
            }
        )
    return candidates, reused_a, len(records)


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})

    b_candidates, reused_b, total_b = _collect_source_b(cr)
    a_candidates, reused_a, total_a = _collect_source_a(cr)

    if not total_b and not total_a:
        _logger.info("reuse-s1p6: жодної легасі-таблиці немає — нічого переносити")
        return

    groups = {}
    for c in b_candidates + a_candidates:
        groups.setdefault((c["partner_id"], c["bucket"]), []).append(c)

    created = 0
    merged_duplicates = 0
    notes_posted = 0

    for (partner_id, bucket), group in groups.items():
        channel = _get_or_create_channel(env, bucket)
        ranked = sorted(group, key=_candidate_sort_key, reverse=True)
        winner = ranked[0]
        losers = ranked[1:]

        new_id = _insert_keeper_row(
            cr, partner_id, channel, winner["hours_completed"], winner["state"],
            winner["certificate_number"], winner["issue_date"], winner["expiry_date"],
            winner["session_start_date"], winner["session_end_date"],
            winner["session_location"], winner["instructor_id"],
            winner["create_uid"], winner["create_date"], winner["write_uid"], winner["write_date"],
        )
        if new_id is None:
            _logger.warning(
                "reuse-s1p6: не вдалось вставити ні знайти рядок для partner=%s bucket=%s — пропущено",
                partner_id, bucket,
            )
            continue
        created += 1

        # Мітки на ВСІХ кандидатів групи (переможця й програних) вказують на
        # РЕАЛЬНИЙ виграний рядок — повторний прогін коректно розпізнає кожен
        # legacy id як "вже опрацьований", хоч би з якого джерела.
        for c in group:
            marker = f"reuse_s1p6_rec{c['source']}_{c['legacy_id']}"
            cr.execute(
                """
                INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
                VALUES (%s, %s, 'camp.staff.training.record', %s, TRUE)
                ON CONFLICT DO NOTHING
                """,
                (MODULE, marker, new_id),
            )

        if winner["provenance_note"]:
            env["camp.staff.training.record"].browse(new_id).message_post(
                body=winner["provenance_note"]
            )
            notes_posted += 1

        if losers:
            merged_duplicates += len(losers)
            lines = []
            for c in losers:
                detail = (
                    f"Source {c['source']} #{c['legacy_id']}: state={c['state']}, "
                    f"certificate={c['certificate_number'] or '—'}, "
                    f"issue_date={c['issue_date'] or '—'}"
                )
                if c["provenance_note"]:
                    detail += f" ({c['provenance_note']})"
                lines.append(detail)
            env["camp.staff.training.record"].browse(new_id).message_post(
                body="[reuse-s1p6 INC-215] Злиті дублікати (partner, курс) — виживає "
                "найсильніший стан/найсвіжіша дата, решта задокументована тут:<br/>"
                + "<br/>".join(lines)
            )

    _logger.info(
        "reuse-s1p6: sourceB=%d (вже було %d), sourceA=%d (вже було %d), "
        "груп (partner,bucket)=%d → вставлено/приєднано %d, злитих дублікатів %d, "
        "provenance-нотаток дописано %d",
        total_b, reused_b, total_a, reused_a,
        len(groups), created, merged_duplicates, notes_posted,
    )
