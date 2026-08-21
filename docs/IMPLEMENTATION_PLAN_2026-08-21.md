# План впровадження ТЗ — fayna_camp_portal (код → тести → перевірка)

_Дата: 2026-08-21 · База: `docs/TZ.md` (покращене) + `docs/CODE_TZ_COMPLIANCE_2026-08-21.md` · Мета: закрити розриви код↔ТЗ і пройти prod-gate §10_

## 0. Принципи
- **Spec-driven**: кожна вимога має EARS-критерій приймання + метод верифікації (test/inspection/demo) + MoSCoW.
- **Traceability**: кожен PR мапує вимогу↔тест (метрика: 0 orphans, 100% критичних).
- **Reuse-first**: Community-only; OCA виключено (AGPL vs OPL-1).
- **CI-гейти**: ruff/bandit/gitleaks/OCA + Odoo unit-тести + e2e Playwright.
- **No-Manual-DB**: зміни через міграції, asset-only → бамп версії (PR-4).

## 1. Фаза 0 — Базлайн і трасування (0.5 дн)
- [ ] Зафіксувати поточний стан: coverage, orphans, verification-method coverage (з `TZ_METRICS`).
- [ ] Створити/оновити CI-скрипт map req↔test (фаза trace tz-audit loop).
- [ ] **Checkpoint:** базлайн зафіксовано, метрики в `docs/tz-audit/`.

## 2. Фаза 1 — Prod-gate блокери (Must) (пріоритет №1)

### 2.1 P1.4 — Міграція даних на проді
- [ ] Виконати скрипти (готові, dry-run відрепетирувано): `populate_from_bs.py`, `migrate_bs_signatures.py`, `populate_escort_from_204.py`, `populate_children_and_events.py`, `populate_step2/step3.py`, `detach_campscout_management.py`, `migrations/17.0.4.0.0/post-migrate.py`.
- [ ] Бекап перед запуском; звірка контрольних сум (row-count до/після, RODO trail).
- [ ] **Checkpoint:** 0 втрачених карток, RODO trail повний, `campscout_management` від'єднано.

### 2.2 F-RODO-7 — Шифрування at-rest + бекапи + ротація + аудит-лог
- [ ] Розбити на 5 під-вимог (singular): DB-шифрування, filestore, бекапи, ротація ключів, аудит-лог.
- [ ] Код: конфіг шифрування, політика бекапів, ротація, аудит-лог доступу.
- [ ] Тест: `test_rodo7_at_rest.py` (перевірка шифрування, бекап-циклу, ротації).
- [ ] **Checkpoint:** тест зелений; аудит-лог пише кожен доступ.

### 2.3 F-KKW-6 / F-FIN-5 — Реальний refund (замість заглушки)
- [ ] Замінити `_schedule_refund` (`participant.py:1668`) на реальний механізм повернення.
- [ ] Edge cases: часткові оплати, комісії платіжних систем, конкурентні скасування.
- [ ] Тест: `test_refund_real.py` (успіх + гілка помилки).
- [ ] **Checkpoint:** refund виконується, не лише логується.

### 2.4 N-6 — Health-check ендпоінт
- [ ] Додати `/healthz` (liveness) + `/readyz` (readiness) у `controllers/`.
- [ ] Тест: `test_health_check.py` (200 на liveness, готовність залежить від стану).
- [ ] **Checkpoint:** ендпоінт відповідає, CI перевіряє.

### 2.5 N-7 — Observability (SLO/SLI, метрики)
- [ ] Додати метрики (prometheus-формат) для ключових SLO: SMS-доставка, cron-цикли, ескалації Kamilka.
- [ ] Тест: `test_observability.py` (наявність метрик, формат).
- [ ] **Checkpoint:** метрики експортуються, SLO/SLI визначені.

### 2.6 T-5 — Visual AI gate
- [ ] Налаштувати e2e Playwright + AI-перевірку скріншотів ключових екранів.
- [ ] **Checkpoint:** гейт у CI, скріншоти проходять.

### 2.7 M-6 — DR-drill
- [ ] Документувати рівні rollback (DB, filestore, конфіг) + критерії приймання кожного рівня.
- [ ] Провести drill на staging.
- [ ] **Checkpoint:** кожен рівень відкату підтверджено.

### 2.8 F-RODO-4 / F-RODO-6 — Erasure wizard + UODO export
- [ ] Майстер видалення даних суб'єкта (мапінг полів, каскад).
- [ ] Експорт даних (art.15) з вимірними критеріями повноти колонок.
- [ ] Тест: `test_rodo_erasure.py`, `test_rodo_export.py`.
- [ ] **Checkpoint:** wizard + export працюють, тести зелені.

## 3. Фаза 2 — Should (пріоритет №2)
- [ ] **F-WIZ-7** high-risk camps — позначення + обробка high-risk активностей; тест.
- [ ] **F-KKW-3** signed_pdf_hash — хеш підписаного PDF; тест.
- [ ] **N-9** загальний rate-limit + retry-backoff (розширити з `admin.py:605`); тест.
- [ ] **F-MY-5** `/my/preferences` сторінка (sms_opt_in, marketing); тест.
- [ ] **F-DOC-3 / F-DOC-4** send to inspector + retention cron; тест.

## 4. Фаза 3 — Could (пріоритет №3)
- [ ] **F-COM-4** DM chat батько↔виховник (розширити `event_channel_create.py`); тест.
- [ ] **F-FIN-4** rejestr faktur за місяць (замість TODO `budget.py:22`); тест.
- [ ] **F-SALE-2** Offer 2026 canon; тест.
- [ ] **N-10** job-queue; тест.
- [ ] **F-I18N-3** формалізований i18n-процес (TMS, CI-перевірка осиротілих ключів).

## 5. Фаза 4 — Тестування та верифікація (наскрізно)
- [ ] **Unit-тести**: кожна нова вимога → тест; coverage ≥70% (зараз 59%).
- [ ] **e2e Playwright**: критичні шляхи по ролях (parent, wychowawca, kierownik, organizator).
- [ ] **Human QA**: всі ролі, mobile audit `/my/*` (P4.2).
- [ ] **CI-гейти**: ruff, bandit, gitleaks, OCA, unit, e2e — все зелено.
- [ ] **Traceability**: 0 orphans, 100% критичних вимог з тестом.
- [ ] **Checkpoint (ЗАКОН):** P1.4 виконано + QA green + CI green → deploy prod.

## 6. Фаза 5 — Prod-gate та деплой
- [ ] Deploy staging → smoke → prod (конвеєр `deploy-staging.yml` + прод-стадія).
- [ ] Після деплою: health-check, метрики, моніторинг.
- [ ] **Checkpoint:** prod живий, SLO виконуються, DR-drill пройдено.

## 7. Метрики успіху (з TZ_METRICS)
| Метрика | Зараз | Ціль |
|---|---|---|
| Coverage тестів | 59% | ≥70% |
| Orphans | 43 | 0 |
| Verification-method coverage | 74% | 100% |
| Вимірність | 52% | ≥90% |
| Spec-drift | — | 0 нових |
| DoD-виконання | — | 100% закритих з доказом |

## 8. Ризики
- **P1.4** — міграція на проді без збоїв (критерій M-4 "без жодного збою" невимірний → задати поріг).
- **F-RODO-7** — шифрування at-rest може конфліктувати з M-4 (прод живий без нейтралізації) → узгодити порядок.
- **F-VAT-2 vs F-VAT-4** — конфлікт режимів VAT zw. vs marża → рішення власника.
- **F-REC-1 vs PR-6** — конфлікт політики (власна рекрутація) → рішення власника.
