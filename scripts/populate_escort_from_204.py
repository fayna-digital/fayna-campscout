# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Міграція: для замовлень з продуктом 204 (Indywidualna asysta) створити
draft camp.escort на кожну дитину+заїзд. Ідемпотентний, DRY_RUN за замовчуванням.

Запуск через odoo shell (НЕ як module data):
  docker exec -i campscout_web odoo shell -c /etc/odoo/odoo.conf -d campscout \
    --no-http < scripts/populate_escort_from_204.py

TZ §5.2/§7. Патерн — scripts/populate_from_bs.py.
⚠️ [ПРИПУЩЕННЯ] точний звʼязок event.registration ↔ camp.participant звіряється
   на staging (M0): нижче використано registration.partner_id == participant.partner_id.
   Перед commit-прогоном підтвердити реальні поля.
"""

import logging

DRY_RUN = True  # True → лише рахує/друкує, нічого не пише
PRODUCT_204_TMPL = 204

_logger = logging.getLogger("populate_escort_from_204")


def run(env):
    Escort = env["camp.escort"]
    SOL = env["sale.order.line"]

    # order lines з продуктом 204 у підтверджених замовленнях
    lines = SOL.search(
        [
            ("product_id.product_tmpl_id", "=", PRODUCT_204_TMPL),
            ("order_id.state", "in", ("sale", "done")),
        ]
    )
    orders = lines.mapped("order_id")
    print(f"Order-lines з product_tmpl_id={PRODUCT_204_TMPL}: {len(lines)}")
    print(f"Замовлень з продуктом 204 (sale/done): {len(orders)}")
    if not lines:
        # Fail-loud: якщо жодного рядка — 204 майже напевно НЕ той продукт на цій БД
        # (id product_template відрізняється між середовищами). Не мовчати.
        tmpl = env["product.template"].browse(PRODUCT_204_TMPL)
        tmpl_name = tmpl.name if tmpl.exists() else "<не існує>"
        print(
            f"⚠️ УВАГА: 0 order-lines з product_tmpl_id={PRODUCT_204_TMPL}. Перевір реальний "
            f"id продукту «Indywidualna asysta» на цій БД перед прогоном. "
            f"product_template[{PRODUCT_204_TMPL}].name={tmpl_name!r}"
        )

    created = skipped = no_match = 0
    for order in orders:
        # реєстрації цього замовлення з ПРЯМИМ звʼязком на дитину
        # (populate_from_bs ставить registration.participant_id — правильний лінк,
        #  на відміну від partner-евристики, що для 2+ дітей обирала б не ту).
        regs = env["event.registration"].search(
            [("sale_order_id", "=", order.id), ("participant_id", "!=", False)]
        )
        if not regs:
            no_match += 1
            continue
        for reg in regs:
            participant = reg.participant_id
            # ідемпотентність: вже є escort на (participant, registration)?
            exists = Escort.search_count(
                [("participant_id", "=", participant.id), ("registration_id", "=", reg.id)]
            )
            if exists:
                skipped += 1
                continue
            if DRY_RUN:
                created += 1
                continue
            with env.cr.savepoint():
                Escort.create(
                    {
                        "participant_id": participant.id,
                        "registration_id": reg.id,
                        "direction": "oba",
                        "state": "draft",
                    }
                )
                created += 1

    print(
        f"Результат: created={created} skipped(існують)={skipped} no_match={no_match}  DRY_RUN={DRY_RUN}"
    )
    if not DRY_RUN:
        env.cr.commit()
        print("COMMIT виконано.")
    else:
        print("DRY_RUN — нічого не записано. Постав DRY_RUN=False для застосування.")


# odoo shell контекст: env уже доступний
try:
    run(env)  # noqa: F821
except NameError:
    print("Запускати в odoo shell (env недоступний поза ним).")
