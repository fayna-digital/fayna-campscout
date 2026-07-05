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

Конфлікт унікальності (partner_id, channel_id) — якщо ОБИДВІ легасі-моделі
мали запис на той самий (partner, відро): Source B (детальніша) переноситься
ПЕРШОЮ, Source A пропускається при конфлікті (ON CONFLICT DO NOTHING) — задо-
кументована розбіжність (S1-4), не блокер (дані лише staging-тестові,
STEP1_TZ контекст даних §10 — прод модуля не встановлений).

Ідемпотентність — ir_model_data-мітки (reuse_s1p6_recA_<id> / reuse_s1p6_recB_
<id> / reuse_s1p6_channel_<course_type>), той самий патерн, що в парах 1/3/5.
"""
import logging

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
    bypasses @api.depends. ON CONFLICT on the keeper's own
    unique_partner_channel constraint makes this idempotent-safe even across
    the two source tables. Returns (new_id_or_None, partner_name)."""
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
    # conflict: another source already claimed this (partner, channel) slot
    cr.execute(
        "SELECT id FROM camp_staff_training_record WHERE partner_id = %s AND channel_id = %s",
        (partner_id, channel.id),
    )
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})

    cr.execute("SELECT to_regclass('public.fayna_vozhatyi_training')")
    has_source_b = bool(cr.fetchone()[0])
    cr.execute("SELECT to_regclass('public.vozhatyi_training_record')")
    has_source_a = bool(cr.fetchone()[0])

    if not has_source_a and not has_source_b:
        _logger.info("reuse-s1p6: жодної легасі-таблиці немає — нічого переносити")
        return

    created_b = reused_b = created_a = reused_a = skipped_a_conflict = 0
    notes_posted = 0

    # ── Source B (детальніша): fayna.vozhatyi.training (+module+certificate) ──
    if has_source_b:
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
            channel = _get_or_create_channel(env, bucket)

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

            new_id = _insert_keeper_row(
                cr, t["participant_id"], channel, hours_completed, new_state,
                certificate_number, issue_date, valid_until,
                t["start_date"], t["end_date"], t["location"], t["instructor_id"],
                t["create_uid"], t["create_date"], t["write_uid"], t["write_date"],
            )
            if new_id is None:
                continue
            created_b += 1

            cr.execute(
                "INSERT INTO ir_model_data (module, name, model, res_id, noupdate) VALUES (%s, %s, 'camp.staff.training.record', %s, TRUE)",
                (MODULE, marker, new_id),
            )

            # module_ids — chatter provenance (documented granularity loss: no
            # separate "module" model on the keeper, slide.channel/slide.slide
            # already natively covers per-lesson breakdown).
            cr.execute(
                """
                SELECT name, hours, completed, completion_date
                FROM fayna_vozhatyi_training_module
                WHERE training_id = %s ORDER BY sequence, id
                """,
                (t["id"],),
            )
            modules = cr.fetchall()
            if modules:
                lines = [
                    f"{m_name} ({m_hours}h, {'ukończono ' + str(m_date) if m_done else 'nieukończono'})"
                    for m_name, m_hours, m_done, m_date in modules
                ]
                env["camp.staff.training.record"].browse(new_id).message_post(
                    body="[migracja fayna.vozhatyi.training #%d] Moduły:<br/>%s"
                    % (t["id"], "<br/>".join(lines))
                )
                notes_posted += 1

    # ── Source A (флет): vozhatyi.training.record ──
    if has_source_a:
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
            channel = _get_or_create_channel(env, bucket)

            if r["state"] == "expired":
                new_state = "expired"
            elif r["state"] == "completed":
                new_state = "certified" if r["certificate_number"] else "completed"
            else:
                new_state = "enrolled"

            hours_completed = (channel.required_hours or 0.0) if new_state in ("completed", "certified", "expired") else 0.0

            new_id = _insert_keeper_row(
                cr, r["partner_id"], channel, hours_completed, new_state,
                r["certificate_number"], r["completion_date"], r["valid_until"],
                None, None, None, None,
                r["create_uid"], r["create_date"], r["write_uid"], r["write_date"],
            )
            if new_id is None:
                skipped_a_conflict += 1
                continue
            created_a += 1

            cr.execute(
                "INSERT INTO ir_model_data (module, name, model, res_id, noupdate) VALUES (%s, %s, 'camp.staff.training.record', %s, TRUE)",
                (MODULE, marker, new_id),
            )

            if r["notes"]:
                env["camp.staff.training.record"].browse(new_id).message_post(
                    body="[migracja vozhatyi.training.record #%d] %s" % (r["id"], r["notes"])
                )
                notes_posted += 1

    _logger.info(
        "reuse-s1p6: sourceB trainings=%d (створено %d, вже було %d), "
        "sourceA records=%d (створено %d, вже було %d, конфлікт-пропущено %d), "
        "chatter-нотаток дописано %d",
        len(trainings) if has_source_b else 0, created_b, reused_b,
        len(records) if has_source_a else 0, created_a, reused_a, skipped_a_conflict,
        notes_posted,
    )
