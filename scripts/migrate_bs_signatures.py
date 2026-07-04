# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""⚠️ DEPRECATED — НЕ ВКЛЮЧАТИ У МІГРАЦІЙНИЙ ПРОЦЕС БЕЗ РІШЕННЯ CTO. ⚠️

Цей скрипт цілиться в поле sale.order.bs_parents_signature, якого на проді НЕ ІСНУЄ.
Реальна схема campscout_management має рівно 21 поле bs_* на sale_order (звірено
2026-07-01 проти прода / переліку ПЕРЕВІРЕНИХ ФАКТІВ) — окремого поля підпису серед
них немає. Підпис батьків зберігається УСЕРЕДИНІ PDF-картки bs_qualification_form_pdf,
яку вже переносить scripts/populate_from_bs.py (копіює attachment на camp.participant і
ставить qualification_signed=True). Тобто перенос підписів НЕ є окремою прогалиною —
він виконується разом із PDF.

Наслідок: у DRY_RUN цей скрипт читає order.bs_parents_signature → AttributeError буде
проковтнутий except-ом як «read FAIL» і кожна реєстрація потрапить у nosig; у реальному
прогоні він не перенесе жодного підпису (переносити нема чого — поля немає).

РІШЕННЯ CTO (винесено у звіт, тут НЕ виконується): вилучити цей скрипт із міграц-
процесу як застарілий (підпис уже покривається populate_from_bs через PDF), або —
якщо коли-небудь зʼявиться окреме binary-поле підпису — переписати під його реальну назву.
Ідемпотентність/патерн лишаються нижче лише як історичний зразок; за замовчуванням DRY_RUN.

--- історичний опис (недійсний, поле відсутнє) ---
§5.6 — перенос живих підписів → camp.participant.qualification_signature.
Лінк: registration.participant_id (populate_from_bs) → order = registration.sale_order_id.
"""

# ⚠️ DEPRECATED-гейт: поле bs_parents_signature не існує на проді. Скрипт залишено як
# no-op, щоб випадковий запуск нічого не робив і голосно повідомляв про причину.
DEPRECATED = True

DRY_RUN = True

if DEPRECATED:
    # Поле-джерело bs_parents_signature на проді відсутнє; підпис уже переноситься
    # через PDF у populate_from_bs.py. Не виконувати логіку — лише повідомити CTO.
    raise SystemExit(
        "migrate_bs_signatures.py DEPRECATED: sale.order.bs_parents_signature не існує "
        "(21 реальних bs_* полів без окремого підпису; підпис — у bs_qualification_form_pdf, "
        "переноситься populate_from_bs.py). Рішення про вилучення з процесу — за CTO. "
        "Щоб примусово запустити історичну логіку, вручну зніми DEPRECATED=True."
    )

Reg = env["event.registration"].sudo()  # noqa: F821
migrated = skipped = nosig = noreg = 0
regs = Reg.search([("participant_id", "!=", False)])
print(f"registrations з participant: {len(regs)}")
for reg in regs:
    order = reg.sale_order_id
    part = reg.participant_id
    if not order:
        noreg += 1
        continue
    try:
        sig = order.bs_parents_signature
    except Exception as e:
        print(f"  read FAIL order {order.id}: {str(e)[:80]}")
        nosig += 1
        continue
    if not sig:
        nosig += 1
        continue
    if part.qualification_signature:
        skipped += 1
        continue
    if DRY_RUN:
        migrated += 1
        continue
    part.sudo().write({"qualification_signature": sig})
    migrated += 1

print(
    f"ПІДСУМОК: migrated={migrated} skipped(вже є)={skipped} no_signature={nosig} no_order={noreg} | DRY_RUN={DRY_RUN}"
)
if not DRY_RUN:
    env.cr.commit()  # noqa: F821
    print("COMMIT.")
