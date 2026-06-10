# populate_from_bs.py — MIGRATION_BACK крок 4.3: bs_* (sale_order) → camp.participant
#
# Запуск НА STAGING (odoo shell, БД вже нейтралізована):
#   cat scripts/populate_from_bs.py | docker exec -i campscout_web \
#       odoo shell -c /etc/odoo/odoo.conf -d campscout --no-http
#
# Режим: DRY_RUN=True — лише звіт, нічого не пише. Перемкнути вручну після звірки.
# Idempotent: реєстрації, що вже мають participant_id, пропускаються.
# Картки зі старого checkout = wzór 2021 (przepis przejściowy §2 Dz.U.2026/704),
# qualification_signed=True (підпис вже існує на PDF), PDF → ir.attachment.

import logging
import re
from datetime import date

DRY_RUN = True


def parse_bs_date(raw):
    """bs_birth_date — varchar зі старого checkout: 'DD.MM.YYYY', 'DD.MM.YY',
    або лише 'YYYY' (стара картка питала тільки rok urodzenia).
    Рік → 31.12 (мінімальний можливий вік → суворіший ліміт §2 — безпечний бік).
    """
    if not raw:
        return False
    raw = raw.strip()
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", raw)
    if m:
        d, mo, y = int(m[1]), int(m[2]), int(m[3])
        try:
            return date(y, mo, d)
        except ValueError:
            return False
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{2})", raw)
    if m:
        d, mo, y = int(m[1]), int(m[2]), 2000 + int(m[3])
        try:
            return date(y, mo, d)
        except ValueError:
            return False
    m = re.fullmatch(r"(\d{4})", raw)
    if m:
        return date(int(m[1]), 12, 31)
    return False

_logger = logging.getLogger("populate_from_bs")

SO = env["sale.order"].sudo()  # noqa: F821 (env інжектиться odoo shell)
Reg = env["event.registration"].sudo()  # noqa: F821
Participant = env["camp.participant"].sudo()  # noqa: F821
Attachment = env["ir.attachment"].sudo()  # noqa: F821

orders = SO.search(
    [
        ("bs_child_name", "!=", False),
        ("state", "in", ("sale", "done")),
    ],
    order="id",
)
print(f"SO з даними дитини (bs_child_name): {len(orders)}")

created = skipped_done = no_reg = errors = 0
report = []

for so in orders:
    # реєстрація цього замовлення (event_sale зв'язує через sale_order_id)
    regs = Reg.search(
        [("sale_order_id", "=", so.id), ("state", "in", ("open", "done"))]
    )
    if not regs:
        no_reg += 1
        report.append(f"NO-REG  SO {so.name}: '{so.bs_child_name}' — реєстрації нема")
        continue

    for reg in regs:
        if reg.participant_id:
            skipped_done += 1
            continue

        # ПІБ: останнє слово = прізвище (польська конвенція 'Imię Nazwisko')
        full = (so.bs_child_name or "").strip()
        parts = full.rsplit(" ", 1)
        first = parts[0] if len(parts) == 2 else full
        last = parts[1] if len(parts) == 2 else "(brak nazwiska)"

        birth = parse_bs_date(so.bs_birth_date)
        vals = {
            "first_name": first,
            "last_name": last,
            "birth_date": birth,
            "parent_partner_id": so.partner_id.id,
            "wzor_version": "2021",  # старий checkout = wzór 2021, immutable
            # bs_parents_phone → обов'язковий контакт НС (правило перед підписом)
            "emergency_contact_1_name": (so.bs_parents_names or so.partner_id.name or "")[:128],
            "emergency_contact_1_phone": (so.bs_parents_phone or so.partner_id.phone or "")[:64],
            # меддані зі старої форми — як текст (структуровані pkt9 = лише wzór 2026)
            "chronic_conditions": so.bs_child_health_info or False,
            "special_needs": so.bs_child_needs or False,
            "vacc_other": so.bs_child_vaccination_info or False,
            "passport_number": so.bs_passport_number or False,
        }

        if DRY_RUN:
            created += 1
            pdf = "PDF" if so.bs_qualification_form_pdf else "—"
            report.append(f"CREATE  SO {so.name}: {first} {last} [{pdf}] → reg {reg.id}")
            continue

        try:
            # savepoint: SQL-помилка однієї ітерації не ламає всю транзакцію
            # (InFailedSqlTransaction — INC staging 11.06)
            with env.cr.savepoint():  # noqa: F821
                if not birth and so.bs_birth_date:
                    # дата не розпарсилась — зберегти сирий текст, не губити
                    vals["special_needs"] = (
                        (vals.get("special_needs") or "")
                        + f"\n[migracja] data urodzenia (raw): {so.bs_birth_date}"
                    ).strip()
                child = Participant.create(vals)
                # bs_qualification_form_pdf = Many2one ir.attachment (integer!)
                # → копія attachment на учасника (оригінал лишається на SO)
                pdf_att = (
                    Attachment.browse(so.bs_qualification_form_pdf.id)
                    if so.bs_qualification_form_pdf
                    else Attachment
                )
                if pdf_att and pdf_att.exists():
                    pdf_att.copy(
                        {
                            "name": f"Karta_kwalifikacyjna_2021_{first}_{last}_{so.name}.pdf",
                            "res_model": "camp.participant",
                            "res_id": child.id,
                        }
                    )
                    # підпис уже існує на папері/PDF → фіксуємо (signed ПІСЛЯ
                    # create — protection блокує write лише ПІСЛЯ signed)
                    child.write(
                        {
                            "qualification_signed": True,
                            "qualification_signed_date": so.bs_qc_date or so.date_order,
                        }
                    )
                reg.participant_id = child.id
                created += 1
        except Exception as e:  # noqa: BLE001 — повний звіт важливіший за зупинку
            errors += 1
            report.append(f"ERROR   SO {so.name}: {type(e).__name__}: {e}")

print("\n".join(report[:60]))
print(
    f"\nПІДСУМОК: created={created} skipped(вже є)={skipped_done} "
    f"no_reg={no_reg} errors={errors} | DRY_RUN={DRY_RUN}"
)
if not DRY_RUN:
    env.cr.commit()  # noqa: F821
    print("COMMITTED")
