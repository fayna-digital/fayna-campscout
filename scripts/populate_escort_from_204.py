# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Міграція: для замовлень з продуктом 204 (Indywidualna asysta) створити
draft camp.escort на кожну дитину+заїзд. Ідемпотентний, DRY_RUN за замовчуванням.

Запуск через odoo shell (НЕ як module data):
  docker exec -i campscout_web odoo shell -c /etc/odoo/odoo.conf -d campscout \
    --no-http < scripts/populate_escort_from_204.py

TZ §5.2/§7. Патерн — scripts/populate_from_bs.py.

ЧОМУ ДВА ШЛЯХИ МАТЧИНГУ (урок write-репетиції 2026-07-01, 26/69 no_match):
escort часто продається ОКРЕМИМ замовленням, а реєстрація дитини живе на
замовленні ТАБОРУ того ж батька. Матчити лише через реєстрації самого
escort-замовлення = пропустити ~38%. Тому:
  1) ПРЯМИЙ шлях — реєстрації escort-замовлення з participant_id (як раніше);
  2) FALLBACK за ДИТИНОЮ — по батькові (order.partner_id) + bs_child_name
     знайти camp.participant серед УСІХ замовлень батька, взяти його
     реєстрацію; якщо в батька рівно одна дитина з однією реєстрацією —
     детермінований матч і без імені.
Кожен no_match друкується З ПРИЧИНОЮ — «непояснених» бути не повинно.
"""

import logging

DRY_RUN = True  # True → лише рахує/друкує, нічого не пише
PRODUCT_204_TMPL = 204

_logger = logging.getLogger("populate_escort_from_204")


def _norm(s):
    return " ".join((s or "").strip().lower().split())


def _tokens(s):
    return tuple(sorted(_norm(s).split()))


def run(env):
    Escort = env["camp.escort"]
    SOL = env["sale.order.line"]
    Participant = env["camp.participant"]
    Registration = env["event.registration"]

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

    has_bs = "bs_child_name" in env["sale.order"]._fields

    def _make(participant, reg):
        """Ідемпотентне створення escort на (participant, registration).
        Повертає 'created' або 'skipped'."""
        exists = Escort.search_count(
            [("participant_id", "=", participant.id), ("registration_id", "=", reg.id)]
        )
        if exists:
            return "skipped"
        if not DRY_RUN:
            with env.cr.savepoint():
                Escort.create(
                    {
                        "participant_id": participant.id,
                        "registration_id": reg.id,
                        "direction": "oba",
                        "state": "draft",
                    }
                )
        return "created"

    created = skipped = 0
    unmatched = []  # (order.name, причина)

    for order in orders:
        # ── Шлях 1: реєстрації самого escort-замовлення з прямим лінком на дитину
        # (populate_from_bs ставить registration.participant_id — правильний лінк,
        #  на відміну від partner-евристики, що для 2+ дітей обирала б не ту).
        regs = Registration.search(
            [("sale_order_id", "=", order.id), ("participant_id", "!=", False)]
        )
        if regs:
            for reg in regs:
                if _make(reg.participant_id, reg) == "created":
                    created += 1
                else:
                    skipped += 1
            continue

        # ── Шлях 2 (fallback): матч за ДИТИНОЮ через усі замовлення батька
        partner = order.partner_id
        if not partner:
            unmatched.append((order.name, "замовлення без partner_id"))
            continue
        children = Participant.search([("parent_partner_id", "=", partner.id)])
        child_name = _norm(order.bs_child_name) if has_bs else ""

        if child_name:
            matches = children.filtered(
                lambda p: _norm(f"{p.first_name} {p.last_name}") == child_name
                or _tokens(f"{p.first_name} {p.last_name}") == _tokens(child_name)
            )
        elif len(children) == 1:
            matches = children  # єдина дитина батька — детерміновано і без імені
        else:
            matches = Participant.browse()

        if not matches:
            reason = (
                f"дитину не знайдено: bs_child_name={order.bs_child_name!r}, "
                f"дітей у батька {partner.display_name!r}: {len(children)}"
            )
            unmatched.append((order.name, reason))
            continue
        if len(matches) > 1:
            unmatched.append(
                (order.name, f"неоднозначно: {len(matches)} дітей з іменем {child_name!r}")
            )
            continue

        participant = matches[0]
        regs2 = Registration.search([("participant_id", "=", participant.id)])
        if not regs2:
            unmatched.append((order.name, f"учасник id={participant.id} без жодної реєстрації"))
            continue
        if len(regs2) > 1:
            unmatched.append(
                (
                    order.name,
                    f"неоднозначно: {len(regs2)} реєстрацій учасника id={participant.id} "
                    f"(events: {regs2.mapped('event_id.name')})",
                )
            )
            continue

        if _make(participant, regs2[0]) == "created":
            created += 1
        else:
            skipped += 1

    print(
        f"Результат: created={created} skipped(існують)={skipped} "
        f"no_match={len(unmatched)}  DRY_RUN={DRY_RUN}"
    )
    for name, reason in unmatched:
        print(f"  NO-MATCH {name}: {reason}")
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
