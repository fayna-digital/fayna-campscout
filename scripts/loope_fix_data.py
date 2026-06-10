# loope_fix_data.py — LOOP-E ітерація 1, фіксери даних F1/F2/F4.
#   F1: PESEL у passport_number → поле pesel + СПРАВЖНЯ дата народження + стать.
#   F2: транслітерація імен КМУ-2010 (урядові документи — ЛИШЕ латинкою, вимога user).
#   F4: учасники для всіх open/done реєстрацій без participant_id (чернетки без дати)
#       + budget/teczka/program для ВСІХ active подій.
# Запуск (ПІСЛЯ -u модуля: birth_date вже optional!):
#   sed DRY_RUN → False | docker exec -i campscout_web odoo shell -d campscout --no-http
# Idempotent.

import re
from datetime import date

DRY_RUN = True

# Транслітерація КМУ-2010 (постанова №55 від 27.01.2010, паспортна)
_KMU = {
    "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e",
    "є": "ie", "ж": "zh", "з": "z", "и": "y", "і": "i", "ї": "i", "й": "i",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "shch", "ь": "", "ю": "iu", "я": "ia", "'": "", "’": "",
}


def translit(text):
    out = []
    for i, ch in enumerate(text):
        low = ch.lower()
        if low in _KMU:
            t = _KMU[low]
            # початок слова: Є→Ye, Ї→Yi, Й→Y, Ю→Yu, Я→Ya
            if i == 0 or not text[i - 1].isalpha():
                t = {"є": "ye", "ї": "yi", "й": "y", "ю": "yu", "я": "ya"}.get(low, t)
            out.append(t.capitalize() if ch.isupper() and t else t)
        else:
            out.append(ch)
    return "".join(out)


def pesel_parse(p):
    """PESEL → (date, gender) або (None, None). Чексума + декада століття."""
    if not re.fullmatch(r"\d{11}", p or ""):
        return None, None
    w = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
    if (10 - sum(int(p[i]) * w[i] for i in range(10)) % 10) % 10 != int(p[10]):
        return None, None
    yy, mm, dd = int(p[0:2]), int(p[2:4]), int(p[4:6])
    if 1 <= mm <= 12:
        year = 1900 + yy
    elif 21 <= mm <= 32:
        year, mm = 2000 + yy, mm - 20
    elif 41 <= mm <= 52:
        year, mm = 2100 + yy, mm - 40
    else:
        return None, None
    try:
        born = date(year, mm, dd)
    except ValueError:
        return None, None
    gender = "m" if int(p[9]) % 2 else "f"  # selection: m/f/x (grep!)
    return born, gender


P = env["camp.participant"].sudo()  # noqa: F821
Reg = env["event.registration"].sudo()  # noqa: F821
Event = env["event.event"].sudo()  # noqa: F821
Group = env["camp.group"].sudo()  # noqa: F821
Teczka = env["camp.teczka.ko"].sudo()  # noqa: F821
Program = env["camp.program.wypoczynku"].sudo()  # noqa: F821

f1 = f2 = f4_kids = f4_events = errors = 0
report = []

# --- F1: PESEL з паспорта ---------------------------------------------------
for child in P.search([("passport_number", "=like", "___________")]):  # 11 симв.
    born, gender = pesel_parse(child.passport_number)
    if not born:
        report.append(f"F1-SKIP {child.display_name}: 11 цифр, але не PESEL (чексума)")
        continue
    vals = {"pesel": child.passport_number, "passport_number": False, "birth_date": born}
    if not child.gender:
        vals["gender"] = gender
    if not DRY_RUN:
        try:
            with env.cr.savepoint():  # noqa: F821
                child.write(vals)
        except Exception as e:  # noqa: BLE001
            errors += 1
            report.append(f"F1-ERR {child.display_name}: {e}")
            continue
    f1 += 1

# --- F2: транслітерація КМУ ---------------------------------------------------
CYR = re.compile(r"[а-яА-ЯіїєґІЇЄҐ]")
for child in P.search([]):
    if CYR.search(child.first_name or "") or CYR.search(child.last_name or ""):
        new_f, new_l = translit(child.first_name or ""), translit(child.last_name or "")
        note = f"[migracja] оригінал кирилицею: {child.first_name} {child.last_name}"
        if not DRY_RUN:
            try:
                with env.cr.savepoint():  # noqa: F821
                    child.write(
                        {
                            "first_name": new_f,
                            "last_name": new_l,
                            "special_needs": ((child.special_needs or "") + "\n" + note).strip(),
                        }
                    )
            except Exception as e:  # noqa: BLE001
                errors += 1
                report.append(f"F2-ERR {child.display_name}: {e}")
                continue
        f2 += 1
        report.append(f"F2 {child.first_name} {child.last_name} → {new_f} {new_l}")

# --- F4a: діти з голих реєстрацій ---------------------------------------------
for reg in Reg.search(
    [("state", "in", ("open", "done")), ("participant_id", "=", False)]
):
    raw = (reg.name or "").strip() or "(brak imienia)"
    parts = raw.rsplit(" ", 1)
    first = translit(parts[0]) if CYR.search(parts[0]) else parts[0]
    last = (
        (translit(parts[1]) if CYR.search(parts[1]) else parts[1])
        if len(parts) == 2
        else "(brak nazwiska)"
    )
    vals = {
        "first_name": first,
        "last_name": last,
        "parent_partner_id": reg.partner_id.id,
        "emergency_contact_1_name": reg.partner_id.name or "",
        "emergency_contact_1_phone": reg.phone or reg.partner_id.phone or "",
        # birth_date невідома — чернетка; підпис заблокує гейт
    }
    if not DRY_RUN:
        try:
            with env.cr.savepoint():  # noqa: F821
                child = P.create(vals)
                reg.participant_id = child.id
        except Exception as e:  # noqa: BLE001
            errors += 1
            report.append(f"F4a-ERR reg{reg.id} '{raw}': {e}")
            continue
    f4_kids += 1

# --- F4b: усі ACTIVE події мають budget/teczka/program -------------------------
for ev in Event.search([("active", "=", True)]):
    try:
        with env.cr.savepoint():  # noqa: F821
            made = []
            if not ev.camp_budget_ids:
                if not DRY_RUN:
                    ev.action_open_budget()
                made.append("budget")
            if not Teczka.search_count([("event_id", "=", ev.id)]):
                if not DRY_RUN:
                    Teczka.create({"event_id": ev.id})
                made.append("teczka")
            if not Program.search_count([("event_id", "=", ev.id)]):
                if not DRY_RUN:
                    Program.create({"event_id": ev.id})
                made.append("program")
            if made:
                f4_events += 1
                report.append(f"F4b {ev.name}: +{'+'.join(made)}")
    except Exception as e:  # noqa: BLE001
        errors += 1
        report.append(f"F4b-ERR {ev.name}: {type(e).__name__}: {e}")

print("\n".join(report[:40]))
print(
    f"\nПІДСУМОК: F1_pesel={f1} F2_translit={f2} F4_kids={f4_kids} "
    f"F4_events={f4_events} errors={errors} | DRY_RUN={DRY_RUN}"
)
if not DRY_RUN:
    env.cr.commit()  # noqa: F821
    print("COMMITTED")
