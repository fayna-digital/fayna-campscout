# populate_step2_groups_budgets.py — MIGRATION_BACK кроки 4.2 + 4.4:
# для кожного event з реєстраціями: групи (auto-split §2) + budget(analytic) + teczka KO.
# Запуск: cat scripts/populate_step2_groups_budgets.py | docker exec -i campscout_web \
#   odoo shell -c /etc/odoo/odoo.conf -d campscout --no-http
# Idempotent: подія з групами/бюджетом/teczką пропускається.

DRY_RUN = True

Event = env["event.event"].sudo()  # noqa: F821
Group = env["camp.group"].sudo()  # noqa: F821
Teczka = env["camp.teczka.ko"].sudo()  # noqa: F821

events = Event.search([("registration_ids.state", "in", ("open", "done"))])
print(f"Подій з реєстраціями: {len(events)}")

g_made = b_made = t_made = skipped = errors = 0
for ev in events:
    try:
        with env.cr.savepoint():  # noqa: F821
            # групи §2 (лише якщо ще нема жодної на події)
            if not Group.search_count([("event_id", "=", ev.id)]):
                if not DRY_RUN:
                    Group.action_auto_split(ev)
                g_made += 1
            else:
                skipped += 1
            # бюджет + analytic (метод сам idempotent)
            if not ev.camp_budget_ids:
                if not DRY_RUN:
                    ev.action_open_budget()
                b_made += 1
            # teczka KO
            if not Teczka.search_count([("event_id", "=", ev.id)]):
                if not DRY_RUN:
                    Teczka.create({"event_id": ev.id})
                t_made += 1
    except Exception as e:  # noqa: BLE001
        errors += 1
        print(f"ERROR {ev.name}: {type(e).__name__}: {e}")

print(
    f"ПІДСУМОК: groups_split={g_made} budgets={b_made} teczki={t_made} "
    f"skip={skipped} errors={errors} | DRY_RUN={DRY_RUN}"
)
if not DRY_RUN:
    env.cr.commit()  # noqa: F821
    print("COMMITTED")
