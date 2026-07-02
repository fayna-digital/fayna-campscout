# ТЗ — fayna_camp_portal (Портал CampScout)

> Spec-driven ТЗ за [REPO_STANDARD](../../fayna-digital-docs/contributing/REPO_STANDARD.md) — 6 областей.
> Owner: Fayna Digital (Volodymyr Shevchenko). Версія модуля: `17.0.4.0.0`.
> Архітектура: **hotel-pattern** — увесь camp-specific код в одному модулі (pivot 2026-06-07, Strangler Fig із `campscout_management`).
> Цей TZ переписано 2026-06-08 зі старого scaffold-шаблону (`fayna_campscout` «thin data layer»), що більше не відображав реальність: модуль — повноцінна система з 27 моделей, ~95% реалізовано.
>
> **Реальний стан (оновлено 2026-06-30, версія `17.0.4.0.0`):** модуль функціонально завершений, на staging ✅, prod ❌. Правові доповнення (P2) і тести критичних шляхів (P3) — **зроблено**; міграційні скрипти (P1) написані й відрепетирувані, але **не виконані на проді**. Додано фічі поза первинним знімком ТЗ: **escort/konwój** (`camp_escort.py`, `/my/escort`), **kiosk-режим** (`controllers/kiosk.py`), **teczka KO** (`teczka_ko.py`), **regulaminy** (`regulamin.py`), **budget** (`budget.py`), **канон ролей ADR-22** (`test_role_canon.py`), **VAT §7**, **CD-інфра** (CI/CD + secrets). Єдине плече, що лишилось — **prod-cutover** (виконати міграцію на проді + human QA green + перший живий деплой). Детальний статус по фазах — у [PLAN.md](PLAN.md).

---

## 1. Objective

Єдиний Odoo-17 модуль управління дитячими таборами CampScout під польське право (Rozp. MEN 30.03.2016, Ustawa Kamilka 2024, RODO, EU 1169/2011). Будується на нативних Odoo-фічах (`mail.thread`, `portal`, `event`, `sale`, `loyalty`, `sms`) замість 21 окремого `fayna_camp_*` модуля.

**Що модуль робить (реально, не scaffold):**
- **6-рольний RBAC** — Organizator / Sales / Kierownik / Wychowawca / Instructor / Parent (+ опційні Medical/Nutrition Officer): record rules + field-level `groups=` на медичних полях (RODO art.9). 13 груп, 170+ ACL.
- **Картка кваліфікаційна** (5 секцій MEN) з підписом батьків.
- **Ustawa Kamilka 2024** — інцидент `severity='kamilka'` обходить SMS opt-in (GDPR art.6.1.d vital interest), 5-хв ескалація через cron + **immutable** Kuratorium notification log.
- **SMS 3-рівнева** (CRITICAL/IMPORTANT/INFO) через `fayna_sms_base` dispatcher; wizard масової розсилки для wychowawcy з cost-guard (100/300 ліміт) + **immutable** audit log (7р).
- **Portal `/my/*`** — кабінет батьків: учасники, реєстрації, лояльність, stories, транспорт, support.
- **Admin dashboard `/admin/dashboard`** — KPI + view-as impersonation через `with_user()` (НЕ `sudo()`) + immutable RODO art.30 log.
- **Бізнес-логіка:** лояльність (banda/platinum/gold), сезони, reviews, installment plans, харчування (EU-14 алергени, дієти, меню), транспорт, stories, навчання (MEN 36h/10h + vozhatyi), звіти/snapshots.
- **i18n:** PL + UA значно розширено (`pl_PL.po` / `uk_UA.po` ~23k рядків кожен станом на 2026-06-30; первинний знімок 08.06 був 374 рядки).

**Що ще scaffold:** `campscout.portal.session` / `campscout.portal.menu` (session-tracking, мінімальні методи).

## 2. Commands

```bash
# --- Lint / format / security (джерело правди — .pre-commit-config.yaml) ---
pre-commit run --all-files            # ruff + ruff-format + OCA + bandit + gitleaks

# --- Тести (Odoo test runner у контейнері; потрібна БД) ---
docker exec campscout_web odoo -c /etc/odoo/odoo.conf -d campscout_test \
  --test-enable --test-tags /fayna_camp_portal --stop-after-init -i fayna_camp_portal

# --- Локальне оновлення модуля (зміна моделей/views/data) ---
docker exec campscout_web odoo -c /etc/odoo/odoo.conf -d campscout \
  -u fayna_camp_portal --stop-after-init && docker restart campscout_web

# --- Деплой #4ZONES (Mac → GitHub → staging → prod) ---
# ssh campscout; cd /opt/campscout/custom-addons/fayna_camp_portal
# git pull && sudo chmod -R o+rX .          # capital X!
# odoo -u fayna_camp_portal --stop-after-init; docker restart campscout_web
```

## 3. Project Structure

```
fayna_camp_portal/
├── __manifest__.py            # 17.0.2.0.0; depends: ...+ fayna_rodo_compliance, fayna_sms_base
├── hooks.py                   # post_init_hook — міграція ir.model.data з absorbed-модулів
├── models/                    # 27 файлів, ~27 моделей (1000+ полів)
│   ├── camp.py                # camp.camp + категорії/активності/FAQ/housing (ядро)
│   ├── participant.py         # camp.participant (дитина) + картка кваліфікаційна
│   ├── operations.py          # staff/сертифікати/journal/program/Kuratorium/reports (найбільший)
│   ├── emergency.py           # camp.incident.report (7-state workflow, 18 дій, SLA)
│   ├── incident_kamilka.py    # _inherit: Ustawa Kamilka vital-interest override
│   ├── incident_notification_log.py  # immutable Kuratorium trail
│   ├── commercial.py          # лояльність/сезони/reviews/installments (sale.order)
│   ├── nutrition.py           # EU-14 алергени/дієти/меню
│   ├── sms.py / sms_notify.py # маршрутизація SMS, priority-aware
│   ├── transport.py / stories.py     # portal.mixin для /my/*
│   ├── training.py / training_vozhatyi.py  # MEN-навчання + сертифікати
│   ├── reports.py             # KPI/marketing snapshots
│   ├── admin_access_log.py / staff_sms_log.py   # IMMUTABLE audit (write/unlink → UserError)
│   └── *_inherit.py / *_extensions.py  # res.partner/res.users/event.event розширення
├── controllers/
│   ├── portal.py              # /my, /my/home, /my/counters (parent, group_portal)
│   └── admin.py               # /admin/dashboard + /admin/as-* (organizator-only)
├── wizards/staff_sms_composer.py     # SMS broadcast wizard (cost-guard + audit)
├── security/  groups.xml (13 груп) · ir.model.access.csv (170+) · record_rules.xml
├── data/      cron.xml · cron_kamilka_escalation.xml · sms_*templates.xml · ir_config_parameter.xml
├── views/     16 XML (backend UI всіх ролей) + menus.xml
├── templates/ portal_templates · portal_chatter · website_templates · admin_dashboard
├── static/    scss/ css/ js/ (portal hero, chat-window fix)
├── i18n/       pl_PL.po · uk_UA.po (374 рядки кожна)
├── tests/      test_scaffold · test_campscout · test_campscout_extended
└── docs/       TZ.md · PLAN.md · CHANGELOG.md · LEGAL_REQUIREMENTS.md · CABINET_STATUS.md
```

## 4. Code Style

- **Odoo 17 конвенції** + OCA pre-commit (ruff, ruff-format, bandit, gitleaks).
- Усі user-facing рядки через `_()` для перекладу (PL/UA — обидві ~100%).
- Бізнес-перевірки → `UserError`/`ValidationError`, обгорнуті у `_()`.
- **Immutable моделі** (audit log) — override `write`/`unlink` із `raise UserError`; ніколи не пом'якшувати.
- **RODO art.9** медичні поля (allergies, medications, doctor_notes, chronic_conditions) — лише через field-level `groups=`; не виводити в загальні views/портал.
- Impersonation — **тільки `with_user()`** (зберігає ACL/record rules), ніколи `sudo()` (обходить RODO).
- `models/__init__.py` — порядок імпорту має значення (`operations` перед `emergency`: `camp.staff` має існувати до `_inherit`, INC-014).
- Mobile audit обов'язковий для будь-яких змін у `/my/*` templates.

## 5. Testing

- Odoo test runner, тег `/fayna_camp_portal`; ціль coverage ≥70% критичних шляхів (master TZ §4.6 ЗАКОН).
- Поточні тести: `test_scaffold` (smoke — модуль ставиться, моделі доступні), `test_campscout` (portal menu, feature flags), `test_campscout_extended` (portal hero values, session, HTTP `/my`).
- **Прогалина (відоме):** немає тестів на критичні правові шляхи — Kamilka escalation cron, SMS cost-guard, immutability audit-логів, field-level RODO access, view-as. Це борг PLAN.md (фаза перед prod-gate).

## 6. Boundaries

- **Один модуль на весь camp-логік** (hotel-pattern). Новий camp-функціонал додається СЮДИ, не в нові `fayna_camp_*`.
- **Горизонтальна інфраструктура — окремо:** `fayna_rodo_compliance` (RODO consent/art.9), `fayna_sms_base`/`fayna_sms_turbosms` (SMS) — reusable, не зливати сюди.
- **Група B (14× `fayna_camp_*` deprecated)** — їхній код ПЕРЕНОСиться сюди, репо не приводяться до стандарту (зникнуть).
- **`campscout_management`** (старий моноліт) ще активний на prod — паралельно, доки не завершимо міграцію даних (~97 клієнтів + 36 дітей; ризик RODO audit trail).
- **Prod-gate (ЗАКОН):** prod лише коли весь модуль на Hetzner staging + human QA green. Зараз: **staging ✅ / prod ❌**.
- НЕ чіпати нативні Odoo-таблиці деструктивно — rollback має лишати ядро Odoo незайманим.

---

## Success Criteria

- [ ] 🔴 Міграція даних `campscout_management → fayna_camp_portal` **виконана на проді** без втрати юр.карток + RODO trail (скрипти готові й відрепетирувані — лишилось виконання).
- [x] Тести критичних правових шляхів (Kamilka, immutability, field-level RODO, RSPTS, escort) — ~25 тест-файлів; формальний coverage ≥70% звести перед gate.
- [x] Картка кваліфікаційна wzór 2026 (Dz.U.2026/704 §10) — поля пункту 9 (12 полів у `participant.py`).
- [x] `camp.incident.register` (§12) + `camp.incident.card` (§11) — `models/incident_card.py`.
- [x] RSPTS-гейт §13 — `camp.staff._check_rspts_before_admission` (кадра draft без weryfikacji KRK/RSPTS).
- [🟡] i18n UA — значно розширено (~23k рядків .po); точний % покриття не зведено.
- [ ] Human QA green на staging → prod-gate знятий.

## Open Questions

- **CHANGELOG биті посилання:** записи 17.0.x посилаються на дорефакторні імена файлів (`camp_participant.py`, `sms_dispatcher.py`, `camp_incident.py`, `admin_dashboard.py`, `sms_broadcast_wizard.py`), яких уже немає (реальні: `participant.py`, `sms.py`, `incident_kamilka.py`, `admin.py`, `staff_sms_composer.py`). Виправити посилання чи лишити як історичний знімок? (поки додано нотатку в CHANGELOG).
- ~~**`api.py` /api/v1/***~~ — ЗАКРИТО 2026-07-02: прибрано (P4.3). Споживачів нуль (портал JS/XML, Astro-сайт, тести — все 0), мобільного застосунку нема; `story_detail` мав IDOR повз consent-gate. Native Odoo: portal `/my/*` покриває батьківські сценарії. Відновлення — з git-історії, коли з'явиться реальний споживач.
- **GitHub репо vs модуль:** remote = `VladSh77/fayna-campscout`, модуль = `fayna_camp_portal`. Лишаємо розбіжність назв чи перейменувати репо?
- ~~**`campscout.portal.session/.menu`**~~ — ЗАКРИТО 2026-07-02: у коді вже не існують (повний grep py/xml/csv — 0 збігів); прибрані попередніми рефакторами.

---

## Reference

- Майстер-ТЗ: [CAMPSCOUT_MASTER_TZ.md](../../fayna-digital-docs/contributing/CAMPSCOUT_MASTER_TZ.md) §16 Phase 7
- Правові норми: [LEGAL_REQUIREMENTS.md](LEGAL_REQUIREMENTS.md) (ITW Niezbędnik Kierownika Wypoczynku 2024)
- Статус кабінету: [CABINET_STATUS.md](CABINET_STATUS.md)
- План реалізації: [PLAN.md](PLAN.md)
