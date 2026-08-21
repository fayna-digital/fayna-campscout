# Звіт відповідності коду ТЗ — fayna_camp_portal

_Дата: 2026-08-21 · Модуль: `fayna_camp_portal` v17.0.4.1.8 · База: `docs/TZ.md` (покращена 2026-08-21, EARS + MoSCoW + NFR 5a)_

## 1. Резюме

Перевірено фактичний код проти покращеного ТЗ (131 вимога). Метод — grep/інспекція критичних шляхів у `models/`, `controllers/`, `wizards/`, `data/`, `migrations/`, `tests/`, `.github/workflows/`.

**Висновок:** код в цілому відповідає ТЗ на рівні реалізованих вимог (✅/🟡), але **покращене ТЗ додало нові критерії (EARS-приймання, NFR 5a N-6..N-10, MoSCoW), які ще НЕ мають коду/тестів**. Найбільші розриви — нові NFR 5a (health-check, observability, secrets, rate-limit, job-queue) та prod-gate блокери (F-RODO-7, F-RODO-4, F-RODO-6, F-KKW-6 refund, T-5, M-6 DR-drill).

## 2. Підтверджені розриви код ↔ ТЗ

### 2.1 🔴 НЕ реалізовано (код відсутній)

| Вимога | Очікування (ТЗ) | Факт у коді | Доказ |
|---|---|---|---|
| **N-6** health check | liveness/readiness ендпоінт | Відсутній `/healthz`/`/readyz` | grep 0 збігів |
| **N-7** observability | SLO/SLI, метрики, трейси | Відсутній prometheus/otel/grafana | grep 0 збігів |
| **F-RODO-4** erasure wizard | Майстер видалення даних суб'єкта | Лише `camp.create.wizard`; erasure-майстра немає | `wizards/` 2 файли |
| **F-RODO-6** UODO export | Експорт даних (art.15) | Відсутній | grep 0 збігів |
| **F-RODO-7** шифрування at-rest | DB/filestore шифрування, бекапи, ротація, аудит-лог | Відсутній код | grep 0 збігів |
| **F-WIZ-7** high-risk camps | Позначення та обробка high-risk активностей | Лише алерген-ризик у `nutrition.py:94` | grep |
| **F-KKW-3** signed_pdf_hash | Хеш підписаного PDF | Лише хешування телефонів у `sms.py:31` | grep |
| **F-COM-4** DM chat | Прямий чат батько↔виховник | Лише auto-create staff `discuss.channel` (`event_channel_create.py`) | grep |
| **T-5** visual AI gate | Візуальний AI-гейт скріншотів | Відсутній | grep 0 збігів |
| **M-6** DR-drill | Disaster-recovery drill, рівні rollback | Відсутній | grep 0 збігів |
| **F-FIN-4** rejestr faktur | Реєстр фактур за місяць | Лише TODO-коментар | `budget.py:22` |
| **F-SALE-2** Offer 2026 canon | Відповідність канону Offer 2026 | Не доведено | grep 0 збігів |

### 2.2 🟡 Частково (заглушка / неповно)

| Вимога | Стан | Доказ |
|---|---|---|
| **F-KKW-6** refund | **Заглушка**: `_schedule_refund` лише логує зобов'язання, реального повернення немає | `participant.py:1668-1685` |
| **N-8** secrets | Файл `telegram_secrets.env` є, але vault/ротації немає | `document_submission.py:32` |
| **N-9** rate-limit | Лише login-as rate-limit (10/5хв); загального rate-limit/retry-backoff немає | `admin.py:605` |
| **N-10** cron/job-queue | Cron є (auto_refusal, medication, training), job-queue немає | `data/cron.xml` |
| **F-DOC-3** send to inspector | Модель kuratorium notification є, але дії "надіслати" немає | `operations.py:3279` |
| **F-DOC-4** retention cron | 7y retention на рівні моделі; cron-purge "на рівні платформи, не модуля" | `admin_access_log.py:11` |
| **F-VAT-4** VAT-marża | Поля marża в `budget.py` є; invoice-level VAT-marża не підтверджено | `budget.py:68` |
| **F-MY-5** preferences | `sms_opt_in` на `res.partner` є; сторінки `/my/preferences` не знайдено | `res_partner_inherit.py:25` |
| **F-I18N-3** process | `.po` є (pl/uk ~23k); формалізованого процесу немає | `i18n/` |

## 3. Що відповідає (✅ підтверджено кодом)

- **RBAC 6 ролей** — `security/groups.xml`, `ir.model.access.csv`, `record_rules.xml`; роль-канон `_role_taxonomy.py` (ADR-22).
- **Ustawa Kamilka** — `incident_kamilka.py` (5-хв ескалація, immutable kuratorium log), `incident_card.py` (§11), `incident_register` (§12).
- **Karta kwalifikacyjna wzór 2026** — `participant.py` (12 полів п.9), `teczka_ko.py`.
- **Program Wypoczynku (Załącznik 9)** — `operations.py:1572` (6 секцій).
- **Kuratorium Zgłoszenie (Załącznik 1)** — `operations.py:3279` + checklist.
- **SMS трирівневий** — `sms_notify.py` (CRITICAL/IMPORTANT/INFO, opt-in override), `staff_sms_log.py` (immutable).
- **RODO art.9 field-level** — `art9_security.py`, `medication.py` (груповий гейт).
- **Immutable audit** — `admin_access_log.py`, `staff_sms_log.py` (7y retention).
- **Native Odoo reuse** — mail.thread, portal, event, sale, discuss.channel.
- **Тести** — 43 `test_*.py` + `e2e/`; CI `ci.yml` (lint + unit-тести), `deploy-staging.yml`, `e2e.yml`.

## 4. Метрики відповідності (базлайн з TZ_METRICS)

| Метрика | Базлайн | Ціль |
|---|---|---|
| Traceability coverage | 100% | 100% критичних, ≥70% всіх |
| Orphans (тести без вимоги) | 43 | 0 |
| Verification-method coverage | 74% | 100% |
| Вимірність (числа/пороги) | 52% | ≥90% |
| EARS-parsable | 20% | — |
| Coverage тестів | 59% (07-02) | ≥70% |

## 5. Пріоритетні розриви для впровадження (MoSCoW)

**Must (блокери prod-gate §10):**
1. **P1.4** — виконати міграцію на проді (скрипти готові, dry-run відрепетирувано).
2. **F-RODO-7** — шифрування at-rest + бекапи + ротація + аудит-лог (5 під-вимог).
3. **F-KKW-6 / F-FIN-5** — реальний refund замість заглушки `_schedule_refund`.
4. **N-6** — health-check ендпоінт (liveness/readiness).
5. **N-7** — observability (SLO/SLI, метрики).
6. **T-5** — visual AI gate.
7. **M-6** — DR-drill.
8. **F-RODO-4 / F-RODO-6** — erasure wizard + UODO export.

**Should:**
9. **F-WIZ-7** — high-risk camps.
10. **F-KKW-3** — signed_pdf_hash.
11. **N-9** — загальний rate-limit + retry-backoff.
12. **F-MY-5** — `/my/preferences` сторінка.
13. **F-DOC-3 / F-DOC-4** — send to inspector + retention cron.

**Could:**
14. **F-COM-4** — DM chat батько↔виховник.
15. **F-FIN-4** — rejestr faktur.
16. **F-SALE-2** — Offer 2026 canon.
17. **N-10** — job-queue.
18. **F-I18N-3** — формалізований i18n-процес.

## 6. Джерела
- `docs/TZ.md` — канонічне ТЗ (покращене 2026-08-21).
- `docs/tz-audit/TZ_AUDIT_2026-08-21.md`, `TZ_IMPROVE_2026-08-21.md`, `TZ_METRICS_2026-08-21.md`, `SUMMARY.md`.
- `docs/PLAN.md` — фази P1-P5.
- Фактичний код: `models/`, `controllers/`, `wizards/`, `data/`, `migrations/`, `tests/`, `.github/workflows/`.
