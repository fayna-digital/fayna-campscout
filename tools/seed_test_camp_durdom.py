# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# ruff: noqa: F821  — odoo shell: env інжектується в рантаймі
"""SEED тестового табору «ДУРДОМ СОНЕЧКО» — для візуального тесту кіоска/сторінок на STAGING.
Запуск:  cat tools/seed_test_camp_durdom.py | docker exec -i campscout_web \
            odoo shell -c /etc/odoo/odoo.conf -d campscout --no-http
НЕ для прода. Ідемпотентний: якщо табір уже є — нічого не робить.
Дані-наповнювачі — Lorem Ipsum (текст розробників для тесту сторінок),
структурний кістяк (їжа, душ, плавання) — реальний, бо власник просив у програмі.
"""

from datetime import date, datetime, timedelta

LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
)
LOREM_SHORT = "Lorem ipsum dolor sit amet"

CAMP_NAME = "ДУРДОМ СОНЕЧКО"
GROUP_NAMES = ["Палата номер 6", "Чортики", "Водолази", "Наполеони", "Русалки", "Медузи"]
N_CHILDREN = 60
DAYS = 14
START = date(2026, 7, 1)

FIRST = [
    "Adam",
    "Zofia",
    "Jan",
    "Maja",
    "Kacper",
    "Lena",
    "Filip",
    "Zuzia",
    "Szymon",
    "Hania",
    "Mikołaj",
    "Ola",
    "Wojtek",
    "Ala",
    "Igor",
    "Nadia",
    "Олег",
    "Соломія",
    "Назар",
    "Даринка",
    "Остап",
    "Мирослава",
]
LAST = [
    "Nowak",
    "Kowalski",
    "Wiśniewski",
    "Wójcik",
    "Kowalczyk",
    "Kamiński",
    "Шевченко",
    "Коваленко",
    "Бондаренко",
    "Ткачук",
    "Мельник",
    "Поліщук",
]


def _sel0(model, field):
    sel = env[model]._fields[field].selection
    if callable(sel):
        sel = sel(env[model])
    return sel[0][0]


existing = env["event.event"].search([("name", "=", CAMP_NAME)], limit=1)
if existing:
    print(f"SEED: табір вже існує (id={existing.id}) — пропускаю.")
else:
    badge = _sel0("event.event", "badge_format")
    camp = env["event.event"].create(
        {
            "name": CAMP_NAME,
            "date_begin": datetime.combine(START, datetime.min.time()).replace(hour=8),
            "date_end": datetime.combine(START + timedelta(days=DAYS), datetime.min.time()).replace(
                hour=18
            ),
            "badge_format": badge,
        }
    )
    print(f"SEED event id={camp.id} badge={badge}")

    # — Групи —
    groups = []
    for gname in GROUP_NAMES:
        groups.append(env["camp.group"].create({"name": gname, "event_id": camp.id}))
    print(f"SEED groups={len(groups)}")

    # — Батьки + діти (60), по 10 у групу, перший у групі = молодий лідер —
    n_parents = N_CHILDREN // 2
    parents = []
    for i in range(n_parents):
        parents.append(
            env["res.partner"].create(
                {
                    "name": "Rodzic Test %02d %s" % (i + 1, LAST[i % len(LAST)]),
                    "is_company": False,
                    "email": "rodzic.test%02d@example.test" % (i + 1),
                    "phone": "+48 600 %03d %03d" % (i, i),
                }
            )
        )
    leaders_marked = 0
    children = []  # {part, parent, gi, leader} — для чату
    for i in range(N_CHILDREN):
        gi = i % len(groups)
        g = groups[gi]
        is_leader = (i // len(groups)) == 0  # перша «хвиля» = молоді лідери груп
        fn = FIRST[i % len(FIRST)]
        ln = LAST[i % len(LAST)]
        if is_leader:
            fn = "⭐ " + fn
            leaders_marked += 1
        parent = parents[i % n_parents]
        child_partner = env["res.partner"].create(
            {
                "name": f"{fn} {ln}",
                "is_company": False,
            }
        )
        part = env["camp.participant"].create(
            {
                "partner_id": child_partner.id,
                "parent_partner_id": parent.id,
                "first_name": fn,
                "last_name": ln,
                "wzor_version": "2026",
            }
        )
        # реєстрація дитини на табір — ПОТРІБНА перед призначенням у групу (constraint camp_group)
        env["event.registration"].create(
            {
                "event_id": camp.id,
                "participant_id": part.id,
                "partner_id": child_partner.id,
            }
        )
        # — Grupa + Karta kwalifikacyjna (Lorem) + podpis rodzica (audit: data/IP) —
        part.write(
            {
                "group_id": g.id,
                "birth_date": date(2013 + (i % 5), (i % 12) + 1, (i % 27) + 1),  # вік ~9-13
                "allergies": "Alergie: " + LOREM_SHORT,
                "medications": "Leki: " + LOREM_SHORT,
                "chronic_conditions": "Choroby przewlekłe: " + LOREM_SHORT,
                "psycho_behavioral_notes": LOREM,
                "emergency_contact_1_name": parent.name,
                "emergency_contact_1_phone": parent.phone or "+48 600 000 000",
                "emergency_contact_1_relation": "Rodzic",
                "v_health_notes": "Stan zdrowia po turnusie: " + LOREM_SHORT,
                "qualification_signed": True,
                "qualification_signed_date": datetime.now(),
                "qualification_signed_ip": "127.0.0.1",
                "qualification_signed_by_name": parent.name,
                "qualification_signature": "c2lnbmF0dXJl",
            }
        )
        children.append({"part": part, "parent": parent, "gi": gi, "leader": is_leader})
    print(
        f"SEED children={N_CHILDREN} leaders={leaders_marked} parents={n_parents} + karty(Lorem, podpisane)"
    )

    # — Штат: 3 виховники (2 з KRK→доступ, 1 без), 3 волонтери, 1 інструктор плавання —
    df = START
    dt = START + timedelta(days=DAYS)
    # ADR-22 canon role keys.
    staff_spec = [
        ("Wychowawca Anna (KRK ✓)", "wychowawca", True, "Палата номер 6, Чортики"),
        ("Wychowawca Bartek (KRK ✓)", "wychowawca", True, "Водолази, Наполеони"),
        ("Wychowawca Cezary (BEZ KRK)", "wychowawca", False, "Русалки, Медузи"),
        ("Wolontariusz Dawid", "wolontariusz", False, ""),
        ("Wolontariusz Ewa", "wolontariusz", False, ""),
        ("Wolontariusz Franek", "wolontariusz", False, ""),
        ("Instruktor pływania Gosia", "instruktor", True, ""),
    ]
    staff = {}
    for name, role, has_krk, assigned in staff_spec:
        rec = env["camp.staff"].create(
            {
                "name": name,
                "event_id": camp.id,
                "role": role,
                "date_from": df,
                "date_to": dt,
                "assigned_groups": assigned,
            }
        )
        if has_krk:
            # KRK-довідка (zaświadczenie o niekaralności) verified → has_valid_krk=True → §13-допуск
            env["camp.staff.cert"].create(
                {
                    "staff_id": rec.id,
                    "cert_type": "krk",
                    "verification_status": "verified",
                    "issue_date": df - timedelta(days=30),
                    "expiry_date": dt + timedelta(days=365),
                }
            )
        staff[name] = rec
    print(f"SEED staff={len(staff)} (KRK✓={sum(1 for s in staff.values() if s.has_valid_krk)})")

    wychowawcy = [
        staff["Wychowawca Anna (KRK ✓)"],
        staff["Wychowawca Bartek (KRK ✓)"],
        staff["Wychowawca Cezary (BEZ KRK)"],
    ]

    # — 4-разове меню × 14 днів (Lorem) —
    for d in range(DAYS):
        env["camp.menu.day"].create(
            {
                "event_id": camp.id,
                "menu_date": START + timedelta(days=d),
                "breakfast": "Śniadanie — " + LOREM_SHORT,
                "lunch": "Obiad — " + LOREM,
                "afternoon_snack": "Podwieczorek — " + LOREM_SHORT,
                "dinner": "Kolacja — " + LOREM_SHORT,
            }
        )
    print(f"SEED menu_days={DAYS} (4 posiłki)")

    # — Хелпер: побудувати день програми з кістяком + Lorem + ВЕЧІРНІМ ДУШЕМ-ротацією —
    even_groups = "Палата номer 6, Водолази, Русалки"  # 30 дітей
    odd_groups = "Чортики, Наполеони, Медузи"  # 30 дітей

    def build_day(program, d, rainy):
        the_date = START + timedelta(days=d)
        day = env["camp.program.day"].create(
            {
                "program_id": program.id,
                "date": the_date,
                "day_number": d + 1,
                "notes": LOREM_SHORT,
            }
        )
        # парний/непарний день табору (день 1 = непарний)
        is_even_day = (d + 1) % 2 == 0
        shower_groups = even_groups if is_even_day else odd_groups
        acts = [
            (7.0, 7.5, "Pobudka i toaleta poranna", ""),
            (8.0, 8.5, "Śniadanie", ""),
            (
                9.0,
                11.0,
                ("Zajęcia w sali (deszcz): " if rainy else "Kąpiel morska + ") + LOREM_SHORT,
                LOREM,
            ),
            (11.0, 12.5, "Instruktor pływania — grupa dnia: " + LOREM_SHORT, LOREM),
            (13.0, 14.0, "Obiad", ""),
            (14.0, 15.5, "Cisza poobiednia / " + LOREM_SHORT, LOREM),
            (16.0, 18.0, "Zajęcia programowe: " + LOREM, LOREM),
            (18.5, 19.0, "Kolacja", ""),
            (
                20.0,
                20.5,
                "Wieczorny prysznic (limit 30 miejsc) — DZIŚ myją się: " + shower_groups,
                f"Połowa obozu (30 dzieci). Dni nieparzyste: {odd_groups}. Dni parzyste: {even_groups}. {LOREM_SHORT}",
            ),
            (21.5, 22.0, "Cisza nocna", ""),
        ]
        for tf, tt, title, note in acts:
            env["camp.program.activity.line"].create(
                {
                    "day_id": day.id,
                    "time_from": tf,
                    "time_to": tt,
                    "title": title,
                    "notes": note or LOREM_SHORT,
                }
            )
        return day

    # — 2 програми днів: сонячна (звичайна) + дощова —
    prog_sun = env["camp.program.structured"].create({"event_id": camp.id, "state": "published"})
    prog_rain = env["camp.program.structured"].create({"event_id": camp.id, "state": "published"})
    for d in range(DAYS):
        build_day(prog_sun, d, rainy=False)
        build_day(prog_rain, d, rainy=True)
    print(f"SEED programs=2 (sun+rain) × {DAYS} dni z wieczornym prysznicem (rotacja 30/30)")

    # — 3 програми виховників (кожен зі своєю, легша — 3 дні Lorem) —
    for w in wychowawcy:
        pw = env["camp.program.structured"].create({"event_id": camp.id, "state": "draft"})
        for d in range(3):
            day = env["camp.program.day"].create(
                {
                    "program_id": pw.id,
                    "date": START + timedelta(days=d),
                    "day_number": d + 1,
                    "notes": f"Program wychowawcy {w.name} — {LOREM_SHORT}",
                }
            )
            env["camp.program.activity.line"].create(
                {
                    "day_id": day.id,
                    "time_from": 16.0,
                    "time_to": 18.0,
                    "title": f"Zajęcia grupy ({w.name}): {LOREM_SHORT}",
                    "notes": LOREM,
                }
            )
    print("SEED wychowawca_programs=3")

    # — Щоденники per група (2 виховники з доступом ведуть) —
    dstate = _sel0("fayna.camp.dziennik", "state")
    for g in groups:
        env["fayna.camp.dziennik"].create(
            {
                "state": dstate,
                "event_id": camp.id,
                "group_name": g.name,
                "date_start": START,
                "date_end": START + timedelta(days=DAYS),
                "wychowawca_ids": [(6, 0, [wychowawcy[0].id, wychowawcy[1].id])],
            }
        )
    print(f"SEED dzienniki={len(groups)}")

    # — Чат: батьки ↔ виховник (їх групи) + батьки ↔ керівник (discuss, TZ §419/525) —
    Channel = env["discuss.channel"]
    portal_gid = env.ref("base.group_portal").id
    w_users = {}
    for w in wychowawcy:
        login = f"wych.{w.id}@campscout.test"
        u = env["res.users"].search([("login", "=", login)], limit=1)
        if not u:
            u = (
                env["res.users"]
                .with_context(no_reset_password=True)
                .create(
                    {
                        "name": w.name,
                        "login": login,
                        "email": login,
                        "groups_id": [(6, 0, [portal_gid])],
                    }
                )
            )
        w.user_id = u.id
        w_users[w.id] = u
    kier_user = env["res.users"].browse(508)  # kierownik.test@campscout.eu
    gi2w = {
        0: wychowawcy[0],
        1: wychowawcy[0],
        2: wychowawcy[1],
        3: wychowawcy[1],
        4: wychowawcy[2],
        5: wychowawcy[2],
    }
    chat_n = 0
    seen = set()
    for ch in children:
        p = ch["parent"]
        if p.id in seen or len(seen) >= 8:
            continue
        seen.add(p.id)
        if p.email and not env["res.users"].search([("login", "=", p.email)], limit=1):
            env["res.users"].with_context(no_reset_password=True).create(
                {
                    "name": p.name,
                    "login": p.email,
                    "email": p.email,
                    "groups_id": [(6, 0, [portal_gid])],
                }
            )
        w = gi2w[ch["gi"]]
        wu = w_users[w.id]
        c1 = Channel.create({"name": f"Rodzic {p.name} ↔ {w.name}", "channel_type": "group"})
        c1.add_members(partner_ids=[p.id, wu.partner_id.id])
        c1.message_post(
            body="Dzień dobry, mam pytanie o dziecko. " + LOREM_SHORT,
            author_id=p.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        c2 = Channel.create({"name": f"Rodzic {p.name} ↔ Kierownik", "channel_type": "group"})
        c2.add_members(partner_ids=[p.id, kier_user.partner_id.id])
        c2.message_post(
            body="Witam Kierownika obozu. " + LOREM_SHORT,
            author_id=p.id,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        chat_n += 2
    print(f"SEED chat_channels={chat_n} ({len(seen)} rodziców ↔ wychowawca + ↔ kierownik)")

    env.cr.commit()
    print(f"SEED DONE event_id={camp.id} name={CAMP_NAME}")
