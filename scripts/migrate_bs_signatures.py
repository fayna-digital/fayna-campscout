# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""§5.6 — перенос живих підписів bs_parents_signature (sale.order, Binary attachment)
→ camp.participant.qualification_signature. Прогалина, якої populate_from_bs НЕ робить
(він переносить лише PDF). Без цього 107 підписів лишаються тільки в legacy-полі.

Лінк: registration.participant_id (populate_from_bs) → order = registration.sale_order_id.
Ідемпотентний (пропускає participant, що вже має підпис). DRY_RUN за замовч.
Запуск через odoo shell (як admin → immutability обходиться для signed-карток).
Потребує filestore на staging (Binary читається з файлу).

Критерій приймання: count(bs_parents_signature) ≈ count(qualification_signature) після.
"""

DRY_RUN = True

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
