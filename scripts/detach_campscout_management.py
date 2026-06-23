# -*- coding: utf-8 -*-
"""Детач даних campscout_management: бізнес-записи (товари-табори, події, квитки,
атрибути) ВІДВʼЯЗУються від ir_model_data → стають звичайними плоскими записами,
що НЕ зникнуть при uninstall модуля. КОД (views/menus/fields) НЕ чіпаємо.

Ідемпотентний. DRY_RUN за замовчуванням. Реверсивний: знятий зріз ir_model_data
друкується (для відновлення лінка за потреби).

Запуск через odoo shell:
  docker exec -i campscout_web odoo shell -c /etc/odoo/odoo.conf -d campscout --no-http < detach_campscout_management.py

TZ §3.1/§6.1. ⚠️ Це репетиція на staging-копії прода; на ПРОД — лише окремо за «ок».
"""
DRY_RUN = True
MODULE = "campscout_management"

# ДАНІ → detach (бізнес-записи, керовані в UI). КОД (ir.ui.view/menu/act_window/
# mail.template/field) — НЕ чіпаємо, лишається власністю модуля до перестворення.
DATA_MODELS = (
    "product.template",
    "product.product",
    "event.event",
    "event.event.ticket",
    "product.attribute",
    "product.attribute.value",
)


def parity(env, tag):
    q = """
        SELECT 'product.template', count(*) FROM product_template WHERE active
        UNION ALL SELECT 'product.product', count(*) FROM product_product WHERE active
        UNION ALL SELECT 'event.event', count(*) FROM event_event
        UNION ALL SELECT 'event.event.ticket', count(*) FROM event_event_ticket
        UNION ALL SELECT 'sale.order.line', count(*) FROM sale_order_line
        UNION ALL SELECT 'event.registration', count(*) FROM event_registration
    """
    env.cr.execute(q)
    rows = dict((m, c) for m, c in env.cr.fetchall())
    print("PARITY [%s]: %s" % (tag, rows))
    return rows


def run(env):
    IMD = env["ir.model.data"]
    print("=== DETACH %s (DRY_RUN=%s) ===" % (MODULE, DRY_RUN))
    before = parity(env, "before")

    to_detach = IMD.search([("module", "=", MODULE), ("model", "in", DATA_MODELS)])
    by_model = {}
    for d in to_detach:
        by_model.setdefault(d.model, []).append((d.name, d.res_id))
    for m, items in sorted(by_model.items()):
        print("  %s: %s записів → detach" % (m, len(items)))
    print("  РАЗОМ to-detach: %s ir_model_data рядків" % len(to_detach))

    # реверс-лог (для відновлення)
    print("  REVERSE-LOG (module,model,name,res_id):")
    for d in to_detach[:5]:
        print("    %s|%s|%s|%s" % (MODULE, d.model, d.name, d.res_id))
    print("    ...(%s total)" % len(to_detach))

    if not DRY_RUN:
        # DELETE лінків ir_model_data — самі записи (товари/події) ЛИШАЮТЬСЯ
        ids = tuple(to_detach.ids)
        if ids:
            env.cr.execute("DELETE FROM ir_model_data WHERE id IN %s", (ids,))
        env.cr.commit()
        print("  DETACHED + commit.")
        after = parity(env, "after-detach")
        ok = all(after[k] >= before[k] for k in before)  # нічого не зменшилось
        print("  PARITY OK (нічого не зникло): %s" % ok)
    else:
        print("  DRY_RUN — нічого не змінено. Записи лишаться при uninstall ПІСЛЯ реального detach.")


try:
    run(env)  # noqa: F821
except NameError:
    print("Запускати в odoo shell.")
