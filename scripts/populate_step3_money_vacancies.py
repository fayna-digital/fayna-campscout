# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# populate_step3_money_vacancies.py — MIGRATION_BACK 4.4 + автоштат:
#  (1) posted-фактури → analytic табору (реальні оплати у план-vs-факт бюджету);
#  (2) _sync_staff_vacancies по всіх заїздах (кадри=0 → вакансії = потреба §2);
#  (3) скелет camp.program.wypoczynku де нема.
# Запуск: cat scripts/populate_step3_money_vacancies.py | docker exec -i campscout_web \
#   odoo shell -c /etc/odoo/odoo.conf -d campscout --no-http
# Idempotent: analytic_distribution не перезаписується; вакансії дедупляться двигуном.

DRY_RUN = True

Event = env["event.event"].sudo()  # noqa: F821
Reg = env["event.registration"].sudo()  # noqa: F821
Program = env["camp.program.wypoczynku"].sudo()  # noqa: F821

events = Event.search([("registration_ids.state", "in", ("open", "done"))])
print(f"Заїздів: {len(events)}")

inv_lines_tagged = vac_created = prog_created = errors = 0

for ev in events:
    try:
        with env.cr.savepoint():  # noqa: F821
            budget = ev.camp_budget_ids[:1]
            analytic = budget.analytic_account_id
            # --- (1) фактури → analytic ---------------------------------
            if analytic:
                sos = Reg.search(
                    [("event_id", "=", ev.id), ("state", "in", ("open", "done"))]
                ).mapped("sale_order_id")
                inv_lines = sos.invoice_ids.filtered(
                    lambda m: m.move_type == "out_invoice" and m.state == "posted"
                ).invoice_line_ids.filtered(lambda line: not line.analytic_distribution)
                if not DRY_RUN and inv_lines:
                    inv_lines.write({"analytic_distribution": {str(analytic.id): 100}})
                inv_lines_tagged += len(inv_lines)
            # --- (2) вакансії §2 -----------------------------------------
            before = (
                env["camp.staff.vacancy"]
                .sudo()
                .search_count(  # noqa: F821
                    [("event_id", "=", ev.id)]
                )
            )
            if not DRY_RUN:
                ev._sync_staff_vacancies()
            after = (
                env["camp.staff.vacancy"]
                .sudo()
                .search_count(  # noqa: F821
                    [("event_id", "=", ev.id)]
                )
            )
            vac_created += after - before
            # --- (3) програма-скелет -------------------------------------
            if not Program.search_count([("event_id", "=", ev.id)]):
                if not DRY_RUN:
                    Program.create({"event_id": ev.id})
                prog_created += 1
    except Exception as e:  # noqa: BLE001
        errors += 1
        print(f"ERROR {ev.name}: {type(e).__name__}: {e}")

print(
    f"ПІДСУМОК: invoice_lines_tagged={inv_lines_tagged} vacancies_created={vac_created} "
    f"programs_created={prog_created} errors={errors} | DRY_RUN={DRY_RUN}"
)
if not DRY_RUN:
    env.cr.commit()  # noqa: F821
    print("COMMITTED")
