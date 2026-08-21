# TZ-AUDIT SUMMARY — 2026-08-21

Статус: **MAX_ITER** → **ПОКРАЩЕННЯ ЗАСТОСОВАНО** (2026-08-21)
Файл: /Users/kobzar/Developer/Fayna-Workspace/Projects/fayna_camp_portal/docs/TZ.md
Вимог: 131
Confirmed-знахідок: 183
Scorecard (до покращень): {"appropriate": 1.95, "complete": 1.48, "conforming": 1.82, "correct": 1.9, "feasible": 1.95, "necessary": 1.98, "singular": 1.45, "unambiguous": 1.48, "verifiable": 1.52, "verification_method_pct": 74, "measurable_pct": 52, "ears_pct": 20}
Витрачено: ~$0.29
Артефакти: /Users/kobzar/Developer/Fayna-Workspace/Projects/fayna_camp_portal/docs/tz-audit

## Застосовані покращення (2026-08-21)

План: `TZ_IMPROVE_2026-08-21.md` (200 рядків, MoSCoW). Внесено в `TZ.md`:

- **EARS-критерії: 84** (було ~20% EARS-parsable → тепер кожна ключова вимога має WHEN/IF-THEN формулювання + метод верифікації).
- **Конфлікти: 10/10** критичних розв'язано (F-VAT-2↔F-VAT-4, F-KKW-6↔F-FIN-5, F-RODO-7↔M-4, F-REC-1↔PR-6, F-REC-1a↔F-REC-1, F-I18N-3↔PR-4, F-KSK-2 R4b↔§8 п.1, F-FIN-2↔§8 п.12, F-KAM-2↔§8 п.6, F-RODO-2↔§8 п.8) — кожен з EARS-критерієм розмежування.
- **MoSCoW-пріоритети:** Must (38), Should (8), Could (5) застосовано.
- **Нова NFR-підсекція 5a «Інфраструктура та операції» (N-6..N-10):** health checks/liveness/readiness, observability (метрики/SLO/SLI/error budget), керування секретами, rate-limit на всі публічні форми + retry-backoff, Odoo cron/job-queue. Мікросервісні теми (K8s, queues, sharding, gRPC, CAP тощо) свідомо НЕ застосовні до моноліту — задокументовано в §5a.
- **PR-секція (PR-1..PR-6), GAPS (GAP-2/4/5/7/8), API (API-2/3)** — EARS-критерії додано.

Після покращень: `grep -c "Критерій (EARS)" TZ.md` = 84; `grep -c "Узгодження" TZ.md` = 10; рядків 687.
