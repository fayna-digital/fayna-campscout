# Reuse-аудит fayna_camp_portal — 2026-07-04

**Питання власника:** портал має складатися з готових модулів Odoo (як галузевий пакет «Hotel»), а не з написаного коду. Скільки з нашого кастомного коду дублює готове?

**Метод:** AST-розтин усіх моделей (не построкове читання) → зіставлення кожної моделі зі стандартними addons Odoo 17 Community (список знято з живого контейнера dnj-demo) та OCA-репозиторіями з гілкою 17.0 (GitHub API). Кожен «є аналог» підтверджений читанням маніфесту/моделі кандидата, не думкою LLM. Артефакт розтину: `dissect.json` (сесійний scratchpad).

## Підсумок у цифрах

| Показник | Значення |
|---|---|
| Python у models/ + wizards/ | 20 794 LOC |
| — з них inherit-розширення стандартних моделей (event, sale, product…) | 3 482 LOC (це і є «цеглини», норм) |
| — з них власні моделі | **15 490 LOC** у 77 моделях |
| 🔴 ЗАМІНИТИ на стандарт/OCA (11 моделей) | **1 898 LOC** |
| 🟡 ЗЛИТИ внутрішні дублікати (11 моделей → 5) | **1 282 LOC** (реально мінус ~640) |
| 🟢 ЛИШИТИ (польський закон + унікальний домен) | 12 310 LOC |
| Мертвих моделей (без жодного посилання) | 0 — всі використовуються |

Реалістична економія: **~2 300–2 500 LOC (~15–16% власних моделей)** — після заміни лишаються тонкі inherit-надбудови (~30% обсягу). Головна вигода не рядки, а те, що підтримку цих ділянок несе спільнота OCA/Odoo, а не ми (баги, security, апгрейд на 18/19).

## 🔴 ЗАМІНИТИ — аналог існує, верифіковано кодом

| Наша модель | LOC | Замінник | Доказ |
|---|---|---|---|
| camp.support.request | 470 | **helpdesk_mgmt** (OCA/helpdesk 17.0) + супутні: `_sla`, `_rating`, `_portal_follower` | маніфест прочитано: depends `mail, portal` — портальні тікети, команди, стадії |
| fayna.payment.installment(.plan/.plan.line) | 364 | **sale_invoice_plan** (OCA/sale-workflow 17.0, Production/Stable) | модель прочитано: `sale.invoice.plan` = installment, plan_date, percent, amount, invoiced-трекінг + візард |
| camp.staff.application | 234 | **hr_recruitment** (стандарт, є в Community) — hr.applicant: кандидат/етапи/відмова | стандартний addons-список з живого Odoo 17 |
| camp.staff.vacancy | 179 | **hr_recruitment** — hr.job (вакансія/статус) | там само |
| camp.loyalty.participant + history | 219 | **loyalty.card/program** (стандарт; вже в наших depends!) + тонкий inherit для tier | поля loyalty.card прочитано в контейнері: partner_id, points, expiration_date |
| camp.review | 181 | **rating / portal_rating** (стандарт) + inherit для highlight/improvement | addons-список; website_sale-відгуки працюють на rating.rating |
| camp.story | 178 | **website_blog** (стандарт) — blog.post: заголовок/контент/теги/публікація + inherit для event_id і тегів учасників | addons-список |
| camp.sms.template | 73 | **sms.template** (стандарт, модуль sms — вже в depends) | поля прочитано в контейнері: name, model_id, body з `translate=True` (мультимова без нашого поля lang) |

⚠️ **Ліцензійне питання (вирішити ДО міграції):** модулі OCA — AGPL-3, наш модуль — OPL-1 (пропрієтарний). Залежність OPL-1-модуля від AGPL-модуля — юридично сіра зона; безпечний шлях — винести інтеграційні inherit-шматки в окремий AGPL-модуль або свідомо прийняти AGPL для цих частин. Це рішення власника, не техніки.

## 🟡 ЗЛИТИ — внутрішні дублікати (ми самі собі написали двічі/тричі)

| Дублікат | LOC | Лишити один |
|---|---|---|
| camp.nutrition ⇄ camp.menu.day — ОБИДВІ «денне меню» (breakfast/lunch/dinner на event+дату) | 131+104 | одну, другу змігрувати й видалити |
| camp.participant.diet ⇄ camp.diet.profile — обидві «діет-профіль з алергенами» | 89+111 | одну |
| camp.program + camp.program.activity + camp.schedule.entry ⇄ camp.program.structured(+day+activity.line) — дві системи програми дня | 324 проти 597 | structured-гілку |
| vozhatyi.training.record ⇄ fayna.vozhatyi.training(+module+certificate) ⇄ camp.staff.training.record — ТРИ системи обліку тренінгів кадри | 125+359+229 | одну; довгостроково — OCA **hr_course** (17.0, верифіковано) |
| camp.stats.snapshot ⇄ camp.analytics.snapshot — два KPI-снапшоти | 140+220 | analytics |
| camp.journal ⇄ camp.daily.report — журнал дня і денний рапорт перекриваються | 114+289 | daily.report (він = §2.11) |

Це найдешевша частина економії: без зовнішніх залежностей і ліцензійних питань — тільки міграція даних і видалення.

## 🟢 ЛИШИТИ — аналогів немає (шукав у стандарті й OCA; польський закон)

- **Ядро:** camp.participant (2 055 — karta kwalifikacyjna, PESEL, RODO art.9), presence.interval, camp.group (art. 92c), camp.escort, camp.transport.
- **Документи MEN/Kuratorium:** fayna.camp.dziennik (Załącznik 5), camp.program.wypoczynku (Załącznik 9), camp.kuratorium.notification (Załącznik 1) + checklist/staff, camp.teczka.ko, camp.regulamin(+ack).
- **Інциденти:** camp.incident.report (protokół powypadkowy), incident.card (Karta Wypadku 16 пкт), incident.register (Rejestr 10 колонок), Kamilka-ескалація, notification.log — юридично різні документи, OCA такого не має (перевірено пошуком по OCA org: helpdesk/mgmtsystem — не те).
- **Кадри табору:** camp.staff(+cert+medical) — це кадра wypoczynku на umowa zlecenie per-турнус, не штатні працівники; міграція на hr.employee можлива (OCA hr_employee_document / hr_employee_medical_examination існують на 17.0 — верифіковано), але тягне важкий модуль hr заради 750 LOC → не рекомендую зараз, переглянути при апгрейді на 18.
- **Бюджет:** camp.budget(+line+category) — це BEP-калькулятор (ціна/дитина, VAT marża, точка беззбитковості), а OCA account_budget_oca — бухгалтерський контроль по аналітичних рахунках. Різне призначення → лишити.
- **SMS-інфра:** dispatcher/routing (мультипровайдер TurboSMS) — наша горизонтальна інфра fayna_sms_base.
- **RODO:** admin.access.log (art.30, 7 років) — лишити.
- **Візарди:** camp.create.wizard (867 — оркестрація «новий табір»), staff_sms_composer (285 — з cost-guard і аудитом).
- Дрібні довідники (category/activity/room.type/faq/season, ~160 LOC сумарно) — дешевші за будь-яку заміну.

## Порядок міграції (пропозиція, кожен пункт = окреме ТЗ + «ок» власника)

1. **Злиття дублікатів** (🟡) — нуль зовнішніх ризиків, мінус ~640 LOC, чистить модель даних. Почати з nutrition/diet (найпростіші).
2. **camp.sms.template → sms.template** і **loyalty → loyalty.card** — залежності вже стоять, стандарт уже в системі.
3. **Вирішити AGPL-питання** → тоді helpdesk_mgmt (support) і sale_invoice_plan (розстрочки).
4. **hr_recruitment** (application+vacancy) — стандарт, без ліцензійних питань, але міграція флоу рекрутації.
5. **stories → website_blog, review → rating** — низький пріоритет (працює, не болить).

## Системний запобіжник (щоб 23k не повторились)

У конвеєр розробки додати **reuse-гейт**: перед створенням будь-якої нової моделі агент зобов'язаний показати результат пошуку аналога (стандартні addons + OCA 17.0) і отримати явне «аналога нема» у ТЗ. Без цього артефакту — нова модель не проходить рев'ю. (Кандидат у docs/TZ.md §6 поруч із [T-5].)

---
*Метод і докази: AST-скрипт по 37 файлах; addons-список з контейнера dnj-demo-web-1 (Odoo 17); OCA перевірено по гілках 17.0 через GitHub API; маніфести/моделі helpdesk_mgmt, sale_invoice_plan, hr_course, hr_employee_medical_examination, sms.template, loyalty.card прочитані дослівно. Аудит read-only: код модуля не змінювався.*
