> ⚠️ **SUPERSEDED 2026-07-02** — актуальне джерело істини: єдиний `docs/TZ.md`. Цей датований зріз лишено як історію; при конфлікті — пріоритет `TZ.md`. (REPO_STANDARD: один живий ТЗ, не кілька версій.)

# ТЗ — `fayna_camp_portal`: Production + Sellable Odoo-grade

| Поле | Значення |
|---|---|
| **Статус** | АВТОРИТЕТНЕ. Заміняє застарілі: майстер-ТЗ §1.3/§3.1 (до-pivot, 32 модулі, 71%) і `CABINET_STATUS.md` (до-pivot). У конфлікті — пріоритет цьому документу. |
| **Дата** | 2026-06-23 |
| **Автор** | Claude (CTO) для Fayna Digital — Volodymyr Shevchenko |
| **Базис** | 3 аудити цієї сесії (docs / код 79 моделей / живий staging) + **доведена lossless-міграція на прод-копії** (114 дітей, 97 підписів, detach+uninstall = 0 втрат). |
| **Governance** | #4ZONES (Mac→GitHub→staging→prod), prod-gate ЗАКОН, RODO HIGH/life-critical, людина-в-петлі на 2 точках (деплой, фінал RODO). |

---

## 1. Бачення і планка якості

`fayna_camp_portal` — **єдиний** Odoo 17 модуль (hotel-pattern): повна операційно-юридична платформа для проведення дитячих таборів у Польщі.

**Планка = ПРОДАВАНИЙ Odoo-модуль** (Odoo App Store / OCA-grade), не «працює в нас»:
- стандартний manifest + структура (категорія, версія, опис, images, depends, license), розгортання `-i`/`-u` як будь-який Odoo-модуль;
- **тести ≥70%** критичних шляхів (ЗАКОН майстер-ТЗ §4.6);
- **повна i18n** (.pot + PL/UA/EN, без порожніх/франкенштейнів);
- **чисті доки** (README, технічна, user-guide, CHANGELOG, App-Store index);
- **lint/OCA** чисто (pre-commit, pylint-odoo);
- security/RODO-аудит; чистий install **і** upgrade.

**Робочий цикл:** staging = верстат (чистимо → дописуємо → **тестуємо**) → прод = полірований реліз.

---

## 2. Скоуп, ролі, юр-вимоги

**Ролі (14 груп RBAC):** Organizator, Sales, Kierownik, Wychowawca, Instructor, Parent + надбудови Medical / Nutrition / HR / Emergency / Finance (Księgowa). Кожна — свій інтерфейс під Odoo за логіном (record-rules + per-role views + impersonation організатором).

**Юридично ОБОВ'ЯЗКОВЕ влітку (без цього табір нелегальний):**
- Zgłoszenie wypoczynku do Kuratorium (за 21/14/7 дн) — **подається вручну** (zgł. 25366/WIE/L-2026), не блокер коду.
- Karta kwalifikacyjna **wzór 2026** (Dz.U.2026/704, Zał.6) + przepis przejściowy 2021.
- Weryfikacja RSPTS кадри ПЕРЕД допуском (Ustawa Kamilka).
- Pisemne Standardy Ochrony Małoletnich; Dziennik zajęć (Zał.5); Rejestr + Karta wypadku (**16 пунктів**, не 7); ліміти груп art.92c; RODO art.8/9 (field-level).
- Карти/RODO/транспорт/щоденники/програма — **табори без них працювати не можуть**.

---

## 3. Поточний стан (аудит коду + живий staging)

**Збудовано нативно (~79 моделей):** participant/karta (wzór 2026 + 2021 switch + 18 полів pkt 9), dziennik (Zał.5), incidents + Ustawa Kamilka (escalation cron, immutable log, Karta/Rejestr §11-12), transport, nutrition, budget (BEP/marża), staffing (art.92c, RSPTS), regulamin, teczka KO, training/vozhatyi, stories, loyalty, escort (dozwoła+RODO), звіти організатора (`camp.report` агрегація), **нативний потік продаж→квиток→реєстрація→учасник** (`commercial.py`: `_init_camp_registrations`, `_fayna_get_or_create_participant`).

**Живий staging (прод-копія):** портал installed, /shop+booking цілі (239 замовлень, 277 реєстрацій), 115 учасників + 44 escort мігровано; решта операційних даних = 0 (система не обкатана наповненням).

**Сезон:** турнуси йдуть з 27.06 (Дослідники морів), щільний липень, серпень.

---

## 4. BonSens → власна розробка (Strangler)

| Що робив BonSens | Стан |
|---|---|
| Квитки/реєстрації на продаж, авто-учасник, картка | ✅ **нативно вже** (commercial.py + camp.participant; місцями краще — wzór 2026) |
| product↔подія лінк (bs_camp_id/bs_event_id) | ✅ замінено нативним event_ticket/product-матчингом |
| **Місця/seats з продажів** (bs `_compute_seats`) | ⚠️ **ДОРОБИТИ** (портал на стандартних event-seats) |
| Підпис організатора (res.company) | ⚠️ **ДОРОБИТИ** (перенести джерело в портал-звіт) |
| Перенос даних дітей/підписів | ✅ rehearsed; ⏳ product-лінки 42/59 + organizer-sig перед uninstall |

**Лідові модулі:** `bs_apix_drive_lead` = мертвий (0 лідів) → архівовано `DevJournal/learning/bonsens-archive/`, uninstall восени. `bs_lead_form_for_site` + `bs_crm_lead_work_days` — маркетинг-трек (work_days за майстер-ТЗ «лишається»).

**Decommission (осінь, окреме вікно):** detach product-links → uninstall `bs_campscout_addon` + `campscout_management`. Доведено lossless.

---

## 5. Season-completion (що дописати)

1. Нативний **підпис карти батьками в порталі** (`/my/participants/<id>` детальна + sign-route; метод `sign_qualification()` готовий) — під Strangler покрито старою bs-формою, тож не блокер.
2. **UI згоди RODO/фото** в кабінеті батьків (методи готові, route нема).
3. **seats-from-sales** + **підпис організатора** (BonSens-parity).
4. Mobile-audit усіх `/my/*` (обов'язково).

Пріоритет «нативний підпис vs стара форма» — **рішення власника** (§9).

---

## 6. Hardening до Odoo-grade

- **Тести ≥70%** критичних шляхів: Kamilka-escalation, RODO field-level, immutability audit-логів, seat/registration flow, SMS cost-guard, view-as.
- **i18n PL/UA/EN:** en_US.po з нуля + чистка pl/uk-боргу (D2). Гейт `msgfmt`. (PL — головна; терміни kierownik≠wychowawca звіряти.)
- **Доки:** README, технічна, user-guide, CHANGELOG, App-Store index; виправити застаріле (CABINET_STATUS до-pivot; LEGAL §11 7→16; wzór-футер).
- **Lint/OCA:** pre-commit, pylint-odoo. ⚠️ Пастки: OCA `--fix` зносить self-translations; `po-pretty-format` вимикати.

---

## 7. Міграція даних + деплой

**Скрипти (ідемпотентні, DRY_RUN-first, rehearsed):** `populate_from_bs.py` (114), `migrate_bs_signatures.py` (97, §5.6), `populate_escort_from_204.py` (44, прямий reg.participant_id), `detach_campscout_management.py` (54 лінки, реверсивний).

**Прод (нічне вікно, за «ок», бекап+відкат):** Strangler — портал ПОРУЧ зі старим, **БЕЗ uninstall** на сезон. Послідовність: backup→install portal→populate_from_bs→migrate_bs_signatures→populate_escort→verify parity. Runbook: `DevJournal/projects/campscout/RUNBOOK-prod-deploy-portal-2026-06-23.md`. ⚠️ На staging install спливли 3 Odoo-17 баги (states=/`<list>`/constraint) — виправлені; авторитет = staging, не статика.

---

## 8. ВИКОНАВЧА МОДЕЛЬ — команда агентів (8 виконавців + 2 гейти = 10)

**Принцип розподілу моделей:** суть і все без машинного гейта → **Claude Opus**; обмежена механіка з автоперевіркою → можна не-Claude; фінальні юр/бізнес-рішення → **людина**. «Коло» = цикл «агент зробив → гейт перевірив → REJECT із фідбеком → переробив».

| Роль | Модель | Кіл | Ключовий недолік/пастка |
|---|---|---|---|
| **Архітектор Odoo17** (модель даних, Strangler-заміна) | Opus 4.8 | 1–2 | Хибна архітектура тиражується вниз по всіх потоках — найдорожча точка відмови, моделлю НЕ економити. |
| **Backend BonSens** (commercial.py, seats-from-sales, підпис орг.) | Opus 4.8 | 3–5 | Найважче. Експеримент 22.06: не-Claude (gpt-4o) за 10 ітер. не докрутив простий парсер (max 8/11, iter10 деградація — обірваний код). Дешеву сюди НЕ ставити. 3–5 кіл — оптимістично за готових тестів/фікстур; нечітке seats-ТЗ → застрягне. |
| **Міграція даних** (detach/uninstall, before/after, rollback) | Opus 4.8 (Sonnet на рутині) | 2–3 + прогін на прод-копії | «Зелені тести» оманливі — втрату даних видно лише на реальній копії з 114 дітьми. Синтетика бреше. |
| **Frontend season-completion** (OWL/QWeb, підпис, mobile) | Opus 4.8 (Sonnet на простих view) | 2–4 + mobile-audit окремо | UI агент «бачить» гірше за логіку; візуальний дефект на мобільному гейтом не завжди ловиться — потрібен скрін-рев + людське око. |
| **QA / автотести** (Odoo test framework, ≥70%) | Opus 4.8, **окремий агент** (не той, що писав код) | 2–3 | Ризик «тести під реалізацію» — підтверджують код, а не вимогу. Промпт QA — від ТЗ, не від коду. НЕ не-Claude. |
| **i18n переклад** (PL/UA/EN, .po) | **gemini / deepseek** (не-Claude) | 1–2 | Єдине, що сміливо на дешеву модель — є `msgfmt`-гейт. Але гейт ловить синтаксис, не сенс: фахові терміни + юр-формулювання звіряти точково (без словника — граматично чисто, змістовно криво). Ключі: `~/.secrets/ai_apis.env`. Прецедент: zadarma 988 записів msgfmt PASS. |
| **OCA / quality** (pylint-odoo, pre-commit) | Claude (можна Sonnet 4.6) | 1–2 | Це не «запусти лінтер», а «знай пастки»: `--fix` зносить self-translations, `po-pretty-format` off. Рішення «що з warning» — інженерне. |
| **Tech-writer** (README/user-guide) | Sonnet 4.6; App-Store опис — Opus | 1–2 | Документація відстає від коду — писати ХВОСТОМ, інакше двічі переробляти. |
| **DevOps/деплой** (Docker/nginx/CI, staging→прод) | Opus (ризик високий) | 1–2 підготовки + **ручний запуск людиною** у нічне вікно | Автономний агент НЕ котить на прод сам. chmod o+rX після pull, #4ZONES, нічне вікно (сезон). Автономія тут = повтор інциденту «500 після рестарту». |
| **GATE: Tech-lead / архітектор-рецензент** | Opus 4.8, найвищий effort | КОЖНЕ коло кожного потоку | Ловить (активно цитує LESSONS), але сам не виправляє; слабкий виконавець → REJECT-и зациклюються. Тому виконавці на суті — Opus. |
| **GATE: RODO / юрист (radca)** | агент готує+флагує, 1 коло; **фінал — людина/DPO** | 1 | Агент, що сам стверджує «RODO ок», бреше впевнено (доведено інцидентами). Юр-факт без людської перевірки джерела НЕ приймати. |

**Кіл загалом:** легкі (переклад/OCA/доки) 1–2; середні (frontend/QA/міграція) 2–4; важка (backend BonSens) 3–5; архітектура 1–2 на старті.
**Емпіричне правило:** після 2–3 REJECT без прогресу — переключати на **гібрид** (Claude докручує застрягле сам) або ескалувати людині. НЕ крутити до 10-го кола — там деградація, не покращення.
**Виконання, не дослідження:** «один день» реальний лише тому, що ми вже маємо весь контекст (аудит 79 моделей, staging-стан, lossless доведено). Нова невідома вимога → день розсиплеться.

---

## 9. Рішення поза агентами (власник / людина-в-петлі)

**РІШЕННЯ ВЛАСНИКА 2026-06-23: робимо ПОКИ ЩО ДЛЯ СЕБЕ** (наша продакшн-робота, не на продаж зараз).
1. ~~Ціль продаваності (OCA/App Store)~~ → **відкладено до моменту продажу.** Зараз внутрішнє.
2. ~~Ліцензія/ціна~~ → **LGPL-3 (внутрішня), OPL/ціна — на момент продажу.**
   ⚠️ **Інженерну якість тримаємо на sellable-grade** (тести ≥70%, i18n, доки, чистий код) — щоб продати пізніше БЕЗ переробки. Відкладаємо лише магазинну обгортку (опис/скріншоти/OPL/строгі OCA-конвенції публікації).
3. **[ЗАКРИТО — B] Нативний підпис карти в порталі робимо ЗАРАЗ, повністю.** Стара bs-форма = костиль; «на сезон» = назавжди. Будуємо за патерном escort-підпису (canvas→base64→action_sign→RODO-лог). Стара bs-форма виводиться. **БЕЗ відкладань.**
4. **Людина-в-петлі ОБОВ'ЯЗКОВА на 2 точках** (навмисний запобіжник): запуск деплою на прод + фінал RODO.

Усі рішення власника закрито → команда агентів стартує.

---

## 10. Критерії приймання + ризики

**Приймання (Odoo-grade):** тести ≥70% PASS на staging-Odoo; `msgfmt` PASS усі .po; pylint-odoo/pre-commit чисто; install **і** upgrade без помилок; parity lossless на прод-копії (before=after); /shop+booking 200; smoke кожної ролі; доки повні; mobile-audit `/my/*` зелений.

**Чесні ризики схеми:**
1. **«Виглядає готовим»** — найбільший ризик не баг, а зелений вигляд без суті, якщо QA/backend/OCA віддати дешевій моделі (доведено).
2. **Межа не-Claude** — «вся робота на не-Claude, Claude лише CTO» не докручує реальні задачі; дешеві — тільки переклад під msgfmt.
3. **Оманливі тести міграції** — без прогону на реальній прод-копії «зелена» міграція може мовчки втратити дані.
4. **«Один день» умовний** — це виконання за повного контексту, не дослідження.
5. **Блок на рішеннях власника** (§9 п.1–3).
6. **Людина в петлі** на деплої та фіналі RODO — запобіжник, не опція.

---

## 11. Звʼязки
- Міграційне ТЗ: `DevJournal/projects/campscout/TZ-migracja-legacy-to-portal-2026-06-23.md`
- Runbook прод: `DevJournal/projects/campscout/RUNBOOK-prod-deploy-portal-2026-06-23.md`
- Конвеєр агентів: `fayna-sendpulse-odoo/docs/MULTI_AGENT_WORKFLOW.md` + `docs-sorter/team_llm.py`/`team_review.py`/`design_debate_loop.py`
- Скрипти міграції: `fayna_camp_portal/scripts/populate_from_bs.py`, `migrate_bs_signatures.py`, `populate_escort_from_204.py`, `detach_campscout_management.py`
- LESSONS/інциденти: memory `project_incident_2026-06-23_*`, `project_campscout_legacy_migration_landmine_2026-06-23`
