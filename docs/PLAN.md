# PLAN — fayna_camp_portal

> План реалізації ТЗ ([TZ.md](TZ.md)) за [REPO_STANDARD](../../fayna-digital-docs/contributing/REPO_STANDARD.md).
> Dependency graph + фази + checkpoints. Оновлювати після кожного закритого пункту.

> **Реальний стан (оновлено 2026-06-30, версія `17.0.4.0.0`):**
> Модуль функціонально завершений, на staging ✅, на prod ❌ (не задеплоєний).
> - **P2 (правові доповнення)** — ✅ зроблено (картка wzór2026, incident.register §12, incident.card §11, RSPTS-гейт §13).
> - **P3 (тести критичних шляхів)** — ✅ зроблено (~25 тест-файлів; coverage-число формально не зведено).
> - **P1 (міграція даних)** — 🟡 скрипти написані й відрепетирувані (lossless, dry-run), але **не виконані на проді**.
> - Додано фічі **поза первинним ТЗ**: escort/konwój, kiosk-режим, teczka KO, regulaminy, budget, канон ролей (ADR-22), VAT §7, CD-інфра (CI/CD + secrets).
> - **Єдине плече, що лишилось — prod-cutover:** виконати міграцію на проді + human QA green + перший живий деплой.

---

## Dependency graph (що від чого залежить)

```
[campscout_management моноліт]  ←── ще активний на prod (97 клієнтів + 36 дітей)
            │
            │  МІГРАЦІЯ ДАНИХ (P1 — скрипти готові, виконання лишилось)
            ▼
[fayna_camp_portal]  ── depends ──▶ fayna_rodo_compliance (RODO consent/art.9)
            │                       fayna_sms_base (SMS dispatcher) ──▶ fayna_sms_turbosms
            │
            ├── Правові моделі (P2) ✅: qualification card wzór2026 · incident.register §12
            │        incident.card §11 · staff RSPTS-гейт §13   ← ЗРОБЛЕНО
            │
            ├── Тести критичних шляхів (P3) ✅ ── ~25 тест-файлів   ← ЗРОБЛЕНО
            │
            └── i18n UA (P4) 🟡 ── значно розширено (pl/uk ~23k рядків .po)

PROD-GATE (ЗАКОН): P1-виконання + human QA green  ⇒  тільки тоді prod
```

---

## Фаза P1 — Міграція даних `campscout_management → portal` 🟡 скрипти готові, виконання лишилось

> Найбільший ризик: втрата юр.карток + RODO audit trail при переносі ~97 клієнтів + 36 дітей.
> Скрипти написані й відрепетирувані (dry-run), на проді ще НЕ виконані.

- [x] **P1.1** Інвентар даних на старих таблицях (`campscout_management`) → `docs/MIGRATION_MAP.md`.
- [x] **P1.2** Mapping старих моделей → нові (`camp.participant`, `res.partner`, consent) → `MIGRATION_MAP.md` + `MIGRATION_BACK.md`.
- [x] **P1.3** Міграційні скрипти (idempotent, dry-run): `populate_from_bs.py`, `migrate_bs_signatures.py`, `populate_escort_from_204.py`, `populate_children_and_events.py`, `populate_step2/step3.py`, `detach_campscout_management.py`, `migrations/17.0.4.0.0/post-migrate.py`.
- [ ] **P1.4** 🔴 **Виконати на проді** + звірка контрольних сум: к-сть записів до/після, цілісність RODO trail, бекап перед запуском.
- **Checkpoint:** 0 втрачених карток, RODO trail повний, `campscout_management` від'єднано → P1 done.

## Фаза P2 — Правові доповнення (wzór 2026 / Ustawa Kamilka) ✅ ЗРОБЛЕНО

- [x] **P2.1** Картка кваліфікаційна wzór 2026 (Dz.U.2026/704 §10) — поля п.9 (12 полів у `participant.py`: hydrophobia, fear_of_heights, choroby przewlekłe, soczewki, dieta, emocje…).
- [x] **P2.2** `camp.incident.register` (§12) — Rejestr Wypadków (`models/incident_card.py:494`).
- [x] **P2.3** `camp.incident.card` (§11) — Karta Wypadku (`models/incident_card.py:49`).
- [x] **P2.4** RSPTS-гейт §13 — `camp.staff._check_rspts_before_admission`: кадра draft до верифікації KRK/RSPTS (`staffing.py`, `recruitment.py`, `operations.py:217`).
- **Checkpoint:** ✅ усі поля/моделі присутні, views + ACL + record rules налаштовані.

## Фаза P3 — Тести критичних правових шляхів ✅ ЗРОБЛЕНО (coverage-число звірити)

> Раніше — лише smoke/portal. Тепер ~25 тест-файлів критичних шляхів.

- [x] **P3.1** Kamilka / native approval — `test_native_approval.py`, `test_signoff_rodo.py`.
- [x] **P3.2** SMS / staffing / registration seats — `test_staffing.py`, `test_registration_seats.py`.
- [x] **P3.3** Immutability — `test_rodo_consent_immutable.py`.
- [x] **P3.4** RODO field-level art.9 — `test_art9_access.py`; роль-канон — `test_role_canon.py`.
- [ ] **P3.5** 🟡 Формальний coverage ≥70% — тести є, але `QUALITY_AUDIT_*.md` зі звітом покриття перед gate ще треба згенерувати.
- **Checkpoint:** критичні правові інваріанти під тестом ✅; coverage-число — перед prod-gate.

## Фаза P4 — i18n + polish (паралельно) 🟡

- [x/🟡] **P4.1** UA локалізація — значно розширена (`i18n/uk_UA.po` ~23k рядків, pl_PL.po ~23k); точний % покриття не зведено.
- [ ] **P4.2** Portal `/my/*` mobile audit (обов'язковий перед go-live).
- [ ] **P4.3** Прибрати/задокументувати scaffold: `campscout.portal.session/.menu`, `api.py /api/v1/*`.

## Фаза P5 — Prod-gate 🔴 (єдине плече, що лишилось)

- [🟡] **P5.1** CD-інфра — ✅ `ci.yml` (lint/security гейт), `deploy-staging.yml` (safe deploy: clear .pyc / gated migration / wait-for-green / rollback), `e2e.yml` (Playwright), усі 6 secrets задані. ❌ Лишилось: перший живий прогон deploy+E2E; persistence staging SSH-key (Hetzner Console); юніт-тести Odoo в CI-гейт (зараз тільки lint); прод-стадія в конвеєрі.
- [ ] **P5.2** Виконати P1.4 (міграція на проді) + human QA green по всіх ролях.
- [ ] **P5.3** Виправити биті посилання в CHANGELOG (див. Open Questions TZ).
- **Checkpoint (ЗАКОН):** P1.4 виконано + QA green → deploy prod.

---

## Зв'язки

- [TZ.md](TZ.md) · [LEGAL_REQUIREMENTS.md](LEGAL_REQUIREMENTS.md) · [CABINET_STATUS.md](CABINET_STATUS.md)
- Kanban: [[projects/kanban]] §🟠 CampScout ядро · §🔵 перенесення Групи B
- [CAMPSCOUT_MASTER_TZ.md](../../fayna-digital-docs/contributing/CAMPSCOUT_MASTER_TZ.md) §16
