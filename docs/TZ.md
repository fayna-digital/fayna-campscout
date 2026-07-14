# ТЗ — fayna_camp_portal (Портал CampScout) — ЄДИНИЙ КАНОН

> **Статус документа:** КАНОНІЧНЕ. Єдине живе ТЗ проєкту. Консолідовано **2026-07-03** з 14 історичних ТЗ (повний список і traceability — розділ 15). Усі попередні ТЗ позначені як архів і перейменовані.
> **Репо:** `VladSh77/fayna-campscout` · модуль `fayna_camp_portal` · Odoo 17 · версія `17.0.4.1.8` (зріз 2026-07-06)
> **Власник:** Volodymyr Shevchenko (Fayna Digital)
> **Структура:** REPO_STANDARD (6 областей) + нумеровані вимоги зі статусом і доказом (IEEE-830-стиль).

## Легенда статусів (використовується біля КОЖНОЇ вимоги)

| Позначка | Значення | Що вимагається як доказ |
|---|---|---|
| ✅ | Зроблено | посилання на код/коміт/PR + тест або машинну перевірку |
| 🟡 | Частково / зроблено без повної перевірки | що саме є, чого бракує |
| 🔴 | Не зроблено | у пункті описано ЩО зробити і ЯК (це і є беклог) |
| ⚪ | Чекає рішення власника | сформульоване питання |
| ⛔ | Заборонено / відхилено | причина відмови (щоб не повертатись) |

**Формат кожної вимоги:** `[ID] Назва — пояснення що це і навіщо · Статус · Доказ/тести · (для 🔴) як зробити.`

---

## Зміст

- **0.** Business / Product (мета, ринок, дедлайни)
- **1.** Архітектурні закони (5 непорушних правил)
- **2.** Пакет поставки, ліцензії, залежності
- **3.** Ролі, RBAC, видимість (піраміда)
- **4.** Функціональні вимоги (майстер, програма, рекрутація, картка, RODO, Kamilka, kiosk, портал, чати/SMS, продажі, ціна/VAT, фінанси, документи, i18n)
- **5.** Нефункціональні вимоги (UX, mobile, надійність, безпека)
- **6.** Тестування (що покрито, чим саме, які тести існують)
- **7.** Міграція даних і prod-cutover
- **8.** Ремонтний беклог (актуальний стан R1–R10 + беклог продажу)
- **9.** Процес розробки і гейти
- **10.** Success criteria / prod-gate
- **11.** Відкриті питання (рішення власника)
- **12.** ЧОГО НЕМАЄ ВЗАГАЛІ — і як це зробити
- **13.** Команди (запуск, тести, деплой)
- **14.** Структура коду
- **15.** Traceability: джерела → розділи; реєстр архівів
- **16.** Глосарій · **17.** C4-контекст · **18.** API та зовнішні контракти

---

# 0. Business / Product

*Пояснення розділу: бізнес-рамка, з якої випливають усі пріоритети. Заповнена власником 02.07.2026 (коміт `a029124`, merged у main).*

**[B-1] Проблема і цінність.** MEN-документація (картки кваліфікаційні, dziennik, teczka KO), RODO, Kamilka-протоколи ведуться вручну — довго, дорого, ризиковано (штрафи, кураторіум). Портал автоматизує весь цикл: створення табору → продаж → кадра → проведення → звіти. Ціннісна пропозиція SaaS: **«Ви робите табір — облік залиште нам»**. · ✅ зафіксовано в ТЗ (a029124) · Тести: не застосовно (бізнес-рамка).

**[B-2] Ринок і етапи.** Етап 1 — власна операція CampScout (клієнт-еталон): усі табори сезону 2027 (базлайн 2025 = **5 напрямків / 11 заїздів**) ведуться через портал, моноліт `campscout_management` вимкнено. Етап 2 — SaaS для малих організацій, що роблять табори час від часу: **OSP (Ochotnicza Straż Pożarna)**, парафії, спортклуби, ZHP-подібні. · ✅ зафіксовано (a029124).

**[B-3] Терміни (критичний шлях).** Реєстрація сезону 2027 стартує **серпень–вересень 2026** (~1–2 міс від фіксації); пік літа-2027 — травень 2027. Мін. prod-cutover — до серпня-вересня 2026; крайній — до травня 2027 (тоді зимовиська підуть повз портал). · ✅ зафіксовано; 🔴 сам cutover не виконано (розділ 7). **Критерій (EARS):** портал ПОВНІСТЮ розгорнутий на проді і приймає реєстрації сезону-2027 не пізніше **01.09.2026** (жорсткий дедлайн; цільова дата 01.08.2026). · Верифікація: inspect (запис у CHANGELOG + перша жива реєстрація).

**[B-4] Головний бізнес-ризик.** Проґавити вікно реєстрації → сезон 2027 не на порталі → ще рік «95% готово, 0 у проді, 0 доходу». · Мітигація: розділ 7 (cutover) — найвищий пріоритет після ремонту R2.

**[B-5] UX-DoD продукту.** Кожен екран самозрозумілий без інструкції (recognition-not-recall); двомовність UA/PL (аудиторія — українські діти в Польщі, дефолт мови — PL, рішення власника). · 🟡 двомовність ВЛИТА і жива на staging (PR#17, 04.07; deploy run 28699005633; psql: pl_PL+uk_UA active) — 🟡 лишається за рештою UX-DoD.

**[B-6] Пріоритет використання (пере-тріаж власника 25.06).** Реальний пріоритет = «портал працює для CampScout (сезон)»; «white-label перепродаж» (дебрендинг SMS, data→demo, мета-пакет) — ⏸ відкладено до реального продажу. Ліцензійний захист (OPL-1) — зроблено заздалегідь як дешевий. · ✅ рішення зафіксовано (14-TZ §20.8).

---

# 1. Архітектурні закони (непорушні)

*Пояснення розділу: 5 правил, які перевіряються на КОЖНОМУ ADR і код-рев'ю. Порушення = REJECT незалежно від якості коду. Джерело: 14-TZ §0, підтверджено рев'ю-вердиктом Odoo-platform-reviewer 24.06.*

**[A-1] Orchestrate-not-store.** Модуль — тонка оркестрація поверх нативного Odoo, НЕ паралельна реімплементація. Кожна підсистема в ADR декларує: `Native Odoo: <модуль> — extend` АБО `custom — бо <законна причина>`. · ✅ діє як гейт; доказ дієвості: рекрутацію-custom відхилено і переведено на hr_recruitment (див. [F-REC]); `camp.draft` відхилено. · Тести: непрямо — test_role_canon.py (канон ролей ADR-22).

**[A-2] Закон даних (data-resilience).** Клієнти/батьки = `res.partner`, учасники = `event.registration`+`camp.participant(_inherits res.partner)`, табори = `product.template`, події = `event.event`, фактури = `account.move`, оплати = `account.payment`. Custom-моделі тримають ЛИШЕ процес/домен (програма, групи, §13-cert, teczka, дедлайни) і ПОСИЛАЮТЬСЯ на нативні записи. Обґрунтування: дані custom-моделей гинуть при uninstall (доведено міною legacy: `campscout_management` володіє 24 таборами через `ir_model_data` — розділ 7). · ✅ діє; доказ: майстер створює нативні event/product; approval-стан живе на event (`camp_approval_state` — [ПЕРЕВІРЕНО: grep models/camp.py]).

**[A-3] Native-first + жодних нових fayna_camp_* модулів.** Новий camp-функціонал додається СЮДИ (hotel-pattern, pivot 2026-06-07 після INC-013: 15 модулів → дублювання 60+ моделей → 9 deploy errors). Горизонтальні модулі окремо: `fayna_rodo_compliance`, `fayna_sms_base`(+turbosms), `l10n_pl_ksef_margin`, `zadarma_odoo`. · ✅ діє; 18 старих fayna_camp_* репо deprecated, код перенесено (FAYNA_CAMPSCOUT_TZ §9 кроки 4-13).

**[A-4] Надійність оболонки.** Інтеграція з sale/event/registration/account — у try/except; збій оболонки НЕ блокує продаж/оплату (еталон `staffing.py:489`). Graceful skip замість traceback (урок teczka: NotImplementedError заборонено). Кожен build: py_compile + XML-well-formed + msgfmt + чистий `-u`-лог ПЕРЕД «готово». · ✅ діє як правило; Тести: CI Lint-гейт (ruff+bandit+OCA) на кожен PR [ПЕРЕВІРЕНО: gh pr checks].

**[A-5] Sellable-ready build-гейт.** Від першого рядка: (1) нуль AGPL у depends [✅ звірено, 0]; (2) нуль захардкоджених бізнес-ДАНИХ у коді — модуль для будь-якого організатора (порушення legacy: 24 табори в XML — не повторювати; grep-критерій приймання: назви таборів у `data/` = 0) [✅]; (3) нуль copyleft copy-paste [✅ grep 0]; (4) чисті межі модулів [✅]. Бренд «CampScout» у назві/SMS-рядках — ЛИШИТИ (рішення власника: це відображуваний текст, не дані). · ✅/⏸ дебрендинг SMS відкладено до white-label (B-6).

---

# 2. Пакет поставки, ліцензії, залежності

*Пояснення розділу: що саме є «продуктом» при майбутньому продажу і на яких умовах. Джерело: 14-TZ §2, sellable-cleanup 24.06.*

**[P-1] Комплект поставки** = `fayna_camp_portal` + `fayna_rodo_compliance` + `l10n_pl_ksef_margin` + `fayna_sms_base` (+`fayna_sms_turbosms`) + `zadarma_odoo` + стандартні Odoo (base/mail/sale/event/account/website/portal/sms/loyalty). Деплой КОМПЛЕКТОМ (Odoo не качає depends з інтернету — код мусить бути в addons_path). · ✅ зафіксовано; NOTICE.md у 6 модулях (гілка `chore/sellable-license-cleanup`).

**[P-2] Ліцензія OPL-1** (пропрієтарна, «справжній продаж») у manifest усіх 5 наших модулів + © Fayna Digital. AGPL у дереві depends = 0 (звірено). Co-Authored-By: Claude — зупинено going-forward, історія не переписується (продаж чистим релізом — скрипт `DevJournal/scripts/make-release.sh`, чернетка). · 🟡 ЗНАЙДЕНО НЕВІДПОВІДНІСТЬ: `fayna_rodo_compliance/LICENSE` і `fayna_sms_base/LICENSE` містять LGPL-текст при manifest=OPL-1 → **як зробити:** замінити текст LICENSE на OPL-1 у двох репо (потребує окремого «ок» — #BOUNDARY, чужі репо). · ⚪ рішення: гілка sellable-cleanup досі не merged — коли зливати. **Критерій (EARS):** WHEN модуль релізиться, THEN вміст LICENSE ПОБАЙТНО відповідає OPL-1 в усіх 5 модулях (вкл. fayna_rodo_compliance, fayna_sms_base); нові коміти НЕ містять AI-співавторства. · Верифікація: inspect (hash-порівняння LICENSE; grep трейлерів у нових комітах = 0).

**[P-3] SMS провайдер-агностичність.** `fayna_sms_base` вже має абстракт `sms.provider.base` + config + чергу + лог + 1 адаптер TurboSMS. · 🔴 доробити: розширити `provider_type`, адаптери generic HTTP/REST + SMSAPI.pl / SerwerSMS.pl (PL-ринок; TurboSMS = UA), роутинг + баланс per адаптер. **Як зробити:** новий клас-адаптер на модель provider_type за патерном turbosms; тест — mock HTTP; не блокер сезону.

**[P-4] Manifest-depends порталу:** base, mail, portal, website, website_sale, event, event_sale, sale, sale_management, account, loyalty, sms, website_rating + fayna_rodo_compliance, fayna_sms_base. НЕ залежить від fayna_sms_turbosms. · ✅ [ПЕРЕВІРЕНО: CLAUDE.md модуля + manifest].
---

# 3. Ролі, RBAC, видимість

*Пояснення розділу: хто працює в системі, через який інтерфейс (кіоск чи повний Odoo), і що кому видно. Модель видимості — «піраміда»: Організатор → Табори → Керівник → Групи → Виховник → Діти. Один запис дитини, різні зрізи через record rules — жодного копіювання даних. Джерела: 14-TZ §4-5, FAYNA_CAMPSCOUT §5, ADR-22.*

**[R-1] Канон ролей (ADR-22).** 6 базових груп: Organizator / Sales / Kierownik / Wychowawca / Instructor / Parent + опційні надбудови per табір: Medical Officer (art.9 всього табору), Nutrition, HR, Emergency, Finance. 13 груп у security/groups.xml, 170+ ACL. Єдина модель ролей замість 3×dict (канон закрито). · ✅ Доказ: `security/groups.xml`, ACL-аудит «0 моделей без ACL» (14-TZ §20.2) · Тести: `test_role_canon.py` + ролеві `test_role_*.py` (9 файлів: organizator_create_camp, parent_cabinet, parent_portal, parent_image_consent, kierownik_dziennik, wychowawca_day_note, wychowawca_note, instructor, public_vacancies).

**[R-2] Кіоск vs повний Odoo.** Повний Odoo (профі): організатор, продавець/менеджер (CRM+sale+Zadarma+SMS+Discuss), бухгалтер (якби в системі — scoped ACL без дітей). Кіоск (одна задача): батько, виховник, інструктор, керівник (кіоск операцій + toggle→Odoo). Кандидат = нативний `hr.applicant` (кабінету не має — ⛔ кіоск кандидата відхилено). Без кіоска взагалі: волонтер (але §13/KRK обов'язкові!), молода кадра (інфо-запис, 0 доків — межа §13: вік 18+ і самостійність, не назва ролі), лідер звена (дитина-учасник). · ✅ ядро реалізовано: `controllers/kiosk.py` (плитковий кіоск), `/admin/dashboard` + login-as; 🟡 кіоски instructor/medic — базові · Тести: `test_role_instructor.py`, experiential-прогони конвеєра 24-25.06.

**[R-3] Піраміда видимості + фрактал.** Record rules: батько → свої 1–3 дитини (`rodzic==user`); виховник → своя група ≤15/20, art.9 лише своїх; керівник → весь табір; медик → art.9 всього табору; продавець → свої ліди/клієнти + каталог + заповнюваність (комерція, НЕ операційка); організатор → все (1=1). · ✅ Доказ: `security/record_rules.xml`; RODO-матриця доступів пройшла аудит · Тести: `test_art9_access.py` (field-level), `test_role_parent_cabinet.py` (ізоляція батька). · 🔴 Рекурсивний ієрархічний view-компонент «одна цеглинка на всіх рівнях» (14-TZ §5.1) не збудовано — зараз стандартні group-by списки. **Як зробити:** OWL-компонент tree по event→group→wychowawca→діти, рендер від рівня входу record-rule; ~2-3 дні; після сезонних пріоритетів.

**[R-4] Хто бачить картку дитини (фінальна таблиця §6l-ВИПРАВЛЕНО).** Повну карту (адмін+медична art.9): батько (своя), виховник (група), медик (табір), керівник (табір), організатор (всі), **продавець (свої клієнти — роль QA заповнення; рішення власника 24.06 скасувало ранні обмеження)**. Інструктор: статус + safety-флаги своїх занять. НЕ бачать: бухгалтер, молода кадра, чужий батько. Карта живе двічі: структуровані поля (queryable) + підписаний PDF (immutable юр-артефакт). · ✅ record rules + field groups · Тести: `test_art9_access.py`; ⚠️ attachment-ACL на PDF — див. [F-RODO-2].

**[R-5] Термінологія per культура.** Та сама роль різна назва: комерційний табір «молода кадра» ↔ скаутинг «гурткові»; kierownik ↔ komendant. Лейбл конфігурований за типом організатора, НЕ хардкод (sellable [A-5.2]). · 🔴 термінологічний шар не реалізовано. **Як зробити:** словник лейблів на формі організатора ([F-VAT-3]) + `_get_role_label()` хелпер у view-рендері; ~1 день; потрібно до SaaS-етапу, не до сезону.

---

# 4. Функціональні вимоги

## 4.1 Майстер створення табору (епік A)

*Пояснення: головна дія головної ролі — керівник/організатор створює табір покроково через wizard, а не форму з 50 полів. Це був блокер R1 (табір не створювався взагалі). Джерела: 06-TZ §A, 12-TZ §2-3, REPAIR R1.*

**[F-WIZ-1] Wizard 8+ кроків** (`wizards/camp_create_wizard.py`): тип (MEN selection) → назва → локація → дати → проживання → рамовий день → активності → к-сть дітей → ціна (калькулятор) → створення. Вхід: плитка «Nowy obóz (kreator)» у кіоску. · ✅ Доказ: PR #14 merged `fd9dad2`, задеплоєно на staging (`ada38f3`, R1_VIEW_IN_DB + HTTP 200) · Тести: QA-Playwright наскрізний (8 кроків, event створено, скріни), CI test-gate 170 зелений, `test_role_organizator_create_camp.py`.

**[F-WIZ-2] Per-step валідація (фікс R1).** Поля валідуються ЛИШЕ на своєму кроці (`_STEP_REQUIRED` у `action_next`) + фінальний захист в `action_create_camp` + умовний `required="step=='...'"` у view. Причина дефекту: модельний `required=True` несумісний з persist-on-navigate wizard. · ✅ merged; Тести: Playwright «крок1→Dalej→крок2 без Invalid».

**[F-WIZ-3] Workflow затвердження (draft→submit→approve).** Каскад створення (event + ticket + product + program + групи + budget + teczka) виконується при APPROVE організатора, не одразу; стан живе на native event (`camp_approval_state`), `website_published=False` до approve; `camp.draft` як дзеркало — ⛔ відхилено ([A-2]). · ✅ Доказ: `camp_approval_state` у `models/camp.py` + wizard [ПЕРЕВІРЕНО: grep] · Тести: `test_native_approval.py`.

**[F-WIZ-4] Авто-кістяк програми з валідацією нічної тиші ≥9 год сну** (сніданок/обід/підвечірок/вечеря, підйом/відбій, вільні години). · ✅ Тести: `test_program_skeleton.py`.

**[F-WIZ-5] Авто-групи N=ceil(seats/20) (art.92c)** при каскаді + round-robin поділ дітей при резервації (епік D). · ✅ Тести: `test_camp_group.py`, `test_phase_d_split.py`. Ліміти: ≤20 дітей; є дитина <10 р. → ≤15; niepełnosprawni ≤2 — у constraints camp.group.

**[F-WIZ-6] Форми wypoczynku — повний перелік MEN (=R6).** · ✅ 2026-07-04: додано `polkolonia` + `zielona_szkola` в обидва Selection `vacation_form` (`wizards/camp_create_wizard.py:85` і `camp.kuratorium.notification`, operations.py). Верифікація: test ✅ `test_vacation_forms.py` (повний каталог MEN + sync-гард wizard↔notification). 🔴 **Нова знахідка R6.1:** `action_create_camp` НЕ переносить обране `vacation_form` нікуди (значення губиться; kuratorium notification wizard-ом не створюється) — окремий пункт у §8.

**[F-WIZ-7] High-risk табори.** Авто instructor-вакансія з ліцензією + поля high-risk/ubezpieczenie на event (лижі/вода → обов'язкове страхування + ліцензований інструктор). · 🔴 не реалізовано (GAP-и experiential seed, event 140 Ski Zakopane). **Як зробити:** boolean `is_high_risk` + activity-тип-тригер → вакансія instructor з required license-cert + required insurance attachment; ~1-2 дні.

**[F-WIZ-8] Фото-крок + SEO.** Крок «Фото» → при каскаді `product.image` (галерея) + `image_1920` + website meta/og:image/alt (нативний auto-resize/WebP Odoo 17). · 🟡 контейнерні поля product є; крок фото у wizard — перевірити наявність при наступному прогоні (не верифіковано цим аудитом). **Як довести:** Playwright-прогін кроку фото + перевірка product.image після approve.

## 4.2 Програма табору (епіки A7-A10, C)

*Пояснення: двошарова програма — керівник задає верхній план і «замикає» незмінні слоти (куплені квитки), виховник наповнює деталі лише в люфті; окремо дощовий (запасний) план. Джерело: 06-TZ §Уточнення, 12-TZ §8. Моделі після reuse S1 пара 5 (PR#37, міграція 17.0.4.1.6): keeper `camp.program.structured` + `camp.program.day` + `camp.program.activity.line`; legacy `camp.program`/`camp.program.activity` ВИДАЛЕНІ; `camp.schedule.entry` — окрема маркетингова фіча, свідомо НЕ злита (рішення в migrations/17.0.4.1.6/post-migrate.py).*

**[F-PRG-1] Двошаровість + замки.** `camp.program.activity.line.is_locked` (set керівником) — виховник read-only на locked, редагує лише незамкнені слоти; constraint «виховник не пише поверх locked». · ✅ Доказ: `is_locked` у `models/operations.py` [ПЕРЕВІРЕНО: grep] · Тести: `test_phase_c_wychowawca.py`.

**[F-PRG-2] Дощовий план.** `is_rain_plan` — запасна програма; обидві (звичайна+дощова) рендеряться на картці товару. · ✅ Доказ: grep `models/camp.py`, `operations.py`, wizard · Тести: покриття у program_skeleton/phase_c (частково); 🟡 рендер обох на картці товару — довести скріном картки після [F-SALE-2].

**[F-PRG-3] Правило 100% заповнення виховником** (аварійна/запасна програма — навіть якщо не виконає). · 🟡 як constraint не підтверджено. **Як довести/зробити:** індикатор «програма 100%» вже у панелі керівника ([F-KSK-3]); додати блокуючий чек при старті табору — ~0.5 дня.

**[F-PRG-4] Друк Program Wypoczynku (Załącznik 9) як PDF.** · 🔴 хвіст з 04-TZ Тир 3 (QWeb-report не зроблено). **Як зробити:** `ir.actions.report` + QWeb за wzorem MEN (аналогічно karta_report_templates.xml); DoD: PDF відкривається з форми програми; ~1 день. (Дзеркальний борг: `test_dziennik_pdf.py` існує — dziennik PDF є; програма — ні.)

## 4.3 Рекрутація кадри + §13 (епік B)

*Пояснення: вакансії й найм — через нативний hr_recruitment (вакансія на /jobs, apply, співбесіди-stages), а custom-модель вакансій відхилено; поверх — юридичний гейт §13 Ustawa Kamilka (KRK/RSPTS перед допуском до дітей). Джерела: 06-TZ §16-18, 12-TZ §7, 14-TZ §12.*

**[F-REC-1] Рекрутація кадри — R13-півот: ВЛАСНА легка модель, БЕЗ hr_recruitment.** `camp.staff.vacancy` + публічний `/camp/vacancies` → заявка кандидата → §13-гейт (KRK/RSPTS) → `camp.staff` draft. · ✅ Доказ: `models/staffing.py:6` (R13: БЕЗ hr_recruitment), `models/recruitment.py`, `controllers/recruitment_portal.py` · Тести: `test_role_public_vacancies.py`, `test_staffing.py`. ⚠️ Виправлено 04.07 звіркою код↔ТЗ: попередній текст описував hr_recruitment-bridge, якого в коді немає (grep hr.applicant = 0). 🔁 REUSE-ЦІЛЬ (аудит 04.07): планова міграція на стандартний hr_recruitment — крок 3 плану §8 п.17, лише після «ок» власника.

**[F-REC-1a] Швидкі публічні форми кадри/батьків (без логіну) — тимчасовий стопгап 07.07.2026.** `/camp/kadry/campscout` (instruktor PL + wolontariusz UA, БЕЗ підпису — лише генерація PDF+фіксація факту заповнення), `/camp/kadry/rodzice` (Dodatek 4a/4b, canvas-підпис) та `/camp/kadry/wilcza` (umowa zlecenia кадри табору «Na Wilczej Ścieżce» — instruktor/medyk/kierownik, аварійні бланки; додано на гілці feat/kadry-wilcza-zlecenia); усі — self-contained HTML+JS (pdfMake, client-side генерація), `auth="public"`, без порталу/логіну. Подання фіксується через `POST /camp/submit-document` (`controllers/document_submission.py`) — зберігає PDF+ПІБ+IP+час у `ir.attachment` (не через окрему модель — `camp.document.submission.log` існує в коді, але чекає `-u`, який на цьому стенді на 07.07 був зламаний навіть для `base`; план — перенести на власну модель, коли `-u` запрацює). Перенесено з окремого репо `kadry-forms`/GitHub Pages (07.07) — тепер same-origin з `/camp/submit-document`, CORS не потрібен. · ✅ Доказ: `controllers/kadry_forms.py`, `static/src/kadry/`, `controllers/document_submission.py` · ⚠️ INC-217/218 (07.07): попап згоди на відправку мав необов'язкову кнопку «лише завантажити» — прибрано, відправка обов'язкова. 🔁 REUSE-ЦІЛЬ: інтегрувати з `camp.staff.vacancy`/`[F-REC-1]` замість окремого стопгапу, коли буде час після сезону.

**[F-REC-2] §13-допуск (флоу власника).** hire → staff=draft → підпис RODO + declaracja RSTPO ([F-RODO-3]) → доступ до порталу, але **діти РОЗМИТІ** (0 дій) → працівник вантажить KRK → керівник перевіряє → кнопка «ДОПУСК» → staff=active → діти видимі/редаговані. Гейт: `_check_rspts_before_admission` (`operations.py:217`). · ✅ Доказ: blurred-механіка у `controllers/recruitment_portal.py` [ПЕРЕВІРЕНО: grep] · Тести: `test_staffing.py` (RSPTS-гейт); 🟡 blurred-UX e2e-скріном не доведено — додати Playwright-крок.

**[F-REC-3] Документи кадри (retention 7 років / контракти 10).** KRK/niekaralność, RPS, sanepid, świadectwa курсів (kierownik 3+ роки досвіду з 15) — `ir.attachment` на hr.employee + `camp.staff` cert-поля; повторна верифікація КОЖЕН сезон (KRK дійсний 12 міс); акцепт лише вручну Admin/Organizator; kierownik бачить скани своєї кадри (на контролі KO), wychowawca/sales — ні (RODO art.10); кожен перегляд сканів → audit log. · ✅ модель+гейт; 🟡 повний пакет документів виховника (CV/анкета/umowa zlecenia/евіденція годин/рахунок — еталон кейс Даніеля) у кабінеті не наповнено (camp.escort staff-доки: 0 записів на тесті 02.07). **Як зробити:** чекліст документів на camp.staff + upload у кабінеті staff; ~1-2 дні.

**[F-REC-4] Ставки кадри** (для вакансій і калькулятора): wychowawca 220 / kierownik 260 / instruktor 300 zł/день; вакансія має description/requirements + ставку. · 🟡 ставки в калькуляторі є ([F-VAT-1]); опис/ставка на вакансії — перевірити поля hr.job; скасування реєстрацій НЕ авто-закриває найняту кадру (прапорець overstaffing, рішення людини) — 🟡 не верифіковано.

## 4.4 Картка кваліфікаційна (wzór 2026) + підписи

*Пояснення: юридичне серце системи — карта MEN (Dz.U.2026/704) з медичними полями art.9, підписом батьків онлайн і незаперечністю. Джерела: SPRINT §1, 14-TZ §9.6, PLAN P2.*

**[F-KKW-1] Wzór 2026 + przepis przejściowy.** `wzor_version` 2021/2026 (межа 06.06.2026, старі підписані незмінні); структуровані поля pkt 9 (18: allergy_meds/pollen/food/insect_venom (+notes), motion_sickness, permanent_meds, chronic_diseases, orthodontic_appliance, glasses, contact_lenses, diet_lowcal, diet_vegetarian, emotional_expression_issues, group_functioning_issues, fear_of_heights, hydrophobia, vacc_tetanus_year, vacc_diphtheria_year, vacc_other). Сумісність із BonSens: proxy-поля `fn_*` (1:1 API) на camp.participant для міграційної parity. Emergency contacts — 2 набори + relation; PESEL з checksum-валідацією при вводі. · ✅ Доказ: PLAN P2.1 done, 12 полів wzór2026 у participant.py + pkt9 · Тести: `test_karta_2026.py`, `test_karta_pdf.py`.

**[F-KKW-2] Підпис батьків у порталі (нативний, canvas).** `/my/participants/<id>` → sign → Binary attachment + signed_date + signed_ip + signed_by + RODO-log; одна дитина × один турнус = одна картка; меддані НЕ копіюються між дітьми; спільні дані батьків передзаповнюються. · ✅ Доказ: 04-TZ Тир A verified (curl portal-user 200, signed_by=справжній батько) · Тести: `test_signoff_rodo.py`, `test_escort_signoff.py` (той самий патерн).

**[F-KKW-3] Незаперечність (non-repudiation) — 3 механізми:** (1) immutable PDF (record-lock write після signed); (2) append-only журнал `fayna_rodo_consent_log` + HMAC; (3) хеш підписаного PDF. Фіксація: timestamp, IP, хто, user-agent. Зміна після підпису — ЛИШЕ через amendment-copy: нова редакція окремим записом, стара в архів з audit-trail (write-block на оригіналі). · ✅ механізми 1-2 · Тести: `test_rodo_consent_immutable.py`; 🟡 хеш PDF (мех.3) — не підтверджено кодом. **Як довести:** grep sha у participant sign-flow; якщо нема — додати поле `signed_pdf_hash` + запис у момент підпису (~0.5 дня).

**[F-KKW-4] R1-блокада активностей.** hydrophobia/fear_of_heights → ValidationError на запис у водні/висотні заняття, БЕЗ override (рішення R1 спринту 10.06). · 🟡 поля є; сам constraint не верифіковано тестом. **Як довести/зробити:** тест на ValidationError; якщо constraint відсутній — додати на activity-line registration; ~0.5 дня.

**[F-KKW-5] Згоди 4a (wizerunek) + 4b (marketing)** з canvas-підписом, IP, RODO-log; фото дитини в stories лише за image-consent (consent-gate). Розрізняти ДВІ цілі фото: внутрішній показ у кабінеті ≠ публічний маркетинг (Dodatek 4a) — окремі згоди; 4b — toggle з можливістю ВІДКЛИКАННЯ будь-коли (не лише first-time), відкликання → RODO-log. Тексти згод — HTML-body на res.company (setup-чеклист перед запуском порталу). · ✅ Тести: `test_role_parent_image_consent.py`, `test_story_photo_consent_gate.py`.

**[F-KKW-6] Auto-refusal.** Реєстрація без підписаної карти/RODO за 24 год до старту → cron скасовує + refund + RODO log, місце звільняється (нагадування батькам за 14/3 дні — SMS CRITICAL). · 🟡 cron ВЕРИФІКОВАНО тестом 04.07 (`test_auto_refusal_cron`: прострочений+непідписаний → cancel реєстрацій + латч refused_at + RODO-лог + chatter; підписаний недоторканий; ідемпотентність — 3/3): cron існує (`data/cron.xml: cron_auto_refusal_unsigned`, щоденний). **ЗАЛИШОК 🔴: refund — заглушка** (`_schedule_refund` лише логує, participant.py) — реальний механізм повернення окремим пунктом §8. ⚠️ life-critical для сезону. **Критерій (EARS):** WHEN за <24 год до старту заїзду реєстрація без підписаної карти АБО без RODO-згоди, THEN система АВТОМАТИЧНО скасовує реєстрацію + повний refund + запис у RODO-лог; існує щоденний cron, що це виконує. · Верифікація: test (тест-фікстура з непідписаною картою → cancel+refund+log) + inspect (cron у data/).

**[F-KKW-7] Картка-еталон фірми.** PDF має виглядати як фірмовий еталон (гарніший за MEN-дефолт), res.company з брендом/лого/реквізитами (не «YourCompany»). · 🔴 еталон не знайдено/не застосовано (знахідка тесту 02.07). **Як зробити:** знайти еталон у репо camp / fayna_camp_qualification / Dokumenty → QWeb-стилізація karta_report; конфіг res.company на staging уже виправлено частково; ~1 день.

## 4.5 RODO (модуль fayna_rodo_compliance + портальні стики)

*Пояснення: RODO-модуль — окремий крос-проєктний (своє ТЗ у його репо `fayna_rodo_compliance/docs/TZ.md`); тут — вимоги, що стосуються порталу. ДВІ різні RODO: працівника (Klauzula на hr.employee) і дітей (art.9 на participant) — один журнал, різні суб'єкти; місток = Upoważnienie art.29 на працівнику. Джерела: 15-TZ, 12-TZ §6j-6p, 14-TZ §21.*

**[F-RODO-1] Журнал згод + HMAC (append-only).** `fayna_rodo_consent_log`: partner, consent_type (marketing/image/rodo/art9-access/declaracja), action (granted/revoked/accessed/erased/unsubscribed/declared), timestamp, IP, user-agent, location, hmac_hash, source. · ✅ існує і використовується порталом · Тести: `test_rodo_consent_immutable.py`, `test_signoff_rodo.py`.

**[F-RODO-2] Art.9 — ДВА механізми разом.** (1) field-level groups на медполях (живі форми) — ✅ (`test_art9_access.py`); (2) attachment-ACL на PDF (PDF = плоский файл, field-security його не захищає!) — 🟡 record-rule на ir.attachment з медвмістом не підтверджено тестом. **Як довести/зробити:** тест «бухгалтер/чужий батько не відкриє karta-PDF по прямому URL `/web/content/<id>`»; якщо діри — record rule на ir.attachment (res_model='camp.participant' + медичний res_field) для art.9-груп; ~1 день. ORM-рівень УЖЕ покрито тестами (`test_art9_access.py`: finance_cannot_read_karta_attachment / medic_can_read_karta_attachment; write-rule `rule_attachment_participant_medical_write` у record_rules.xml). ✅ **HTTP-ізоляція ВИРІШЕНА 04.07 (PR#17):** 3 червоні тести PR#15 мали корінь «URL-префікс /pl/ після активації мов» — тести зроблено i18n-aware, leak-асерти зелені (див. [F-I18N-1]). **Критерій (EARS):** WHEN користувач БЕЗ art.9-прав відкриває karta-PDF за прямим URL (вкл. `/web/content/<id>`), THEN доступ заборонено (0 успішних спроб); test_art9_http_isolation = 100% pass. · Верифікація: test (симуляція прямого URL чужим юзером).

**[F-RODO-3] Declaracja-гейт §13 (RSTPO).** КОЖЕН (вкл. організатора) перед першим доступом до карток підтверджує declaracja про несудимість (правова рамка: art.92p ustawy o oświacie + RSTPO; текст у data/, не в Python; prefilled поля з hr-запису: miejscowość, dnia, imię i nazwisko, data urodzenia, adres). Текст verbatim (Dokumenty 9-009, Załącznik 2): «Ja niżej podpisany/a oświadczam pod rygorem odpowiedzialności karnej za składanie fałszywych zeznań stosownie do art. 233 §1 Kodeksu Karnego, że nie figuruję w bazie danych Rejestru Sprawców Przestępstw na Tle Seksualnym z dostępem ograniczonym i nie zostałem/am skazany/a prawomocnym wyrokiem za inne przestępstwo umyślne.» (+опц. zobowiązanie подати zaświadczenie з Rejestru, видане ≤3 міс перед роботою). Блокуючий модал (cookie-style, без «закрити й пропустити»); раз на сезон (KRK 12 міс); лог: хто+коли+IP+місце+user-agent+HMAC (потенційний кримінальний доказ). · ✅ Доказ: declaracja/RSTPO у `models/operations.py` [ПЕРЕВІРЕНО: grep] · 🟡 тесту на блокування нема. **Як довести:** тест «без declaracji act_window карток недоступний»; ~0.5 дня. **Критерій (EARS):** WHEN користувач вперше за 12 міс відкриває картки без підтвердженої declaracji, THEN блокуючий модал забороняє доступ до підтвердження; після підтвердження — доступ і append-only лог. · Верифікація: test (обидві гілки).

**[F-RODO-4] Erasure (право на забуття).** Wizard на res.partner → анонімізація + лог action='erased' + SendPulse sync; юридичні дані (account.move/sale.order, retention 5-7 р.) НЕ видаляються — анонімізація; медичні/інцидентні — не erased (art.17(3)(e), art.89 anonimizacja). · ✅ Доказ: erasure/anonymi у `participant.py`, `commercial.py` [ПЕРЕВІРЕНО: grep] · 🟡 тесту нема; SendPulse-sync не верифіковано.

**[F-RODO-5] Консолідація журналів 2→1 + unsubscribe.** `sendpulse_privacy_consent_log` (fayna-sendpulse-odoo) мігрувати у `fayna_rodo_consent_log`; unsubscribe (native email_opt_out + SendPulse API) — у RODO-модуль; продавець бачить стан згоди контакту (можна дзвонити/SMS/email) на res.partner. · 🔴 міграція журналів не виконана. **Як зробити:** migration-скрипт (2 таблиці → 1, source='sendpulse') + depends sendpulse→rodo; окремий PR у 2 репо; ~1-2 дні; не блокер сезону.

**[F-RODO-6] UODO audit-export.** Кнопка «Завантажити RODO-звіт» (organizator): хто/коли дав згоду, відписався, кого забуто; PDF+XLSX; фільтри per-partner/per-camp/дата. · 🔴 не збудовано. **Як зробити:** QWeb+XLSX report по consent_log (аналог евіденції [F-FIN-2]); ~1 день.

**[F-RODO-7] Мандат максимального захисту (DoD-БЛОКЕР ПРОДА).** Для art.9 + declaracji: (а) шифрування at-rest (filestore + Postgres); (б) бекап filestore+DB разом, офсайт, retention; (в) строгий доступ (повний пакет [F-RODO-2,3]); (г) повний audit art.30; (д) ротація секретів. Без пакету прод таких даних НЕ запускати. · 🔴 інфра-частина (а, б-офсайт, д) не зроблена. **Як зробити:** окремий infra-ADR у campscout-infra (LUKS/pgcrypto або volume-шифрування Hetzner, borg/restic офсайт, ротація) + «ок» власника; ~2-3 дні. Входить у prod-gate (розділ 10). **Критерії (EARS, атомарно):** (а) filestore прода шифрується at-rest (LUKS/volume); (б) Postgres шифрується at-rest (volume/pgcrypto, AES-256); (в) бекап filestore+DB разом, офсайт, retention ≥30 днів; (г) секрети ротуються ≤90 днів; (д) audit-лог art.30 append-only. · Верифікація: inspect (конфіг інфри + журнал ротації) per пункт.

## 4.6 Kamilka + інциденти

*Пояснення: Ustawa Kamilka 2024 — особливий режим НС за участю дітей: обхід SMS opt-in (vital interest), ескалація, незмінні журнали для кураторіуму. Джерела: FAYNA_CAMPSCOUT §5A.8, SPRINT §1, PLAN P2.*

**[F-KAM-1] Kamilka override.** `camp.incident.report` severity='kamilka': SMS на ВСІХ subscribers навіть при opt-out (GDPR art.6.1.d), ескалація через 5 хв без прочитання → резервний контакт; immutable notification log для Kuratorium. · ✅ Доказ: `incident_kamilka.py`, `incident_notification_log.py`, cron_kamilka_escalation.xml · Тести: `test_native_approval.py`/`test_signoff_rodo.py` (суміжно); прямий тест ескалації — 🟡 у переліку відомих боргів P3.

**[F-KAM-2] Karta Wypadku §11 (16 пунктів, не 7!) + Rejestr Wypadków §12** (10 колонок, авто-агрегація, Lp., immutable після закриття турнусу, PDF для KO). · ✅ Доказ: `models/incident_card.py:49` (карта), `:494` (реєстр), PLAN P2.2-2.3 · Тести: `test_incident_card.py`. ✅ Знахідку 02.07 (п.9 opis порожній) закрито 2026-07-04: шаблон `report_incident_card_document` мапить `o.opis_wypadku` (п.9), усі 16 пунктів присутні; найімовірніша причина знахідки — stale-копія `/mnt/addons` на стенді (урок R1). **Критерій (EARS):** WHEN генерується Karta Wypadku, THEN п.9 (opis) заповнений даними camp.incident.card (ніколи не порожній) і документ містить рівно 16 пунктів §11. · Верифікація: test ✅ `test_incident_card.py::test_card_report_renders_16_points_with_opis` (+ рендер реєстру `test_register_report_renders_card_opis`) — рендер QWeb з фікстурою, 16 пунктів + непорожній opis. Нюанс 04.07 (звірка код↔ТЗ): непорожність гарантує гейт `action_confirm` (draft-друк може мати порожній п.9 — шаблон `or ''`).

**[F-KAM-3] SLA-протокол інциденту (BP-006, AHA+Rozp. MEN):** 0-10с scene safety; 0-2хв CPR; 2-15хв безпечне місце+швидка+перший контакт батьків; 15-30хв батьки повністю поінформовані+kierownik на місці; 30хв-24г organizer+kurator+sanepid/prokurator; 24г-7д свідки; 7-21д protokół у 3 копіях. Реалізація: SLA computed booleans + sla_breaches + червоний бейдж у дашборді. · 🟡 workflow 7-state/18 дій є (`emergency.py`); SLA-таймери зі списком порушень не верифіковано. **Як довести/зробити:** перевірити поля sla_* у emergency.py; додати відсутні computed + тест; ~1 день.
## 4.7 Kiosk + кабінети + панель керівника

*Пояснення: кожна не-технічна роль працює в «кіоску» — одне вікно з 3-7 плитками замість сирого Odoo-бекенда; керівник додатково має живу статус-панель по табору (дедлайни, документи, прогрес). Патерн reuse з dnj-shopfloor. Джерела: 12-TZ §1, 06-TZ §20-22, 14-TZ §11, REPAIR R4-R9.*

**[F-KSK-1] Кіоск-плитки per роль** (home_action → OWL/QWeb дашборд; меню сирих апів сховані; toggle «↔ Odoo» лише бекенд-ролям; організатор — toggle в обидва боки + кіоск-хаб по пірамідах з login-as). · ✅ ядро: `controllers/kiosk.py`, kiosk_app.js/kiosk_template.xml; кіоск керівника production-quality (14-TZ §20.2); organizator dashboard-redirect (commit 093cab4) · Тести: experiential-прогони, `test_portal_camp_day.py`; PIN-логін з dnj-патерну — не потрібен (рішення не зафіксовано → не робимо без потреби).

**[F-KSK-2] Kiosk UX-ремонт (з REPAIR_TZ + ux-nielsen):**
- **R4 desktop-адаптація** · ✅ 04.07: сітка 3×3 ≥992px (bootstrap row-cols, гаттери g-класами), max-width 960 по центру; телефон 1 колонка. DoD виконано: Playwright-скріни 1440px (3 плитки/ряд по 320px) + 390px — kiosk_1440/kiosk_390 у сесійному артефакті.
- **R5 бренд** — лого CampScout у шапці kiosk + /my. · 🔴 **Як:** вордмарк з brandbook (репо camp) у header-QWeb; DoD: скрін.
- **R7 мікрокопі** — розкрити «BEP/marże», «Teczka KO», «Raport §2.11» (тултіпи вже додано 25.06 частково ✅). · 🟡 дочистити головні лейбли.
- **R8 кольорова семантика** — акцент лише головному CTA (Nowy obóz), червоний лише НП. · 🔴 **Як:** палітра у scss + легенда.
- **R9 заголовок+контекст** — «Вітаємо, [ім'я] · [роль] · Табір: [назва]», бейджі-лічильники, Sytuacje окремо. · 🔴 **Як:** header-QWeb з user/event context; DoD: скрін.
- **R4b Знахідка власника 04.07 (скрін staging, desktop ≈1730px, kiosk home):** сторінка рендериться mobile-layout — плитки в 1 колонку плитками-гігантами, права половина екрана порожня, хоча в шаблоні `row-cols-lg-3` (розбіжність код↔рендер); перемикач мови PL/UA висить окремо на правому краю ПОСЕРЕДИНІ висоти сторінки, хоча в коді `position-absolute top-0 end-0` (друга розбіжність код↔рендер); кольори langbar = дефолт Odoo, не бренд. · ✅ 04.07 КОРЕНІ ЗНАЙДЕНІ Й ПОЛАГОДЖЕНІ: (1) flex-`gap !important` на bootstrap-row ламав row-cols-математику (50%+50%+gap>100% → перенос → 1 колонка на будь-якій ширині; доведено аналізом скомпільованого бандла staging — класи в DOM/CSS були коректні); (2) langbar position-absolute у скролюваному flex-контейнері з justify-content-center «плавав» — перенесений у header-рядок (спейсер-дзеркало тримає заголовок по центру) + бренд-кольори teal. Верифікація: Playwright 1440px (3×3, langbar top-right) + 390px (1 колонка) — обидва скріни переглянуті адверсарно.
- Беклог 14-TZ §18.4: «← Powrót do kiosku» з кожного екрана; селектор табору для керівника кількох змін («Moje obozy»); full-width адаптивні поля форм. · 🔴 у той самий пакет R4-R9. Оцінка пакета: ~3-5 днів, перед демо клієнту.

**[F-KSK-3] Per-camp статус-панель керівника** (завжди видима): дедлайн Kuratorium 21 дн krajowy / 14 zagraniczny (`deadline_date` ✅ є) + countdown + стан draft→submitted→registered; чек-лист документів ЗАВАНТАЖИТИ (opinia PSP, szkic, KRK/RPS, карти — `checklist_ids` ✅); документи ПОДАТИ; наскрізні індикатори: оплати/рати, рекрутація закрита, програма 100%, страхування, §13-верифікація; нагадування mail.activity/SMS. · 🟡 базова структура є (teczka.ko + checklist); compute-індикатори прогресу і нагадування — доробити. **Як:** compute-поля progress на event + mail.activity генератор; ~2 дні. Тести: `test_regulamin_teczka.py` (суміжно).

**[F-KSK-4] Кабінет керівника = процес-трекер обов'язків** (зібрати KRK, подати в Kuratorium, sanepid/PSP, наповнення дітьми, співбесіди) з нагадуваннями. · 🟡 = [F-KSK-3] + hr_recruitment stages ✅; консолідований трекер-вигляд — у пакеті панелі.

## 4.8 Портал батьків (/my)

*Пояснення: конверсійний кабінет — батько бачить дітей, картки, платежі, повідомлення, історії табору; головна = зміст (Karta dziecka / Płatności / Wiadomości), не ecommerce-заглушка. Джерела: FAYNA_CAMPSCOUT §4, 14-TZ §20, 04-TZ.*

**[F-MY-1] Маршрути /my/*:** home hero, participants (+sign), stories, loyalty, documents, transport, training, support, consents, escort. Створення учасника `/my/participants/new` — з ОБОВ'ЯЗКОВИМ pre-contract consent-блоком (RODO art.6(1)(a), per-child, не per-parent). · ✅ Доказ: 04-TZ verified — усі 9+ routes HTTP 200 (500 на /my/documents виправлено); `/my/escort` + підпис dozwoła/RODO працює (44 escort мігровано) · Тести: `test_role_parent_portal.py`, `test_role_parent_cabinet.py`, `test_escort_signoff.py`, `test_portal_camp_day.py`.

**[F-MY-2] Головна кабінету = зміст** (Karta dziecka / Płatności i faktury / Wiadomości / Dokumenty / Zarezerwuj obóz / Stories / Lojalność). · ✅ PL-версія (verified rodzic.test24, 25.06); UA-версія — після merge R2 ([F-I18N]).

**[F-MY-3] Віконце виховника у батька.** Порожній блок «Twój wychowawca» до призначення; після рекрутації+авто-поділу — виховник дитини видимий; батьки бачать хто виховники і навпаки. · 🟡 D4-видимість record-rule є; блок у /my — не верифіковано скріном. **Як довести:** скрін кабінету з призначеним виховником.

**[F-MY-4] Фото дня / погода дня** для батьків (camp.story published свого заїзду + public-зріз daily.report без службових полів); фото з телефону виховника (capture=camera → upload → прев'ю). · 🟡 stories ✅ (з consent-gate `test_story_photo_consent_gate.py`); погода-день public-зріз і мобільний upload — не верифіковано. **Як:** перевірити daily.report портальний рендер; додати за потреби; ~1 день.

**[F-MY-5] /my/preferences (SMS opt-out)** — батько вимикає SMS (лишає email/push); sms_opt_in / sms_opt_in_marketing на partner. · 🟡 поля opt-in існують (SMS-система їх поважає); окремої сторінки preferences не знайдено. **Як:** додати блок у /my/account або consents; ~0.5 дня.

## 4.9 Чати і сповіщення (SMS 3-tier + discuss)

*Пояснення: не пишемо власний чат — mail.thread чатери (18 моделей) + discuss-канали; SMS — мінімалістичні «зайди подивись» без PII, 3 рівні критичності, cost-guard. Джерела: FAYNA_CAMPSCOUT §5A, 06-TZ §9.6.*

**[F-COM-1] SMS 3-tier:** CRITICAL (bell+email+push+SMS: інциденти, непідписана карта <3 дні, термінові) / IMPORTANT (без SMS) / INFO. Шаблони <50 символів, PII через SMS не йде; шаблони вожатого (Збір/Підйом/Відбій/НЕГАЙНО-Kamilka); SMS дітям лише за sms_consent батька (RODO art.7) + child_mobile, fallback на батька. · ✅ Доказ: `models/sms.py`, `sms_notify.py`, data/sms_*templates.xml, wizard `staff_sms_composer.py` · Тести: у test-gate (SMS cost-guard — заявлено в TZ.md §5 як прогалина → 🟡 прямий тест cost-guard додати).

**[F-COM-2] Cost-guard + immutable audit.** Ліміти 100 SMS/міс вожатий, 300 керівник (ir.config_parameter), cost 0.05 zł/сегмент, preview з recipient count; `camp.staff.sms.log` immutable (retention 7 р.), місячний звіт у дашборді. · ✅ wizard+лог існують (`staff_sms_log.py` immutable) · 🟡 тест на ліміт — додати (~2 год).

**[F-COM-3] Auto-канали discuss per event** («{Camp} — Зміна N»: kierownik+wychowawcy+інструктори; приватний; +30 днів архів після заїзду) + auto-subscribers per модель (карта→батько+kierownik+medical; інцидент→повний список; story→батьки заїзду...). · ✅ staff-канал є (06-TZ §9.6 DONE) · 🟡 повна матриця auto-subscribe по 8 моделях не верифікована.

**[F-COM-4] DM-чат виховник↔батьки своєї групи** (розширення discuss; фіксація всього листування — юр/RODO-слід; RODO art.9 у чаті — окремий ADR: батько напише «дайте ліки»). · 🔴 не збудовано (єдиний великий функціональний гап епіка E). **Як зробити:** ADR (art.9-гейт: попередження/масковані поля) → discuss.channel DM-провізія на призначенні групи (патерн event_channel_create) → чатер-віджет у kiosk/портал; ~2-3 дні. Не блокер cutover, потрібен до сезону-2027 комунікації.

## 4.10 Продажі (dual-path, оферти, місця)

*Пояснення: покупка або через товар (/shop, Path A), або через подію (FB Events, Path B) — обидві приводять у той самий кабінет (RODO+карта); лічильник місць один — event.ticket.seats_available. Джерела: master §2.6.2d, SELLABLE §4-5, FAYNA_CAMPSCOUT §10A.*

**[F-SALE-1] Нативний потік продажу:** sale.order + event_sale → `_init_camp_registrations` → event.registration → `_fayna_get_or_create_participant`; квитки = шар місткості; SKU: service `CS-*` (без року, стабільний URL) + ticket `TCS-*-NN-YY`; один табір = один product.template, зміни = окремі events/tickets. · ✅ Доказ: `commercial.py`; 239 замовлень/277 реєстрацій цілі на staging-копії · Тести: `test_registration_seats.py`, `test_campscout.py`.

**[F-SALE-2] Генератор картки товару `_generate_product_card(event)`** (structured days → daily_routine; активності → activities/highlights; дати/локація/ціна → з event/ticket; канон вигляду = репо `camp/Offer 2026`; обидві програми normal+rain на картці). · ✅ Доказ: `_generate_product_card` у `models/camp.py` [ПЕРЕВІРЕНО: grep] · Тести: `test_card_generator.py` · 🟡 відповідність канону Offer 2026 візуально не доведена — скрін-гейт при демо.

**[F-SALE-3] PDF-оферти (sale_pdf_quote_builder):** 56-стор. каталог → 22 product.document по 12 таборах (COMPANY HEADER 4 стор. + камп-специфічні 3 стор. + auto-quote + FOOTER umowa/RODO/booking 10 стор.). · ✅ ЗАДЕПЛОЄНО НА ПРОД 02.05 (бекап 31МБ, rollback задокументовано) · 🔴 без мапінгу лишились CS-ITA-01-26 (Італія) і SP_01 (Скаутський патруль). **Як:** додати 2 product.document за BP-CAMP-PDF-01..04 (DPI 171, attached_on='inside', per-SKU); ~2 год.

**[F-SALE-4] Розстрочка.** `fayna.payment.installment.*` — ЗАЛИШЕНО (⛔ на видалення: це per-order state machine, НЕ дублікат account.payment.term; критерій «installment не існує в БД» зі старого ТЗ — застарілий, скасовано). · ✅ Доказ: grep `commercial.py`/`camp.py`; моніторинг рат у меню (04-TZ Тир 2).

**[F-SALE-5] Seat counter — єдине джерело:** «вільні місця» на картці читаються виключно з `event.event.ticket.seats_available`; обидва шляхи покупки оновлюють той самий лічильник; seats-from-sales parity з BonSens. · ✅ Тести: `test_registration_seats.py`.

**[F-SALE-6] Публічні маркетинг/сервіс-сторінки (login-free, `auth="public"`, `controllers/kadry_forms.py`):** `/camp/zwrot` — Wniosek o zwrot środків: батько заповнює, client-side PDF → сервер+Telegram+email (аналогічно [F-REC-1a] pipeline); `/camp/oferta/ferie2027` — публічна офера зимових таборів Ферії 2027 (Jugów / Kudowa-Zdrój) для батьків. Обидві — self-contained HTML з `static/src/kadry/`, без порталу/логіну; додано на гілці feat/kadry-wilcza-zlecenia. · ✅ Доказ: `wniosek_zwrot`/`oferta_ferie2027` у `controllers/kadry_forms.py`. 🔁 REUSE-ЦІЛЬ: zwrot інтегрувати з реєстром zwrotів, ferie2027 — з нативним каталогом [F-SALE-2], коли буде час після сезону.

## 4.11 Ціноутворення, VAT, фінанси

*Пояснення: ціна ГЕНЕРУЄТЬСЯ калькулятором cost-build-up у майстрі; VAT-режим — наслідок юридичної форми організатора; факт-витрати йдуть у нативний account з аналітикою per табір; зовнішній бухгалтер отримує евіденцію без доступу в систему. Джерела: 06-TZ §19, 12-TZ §4/§4b-4d, 14-TZ §7/§10.*

**[F-VAT-1] Калькулятор:** `list_price = (Σcost ÷ діти) × (1+markup) × (1+VAT)`; Σcost: проживання/день, харчування/день, кадра (260/300/220 zł/день ÷ діти), страхування, мерч (→ авто-product VAT 23%), канцтовари, операційка, реклама ≤20% бюджету; markup default 5% (editable, ≥5% — ⚪ рішення власника не зафіксовано). · ✅ Доказ: `action_apply_computed_price` (verified 02.07: майстер створює budget з обчисленою ціною) · Тести: `test_pricing_calculator.py`, `test_budget.py`.

**[F-VAT-2] VAT-вердикт (research 24.06, джерела KIS):** послуга табору DEFAULT **zwolniona z VAT** (art.43 ust.1 pkt 24 lit.a — opieka; умови: форма oświaty ≥2 дн, zgłoszenie kuratorium ✓ (25366/WIE/L-2026), реальний nadzór+program); обов'язковий перемикач `zw.` ↔ `VAT-marża 23%` (art.119; fiskus 2024-25 перекваліфіковує на turystykę, особливо при закупівлі бази/транспорту в інших); мерч завжди 23%; кадра zlecenie = поза VAT; підпис «zwolniona», НЕ «маржа 0%». ⛔ «дитячий одяг 5%» — викреслено. · ✅ vat_mode у wizard · ⚪ **[ЛЮДИНА, перед прод-калькулятором]:** księgowa + власна interpretacja indywidualna до KIS (забетонувати zw., зняти ризик domiaru).

**[F-VAT-3] Форма організатора при створенні** (SaaS-ready): фірма (rejestr turystyki: № wpisu; VAT-marża; zaliczki) vs fundacja/NGO (KRS; без marży; може безкоштовно); дані на оферті/фактурах/договорі (колонтитули). Native: `account.fiscal.position` + поля company/partner + QWeb header/footer. · ✅ Доказ: fiscal_position у wizard [ПЕРЕВІРЕНО: grep] · 🟡 повний ланцюг «форма → колонтитули оферти/умови» скріном не доведено.

**[F-FIN-1] Факт-витрати → P&L:** керівник вантажить faktury (vendor bill) з прив'язкою до `account.analytic.account` табору; категорії reuse camp.budget.category; звірка план (camp.budget/BEP) ↔ факт (account); НЕ custom-бухгалтерія. · 🟡 budget+BEP ✅ (тести); аналітика-автостворення на турнус і кабінет-upload фактур — не верифіковано. **Як довести/зробити:** перевірити analytic на event-create; додати upload-роут у кіоск керівника; ~1-2 дні.

**[F-FIN-2] Евіденція для зовнішнього бухгалтера:** кнопка «Скачати евіденцію» (PDF+XLSX: доходи/витрати/сальдо/VAT по табору) + авто-надсилання на пошту; фактури бухгалтер бере в KSeF (шлемо через `l10n_pl_ksef_margin`); бухгалтер НЕ має Odoo-доступу → архітектурно зникає art.9-ризик. · 🟡 PDF-частина Є (з 25.06; канон 03.07 помилково позначив 🔴): `action_print_evidence` + `action_send_evidence_to_ksiegowa` (PDF на email + chatter-лог) — `models/budget.py:587,594`, шаблон `reports/budget_evidence_templates.xml` (`report_camp_budget_evidence`), opt-in місячний cron. ЗАЛИШОК: XLSX-формат + кнопка на панелі [F-KSK-3]; ~0.5-1 день.

**[F-FIN-3] BEP-сигналізатор:** формула коректна (`budget.py:373`: denominator=price−variable, guard price unset); динаміка: збитково→перетин→прибутково. **Рішення власника (кодифіковано в ТЗ 06.07, раніше жило лише в docstring теста):** publish/активація нижче BEP → ПОПЕРЕДЖЕННЯ, НЕ hard-block (`_onchange_website_published_bep_warning`, budget.py; test_bep_activation_warning.py). Недобір → скасування = окрема вимога [F-FIN-5]. · ✅ формула+guard+warning · Тести: `test_bep_activation_warning.py` · 🔴 розрив: 69 sale.order із przychód=0 — продажі НЕ живлять price_per_child/przychód автоматично (знахідка 02.07). **Як:** прогнати повний флоу через майстер+ціну; якщо розрив підтвердиться — compute przychód з sale.order по event; ~1 день. ⚠️ без цього BEP-панель бреше. **Критерій (EARS):** WHEN sale.order підтверджено і прив'язано до event, THEN przychód і price_per_child події оновлюються автоматично; sale.order з przychód=0 при підтверджених продажах = 0 записів. · Верифікація: analyze (SQL-аудит: 69→0) + test (новий SO → BEP-панель оновилась).

**[F-FIN-4] Дві маржі (рішення R8 спринту):** VAT-маржа (art.119, лише koszty «dla bezpośredniej korzyści turysty») ≠ бізнес-маржа (з рекламою/кадрою/overhead); довідник категорій витрат з прапорцями stały/zmienny + «до VAT-маржі»: ośrodek, transport, wyżywienie/доба, кадра (ставки [F-VAT-1]), ubezpieczenie NNW, atrakcje, reklama (лише бізнес-маржа), gadżety COGS, inne. Звіти для księgowej: **Zestawienie obozów** (przychód/koszty/обидві маржі) + **Rejestr faktur за місяць** (numer, kontrahent, obóz, data zapłaty, kwota marża / kwota gadżety) — стик l10n_pl_ksef_margin (поле P_PMarzy). · 🟡 категорії+BEP є; **Zestawienie-звіти Є** (`report_budget_zestawienie` «Zestawienie obozu» + `report_season_budgets` «Zestawienie obozów», обидві маржі — `reports/budget_report_templates.xml`; канон 03.07 помилково числив незбудованими). ЗАЛИШОК: Rejestr faktur za miesiąc (TODO-коментар у шаблоні) + заповнення P_PMarzy — разом з [F-VAT-4].

**[F-FIN-5] Скасування збиткового заїзду (недобір нижче BEP).** Винесено з [F-FIN-3] окремою вимогою (вимога власника була вкладена без ID/статусу). **Критерій (EARS):** WHEN настає дедлайн рішення і заїзд нижче BEP, THEN організатор одним wizard-ом скасовує заїзд: cancel реєстрацій + авто-повідомлення батькам (SMS CRITICAL + email) + повне повернення коштів + звільнення місць + лог рішення. · 🔴 не збудовано; ЗАЛЕЖИТЬ від refund-механізму (§8 п.7b — зараз заглушка `_schedule_refund`). **Як:** wizard «Скасувати заїзд» на event з підтвердженням → ланцюг cancel+refund+notify; ~1-2 дні після 7b.

**[F-VAT-4] Invoice-side VAT-marża (фактура + KSeF) — розрив ланцюга.** Калькулятор ([F-VAT-1]) і бюджет ([F-FIN-4]) марżу РАХУЮТЬ, але фактура при vat_mode=marża її НЕ несе: майстер ставить пласку ціну, ПДВ «рахує księgowa» — ланцюг калькулятор→фактура→KSeF розірваний. **Критерій (EARS):** WHEN виставляється фактура заїзду з vat_mode=marża, THEN податкова база = маржа (ціна − koszty з прапорцем «до VAT-маржі» з camp.budget/analytic), фактура несе позначку «Procedura marży dla biur podróży» БЕЗ ставки/суми VAT на рядку (art.119), а KSeF-експорт FA(3) заповнює P_PMarzy через `l10n_pl_ksef_margin`. · 🔴 не збудовано: `sale_margin` / `account_tax_python` / `l10n_pl_ksef_margin` відсутні в depends (grep manifest = 0; лише коментарі budget.py). **Як (design 01.07; money-critical — ЛИШЕ після «ок» власника, на staging з приймання księgowej):** depends += sale_margin; `purchase_price` на sale.order.line = Σ vat_marza-костів (лише usługi nabyte, НЕ własne — split уже змодельований `category_id.vat_marza`); VAT-marża tax через account_tax_python (23% від margin) у fiscal_position marza; zaliczka→korekta (down-payment на прогноз-маржу → фінальна фактура за фактом, art.119); стик l10n_pl_ksef_margin → KSeF. Зв'язано: ⚪ interpretacja indywidualna ([F-VAT-2], §11 п.8). · Верифікація: test (фікстура заїзду з костами → account.move з базою=маржа) + приймання księgowej на реальному турнусі.

## 4.12 Харчування, транспорт, лояльність, тренінги, звіти

*Пояснення: підтримні підсистеми, збудовані ще до конвеєра; всі native-first. Джерело: SELLABLE §3 (аудит 79 моделей).*

**[F-OPS-1] Харчування:** EU-14 алергени (data/camp_allergens.xml), дієт-профілі, меню; агрегат дієт/алергій для кухні по табору. · ✅ моделі nutrition.py — keeper-и після reuse S1: `camp.diet.profile` (пара 4, PR#36: 2×діет-профілі злиті, фікс ACL-дірки, jsonb-міграція 17.0.4.1.5) + `camp.menu.day` (пара 3, PR#35: legacy camp.nutrition видалено) + `camp.meal.plan(.line)` · 🟡 агрегат-витяг для кухні (зведення «2 ліки, 4 окуляри...» для виховника) — довести/додати view; ~1 день. Diet-counts compute свідомо відкладено (art.9-зона) — тепер закривається разом з [F-RODO-2].

**[F-OPS-2] Транспорт:** `camp.transport` (груповий автобус: локації, час, транспорт, водій, participant_ids) + `/my/transport`. · ✅. **Escort/konwój (індивідуальний супровід):** `camp.escort` (поля: participant_id, registration_id, direction tam/powrót/oba, home_city, pkp_station, departure/arrival_datetime, transport_mode pociag/autokar/własny, escort_person name/phone/doc, medical_help_consent+date+IP, parent_signature+signed date/IP/by, rodo_consent_id, state; immutable draft→collected→signed за патерном _PROTECTED_AFTER_SIGNOFF) + QWeb dozwoła+RODO; 81 SO з продуктом 204 → escort-записи (44 мігровано, скрипт populate_escort_from_204). · ✅ Тести: `test_escort_signoff.py`.

**[F-OPS-3] Лояльність:** розширення нативного loyalty.program (BP-011: fayna_rule_type + override _program_check_compute_points; banda/platinum/gold). · ✅.

**[F-OPS-4] Тренінги кадри:** MEN 36h/10h + wychowawca/kierownik/first_aid/online_platform — ЄДИНИЙ keeper `camp.staff.training.record` (extends native `slide.channel`, website_slides). Reuse S1 пара 6 (05.07): три системи обліку (vozhatyi.training.record ⇄ fayna.vozhatyi.training+module+certificate ⇄ camp.staff.training.record) злиті в одну; сесійна логістика (дата/локація/instructor) + printable QWeb-сертифікат + expiry-cron перенесені на keeper; /my/training портал-маршрут НЕ збудований (був лише заявлений у ТЗ, коду не було — реальний контролер-споживач: `/admin/dashboard` виджет прострочених сертифікатів). · ✅ модель+cron+ACL/rules; 🟡 /my/training портал-кабінет — не збудовано (backlog).

**[F-OPS-5] Звіти/снапшоти:** `camp.analytics.snapshot` (keeper пари 1, PR#32; `camp.stats.snapshot` видалено — тест `test_analytics_snapshot.py`) + `camp.marketing.report` + `/admin/dashboard` KPI (7 секцій: бізнес, тривоги, активні табори, команда, комунікації, маркетинг+SMS-costs, audit) + view-as (with_user, НЕ sudo; immutable `camp.admin.access.log` RODO art.30, 7 років). · ✅ дашборд+view-as+лог · ✅ R10 закрито 2026-07-04: `compute_sudo=True` на всю групу `_compute_metrics` (marketing.report) і `_compute_ack_stats` (regulamin; корінь — stored all_signed мав дефолт True, non-stored сусіди False). Верифікація: test ✅ `test_compute_sudo_consistency.py` (модуль-wide гард груп compute) + старт без warning (харнес-лог).

**[F-OPS-6] Dziennik zajęć (Zał.5)** per camp.group (учасники ≤20; тижневі плани; щоденні записи; uwagi kierownika/KO) + activate/submit workflow + PDF. · ✅ Доказ: 04-TZ Тир 1-2 (форми+workflow), ADR «3 dziennik-моделі — РІЗНІ сутності, НЕ дубль» (⛔ злиття відхилено) · Тести: `test_role_kierownik_dziennik.py`, `test_dziennik_pdf.py`.

## 4.13 Документи, teczka, retention

*Пояснення: жодного окремого «сховища документів» — кожен файл живе ir.attachment на своєму нативному записі; teczka = view-агрегатор + збірка ZIP on-demand на контроль KO. Джерела: 12-TZ §6b-6c, master §9.*

**[F-DOC-1] Реєстр «де живе кожен документ»:** продаж/фінанси → native (оферта=product+QWeb; umowa=sale.order+sign; фактури=account.move; рати=payment.term/installment; поліса=attachment на event+move); правне → custom+attachment (zgłoszenie=teczka.ko; karta=participant; program=camp.program.structured(+.day); dziennik; opinia PSP/sanepid=attachment); кадри §13 → hr.employee attachments + staff cert; RODO → fayna_rodo_compliance. ~90% документів = native. · ✅ архітектура діє.

**[F-DOC-2] Teczka: збірка on-demand.** Кнопка «Завантажити teczkę» → controller збирає attachments + `_render_qweb_pdf` (karty/program/dziennik) → ZIP + об'єднаний PDF з титулкою-реєстром; свіжа генерація, без копій. Складники: оферта, договір, фактури, karty всіх дітей, program, dziennik, zgłoszenie, KRK+świadectwa, PSP+sanepid+szkic, поліса, RODO-zgody. · 🟡 teczka.ko+чеклист є (`test_regulamin_teczka.py`); ZIP-збірка одним кліком — не верифікована. **Як:** controller-stream zip + PDF-merge (OCA report_* / PyPDF); ~1-2 дні.

**[F-DOC-3] Вибір галочками + «Надіслати інспектору»** (mail.compose.message з вибраними attachment, лог у chatter табору). · 🔴 не збудовано. **Як:** wizard з o2m-чеклистом → compose; ~1 день.

**[F-DOC-4] Retention-матриця (авто-виконання):** карти/медичні/journal/звіти/staff-доки/підписи = 7 років (art.118 k.c. 6 р. + буфер; пауза при справі в суді); umowy кадри 10 р. (art.94 k.p.); фінанси/KSeF 5 р.+рік (art.74 o rachunkowości); фото stories 2 р. або до відкликання (art.81 Prawa autorskiego); marketing-згоди — до відкликання. Кваліфікації (świadectwa курсів) — permanent. · ✅ політика зафіксована; 🔴 авто-cron не збудований; формула строку: `max(date_end останньої реєстрації, signed_date) + 7 років` → flag to_erase → перевірка активних claims (пауза при справі) → лог erasure. **Як:** ir.cron daily + wizard-підтвердження; ~1-2 дні; не блокер сезону (перші видалення — 2033).

## 4.14 Двомовність PL/UA (i18n) — R2+R3

*Пояснення: аудиторія — українські діти в Польщі; дефолт PL (рішення власника), повне перемикання UA всюди (kiosk + /my). Джерела: REPAIR R2-R3, R2_STATUS.*

**[F-I18N-1] Перемикач мови:** kiosk (OWL langbar + endpoint `/camp/kiosk/set_lang`, persist на res.users.lang, звужено до PL/UA) + portal (`portal.language_selector` у шапці /my); вибір зберігається після перезаходу. · ✅ код (PR #15: a696ee0+f802a68+1ed0df8); обидва гейти PASS (reviewer high: upgrade-gap закрито migration `17.0.4.1.0`; QA: kiosk 9/9 UA, кабінет 100% UA bidirectional) · Доказ grep: set_lang у `controllers/kiosk.py` · **✅ MERGED 04.07 (PR#17):** art9-ізоляція доведена ЦІЛОЮ (leak-асерти зелені; тести зроблено i18n-aware — tests/http_lang.py), .po-дублі 0 (дедуп за .pot), ruff чистий; staging задеплоєно (run 28699005633), мови активні (psql). i18n-backfill uk_UA 909→0 (PR#22). **Критерій (EARS):** WHEN користувач обирає мову в kiosk або /my, THEN UI перемикається PL↔UA, вибір зберігається на res.users.lang і переживає relogin; PR #15: 0 падінь art9-тестів, 0 .po-дублів, 0 ruff-порушень. · Верифікація: test (e2e перемикання+persist) + CI green.

**[F-I18N-2] Нуль хардкоду мов у шаблонах (R3):** всі UI-рядки через `_()`/`_lt` з перекладом; `.pot` регенерований (code-ref!); 281/281 рядків UA/PL перекладено (gemini під msgfmt-гейт); пастка: model_terms-переклад без code:-reference невидимий для `_lt()`. · ✅ у PR #15 · Тести: msgfmt clean; DoD-grep: хардкод у templates/ = 0.

**[F-I18N-3] Правила процесу i18n:** `odoo -u` НЕ перезаписує переклади → деплой з `--i18n-overwrite`; OCA `--fix` зносить self-translations, po-pretty-format вимкнено; термінологія kierownik≠wychowawca — звірка людиною; help= на кожному user-facing полі; en_US — post-prod (⏸ рішення власника). · ✅ зафіксовано як інваріанти.
---

# 5. Нефункціональні вимоги

*Пояснення розділу: якість, без якої функції не рахуються готовими. Категорія ризику проєкту: HIGH / LIFE-CRITICAL (медичні дані дітей: помилка доступу/рендеру → неправильні ліки → анафілаксія; юридична відповідальність організатора особиста; RODO-штраф до 4% обороту). Звідси — жодних шорткатів у medical/qualification/emergency. Джерела: master §1.4a, §4, 14-TZ §18-19.*

**[N-1] UX (10 евристик Нільсена) як гейт.** Жоден екран жодної ролі не «готовий» без прогону ux-nielsen-reviewer (скріншот-аудит); FAIL по критичних (3/6/8/9) = не готово; новий екран — спершу /ux-design. · ✅ процес закріплено (субагент+скіли встановлені); урок 02.07: хвалебний ux-огляд = безвартісний → промпт ока адверсарний. Автоматизація гейта скрінами в CI — [T-5]. · Поточні порушення = R4/R4b/R7-R9 ([F-KSK-2]).

**[N-2] Mobile-first кіосків і порталу.** Виховники/керівники в полі з телефонів: touch ≥44px, контраст WCAG AA, PDF читається, фото-upload з камери працює, чат читабельний. Гейт: mobile-audit на РЕАЛЬНОМУ телефоні перед «готово» кожного екрана (responsive-grid недостатньо); обов'язковий для будь-яких змін /my/*. · 🟡 портал-аудит разовий був; систематичний прогін по всіх екранах перед cutover — у чеклісті prod-gate.

**[N-3] Надійність:** [A-4] + продажі/оплати не блокуються збоєм оболонки; graceful degradation. Продуктивність (цілі master §7): checkout <500ms; submit карти <500ms; список 10k <1s; звіт <10s; cron <60s. · 🟡 цілі зафіксовані; вимірів (бенчмарків) нема — [GAP-5].

**[N-4] Безпека:** OWASP Top 10 чекліст per реліз; CI: bandit/gitleaks/safety (ruff S*); секрети поза git (ir.config_parameter, GitHub Secrets; BP-010 фільтр при читанні конфігів); impersonation НЕ sudo (with_user + HMAC-патерн BP-004, audit-лог); IDOR-уроки: /api/v1 повністю видалено 02.07 (P4.3: 0 споживачів + IDOR у story_detail повз consent-gate — ADR: native /my/* покриває). Публічна форма заявок: honeypot + rate-limit + mime-whitelist — 🔴 (беклог №10, ~5-8 год). · ✅ ядро; пентест ZAP weekly — [GAP-4].

**[N-5] Data safety:** бекапи перед кожним `-u`/міграцією; lossless-інваріант row-count (розділ 7); staging-нейтралізація (mail/SMS/crons off) при рефреші з прода; ⚠️ scratchpad-стенд ≠ git (синхронізувати перед -u — урок R1). · ✅ практики діють (бекап 31МБ перед PDF-деплоєм; staging_sync.sh).

---

# 6. Тестування

*Пояснення розділу: що реально покрито тестами і чим доводиться кожна вимога. Піраміда: unit ~60% / integration ~30% / e2e ~10%; ціль coverage ≥70% критичних шляхів (ЗАКОН master §4.6). Творець ≠ гейт: QA-агент окремий від автора коду.*

**[T-1] Unit/integration: 43 тест-файли** (зріз 2026-07-06; джерело правди — `ls tests/test_*.py`, число НЕ підтримується вручну) — головні групи:
- Правові: `test_karta_2026/karta_pdf` (wzór 2026+PDF), `test_incident_card` (§11/§12), `test_staffing` (RSPTS §13), `test_rodo_consent_immutable`, `test_signoff_rodo`, `test_escort_signoff`, `test_art9_access`, `test_art9_http_isolation` (HTTP-ізоляція; червоні PR#15 закриті 04.07 у PR#17 — [F-RODO-2]).
- Ролеві (experiential у коді): 9× `test_role_*` (organizator/parent×4/kierownik/wychowawca×2/instructor/public_vacancies) + `test_role_canon` (ADR-22).
- Домені: `test_camp_group` (art.92c), `test_phase_c_wychowawca`, `test_phase_d_split` (round-robin), `test_program_skeleton` (≥9 год), `test_native_approval`, `test_pricing_calculator`, `test_budget`, `test_bep_activation_warning`, `test_registration_seats`, `test_card_generator`, `test_dziennik_pdf`, `test_regulamin_teczka`, `test_portal_camp_day`, `test_story_photo_consent_gate`, `test_campscout`(+extended), `test_scaffold`.
- Reuse-міграційні (S1, 05.07): `test_analytics_snapshot`, `test_legacy_program_migration`, `test_training_migration`.

**[T-2] CI-гейти (обов'язкові на кожен PR):** Lint (ruff+ruff-format+bandit+gitleaks+OCA checks-odoo-module+checks-po) + **test-gate: повний модульний сьют** (число тестів росте — джерело правди: останній зелений CI-run на main, НЕ це речення) + module-upgrade dry-run. Доказ дієвості: PR #14 merged лише після зеленого; PR #15 утримувався червоним до RCA (закрито 04.07, PR#17). · ✅ [ПЕРЕВІРЕНО: gh run list main 05.07 — success на 5f907ff]. Branch protection: review approval + up-to-date. ⚠️ Сліпа зона CI: `-i` ставить модуль з нуля — data-міграції migrations/ на СТАРИХ даних CI не проганяє (потрібна репетиція на staging-копії перед `-u`).

**[T-3] E2E:** `tests/e2e/test_critical_paths.py` (Playwright) + workflow `e2e.yml` на staging (зелений з 02.07; networkidle-антипатерн виправлено на wait_for_url). QA-Playwright-агенти конвеєра: наскрізні прогони майстра (8 кроків), двомовності (9/9 UA kiosk, кабінет 100% UA), зі скрінами. · ✅.

**[T-4] Відомі тестові борги:** 🟡 coverage зведено 04.07: 69% (docs/QUALITY_AUDIT_2026-07-04.md; ціль ≥70%, дельта ~90 stmts); 🔴 pytest-матриця RODO роль×модель×операція (беклог №13, ~4-6 год); 🟡 прямі тести: Kamilka-ескалація cron, SMS cost-guard ліміт, declaracja-блокування, attachment-ACL PDF (auto-refusal cron ✅ 04.07 test_auto_refusal_cron); 🔴 performance-бенчмарки [N-3]; 🔴 UAT з живими користувачами (usability-test-plan) перед prod — процедура: staging → тестер CampScout ops → кроки в docs/TESTING.md → sign-off у PR; без sign-off прод заборонений.

**[T-5] Візуальний AI-гейт (скрін-тести; рішення власника 04.07).** Причина: kiosk home пройшов CI і код-рев'ю, але на десктопі виглядав зламаним ([F-KSK-2] R4b) — текстові гейти рендер не бачать. Вимога: Playwright знімає full-page скріни ключових екранів (kiosk home per роль; /my home; майстер крок 1) у матриці 2 в'юпорти (desktop 1440×900, mobile 390×844) × 2 мови (PL/UA); скріни йдуть адверсарному AI-оглядачу (ux-nielsen-reviewer, промпт «знайди, що зламано» — урок 02.07 про хвалебний огляд). FAIL-критерії: layout не відповідає в'юпорту (mobile-верстка на десктопі й навпаки), елемент не на задекларованому місці (розбіжність код↔рендер), сирий/обрізаний/неперекладений текст, порушення критичних евристик 3/6/8/9 [N-1]. · 🔴 збудувати: стик з e2e.yml (Playwright на staging вже є) — screenshot-джоб + AI-огляд, скріни = артефакт CI-рана; ~1-2 дні. **Критерій (EARS):** WHEN PR змінює UI портальної/кіоскової частини (templates/, static/, views/), THEN CI продукує матрицю скрінів 2×2 і AI-вердикт; merge при FAIL заборонений. · Верифікація: перший прогін мусить зловити R4b (регресійний еталон).

---

# 7. Міграція даних і prod-cutover

*Пояснення розділу: найризикованіша частина проєкту. Це НЕ ETL між базами — зміна власності в одній БД: (1) detach бізнес-даних legacy від ir_model_data (інакше uninstall ВИДАЛИТЬ 24 табори каскадом по замовленнях 157/227k zł); (2) bs_*-картки → camp.participant; (3) RODO-extract ПЕРЕД будь-яким detach (код RODO campscout_management існує ЛИШЕ на проді, не в git — втрата назавжди). Джерела: TZ-migracja (M0 verified live 23.06), PLAN P1, 12-TZ §6p.*

**[M-1] Інвентар (M0, підтверджено на проді 23.06):** campscout_management installed (владіє: product.template=24, attribute.value=21, views=8, menus=4, events=3, tickets=3); bs-дані: child=124, consent=122, qualification_pdf=117, підписи bs=107 (native sale.signature 448 = нескоуп); продукт 204 (asysta): 81 SO / 83 дитини. · ✅ SQL-верифікація виконана.

**[M-2] Скрипти (всі: ідемпотентні, DRY_RUN-first, savepoints, відрепетирувані на прод-копії):** `populate_from_bs.py` (114 дітей; дата-парсер 4 формати, неуспіх → migration_needs_review), `migrate_bs_signatures.py` (97→107 підписів у qualification_signature ДО freeze), `populate_escort_from_204.py` (44), `populate_children_and_events.py`, `populate_step2/3.py`, `detach_campscout_management.py` (54 лінки, реверсивний: зріз ir_model_data у CSV-лог), `migrations/17.0.4.0.0/post-migrate.py`. Detach НЕ чіпає views/mail.template/menus (то КОД — перестворюється окремо). · ✅ P1.1-P1.3 done+rehearsed; lossless доведено (114 дітей, 97 підписів, detach+uninstall = 0 втрат).

**[M-2b] Залишкова BonSens-parity перед uninstall:** 🔴 product↔event лінки перенесено 42/59 (решту домапити); 🔴 bs_organizer_signature (res.company) → звірити з джерелом підпису організатора у портал-karta (=Q5). **Як:** дописати мапінг у detach/populate + контрольна звірка 59/59; ~0.5 дня; ДО uninstall-вікна (не блокує install/detach).

**[M-3] 🔴 RODO-extract скрипт — ПЕРЕД detach (GOTCHA §6p).** Витягти згоди з `bs_client_consent` (~122) і prod-only `rodo_consent.py`/`res_partner_consent.py` (campscout_management, НЕ в git; бекап коду почато 22.06 в ops/). **Як зробити:** скрипт консолідації у fayna_rodo_consent_log (source='bs'/'legacy') + звірка counts; вставити у послідовність кроком 4. Без нього uninstall = втрата згод назавжди. **Критерій (EARS):** WHEN виконується detach legacy, THEN усі RODO-згоди з bs_client_consent (~122) і prod-only rodo_consent/res_partner_consent ПОПЕРЕДНЬО зконсолідовані у fayna_rodo_consent_log; counts джерело=ціль. · Верифікація: inspect (SQL-звірка counts до/після).

**[M-4] Послідовність прода (M3, нічне вікно, лише за явним «ок»):** backup (pg_dump -Fc + filestore checksum) → install portal+rodo (`-i --no-http`, без нейтралізації — прод живий) → populate_from_bs (dry→commit) → **RODO-extract** → migrate_signatures → escort → detach (dry→commit) → verify §M-5 → uninstall legacy = ОКРЕМЕ вікно пізніше (на сезон — Strangler «поруч»). Стратегія: портал ПОРУЧ зі старим, без uninstall до feature-parity. **Критерії (EARS, атомарно):** (а) WHILE портал розгорнутий, THEN legacy працює паралельно без жодного збою своїх функцій; (б) uninstall legacy дозволений ЛИШЕ після 100% feature-parity, підтвердженого UAT. · Верифікація: analyze (моніторинг обох) + demo/UAT. · 🔴 НЕ виконано (P1.4 — головне плече, що лишилось). Передумови: свіжа репетиція на СВІЖІЙ прод-копії (staging = фото 23.06, застаріле) + завершені [F-RODO-7] інфра-мандат + чисті CI.

**[M-5] Критерії приймання cutover (gate):** row-count ДО=ПІСЛЯ по 8 таблицях (product/event/ticket/SO/SOL/registration/partner) + 9 перевірок: PDF-карти 81=81; підписи 107=107; згоди ≈ (різниця → CSV); ir_model_data legacy=0 після detach; uninstall не змінює product-count; grep назв таборів у data/ = 0; escort 81 draft; RODO-log append-only; migration_needs_review → CSV. + smoke 7 кабінетів + /shop 200. Будь-який розрив на staging = СТОП, не на прод. · ✅ визначено; виконання = P1.4. **Критерії (EARS):** row-count 8 таблиць ДО=ПІСЛЯ (точна рівність); PDF 81=81; підписи 107=107; smoke-логін+базова дія у 7 кабінетах = 7/7 pass. · Верифікація: inspect (SQL-порівняння) + test (smoke-скрипт).

**[M-6] Rollback:** L1 git revert (код) / L2 revert+`-u` (manifest) / L3 pg_restore (schema; ≤15 хв) / L4 повний DR. Бекап ≤1 год перед деплоєм. · ✅ практика; 🔴 DR-drill (відпрацювання відновлення) жодного разу не проведено — [GAP-6].

**[M-7] Відкриті питання міграції (⚪ власник):** Q2 кабінет карт — портал повністю (рекомендовано) чи BonSens перехідно; Q3 дублі-продукти (загальні vs датовані) — зливати?; Q4 website.page legal — detach зараз чи після перестворення (рекомендовано б); Q5 bs_organizer_signature → джерело підпису організатора; Q6 мова/к-сть RODO-звітів супроводу (юрист); Q8 Meta-CAPI поля лишаються в crm.lead (підтвердити); Q9 escort: авто-draft для 81 SO чи вручну + чи гейт перед заїздом; Q10 вікно міграції при живій касі (install+detach ок, uninstall окремо).

---

# 8. Ремонтний беклог (актуальний стан на 2026-07-06)

*Пояснення розділу: жива дельта до цільового стану. Джерела: REPAIR_TZ R1-R10 (тест 02.07), беклог продажу 14-TZ §20, знахідки TZ_UPDATE. Після виконання пункт викреслюється тут; якщо ремонт міняє цільову поведінку — спершу правиться відповідний розділ вище.*

> **Анти-дрейф (правило 06.07, після інциденту потрійного розсинхрону §8/STEP1_TZ/kanban):** статус вимоги живе ЛИШЕ в місці її визначення (§0-7, §12); §8 — черга-посилання БЕЗ власного статусу. PR, що закриває пункт, викреслює його тут У ТОМУ Ж diff (узагальнення [S1-5] на всі PR). Kanban = крос-проєктне дзеркало з датою зрізу, не джерело.

**Закрито:** R1 майстер (✅ merged fd9dad2 + staging); організатор-порожній-екран (✅ 093cab4); кіоск керівника + i18n бекенду керівника (✅); ACL-аудит (✅); ліцензія OPL-1 порталу (✅); /api/v1 IDOR (✅ видалено); PDF-оферти (✅ прод).

**У процесі:**
- ~~R2+R3 двомовність~~ ✅ 04.07 (PR#17+#22, staging живий). Додатково закрито тестами 04.07: /my/escort список+лічильник (порожні для батьків), /my/escort/<id> деталь+підпис (303 всім власникам), /admin/as-parent (порожній при user-акаунті) — PR#23; R7 частково (breadcrumb, PR#25).

**Черга (пріоритет: перед демо клієнту → перед cutover → сезонні):**
1. **‼ ПРІОРИТЕТ №1 (власник 04.07, скрін staging):** R4+R4b desktop kiosk (mobile-layout на десктопі, плитки-гіганти; langbar PL/UA посеред правого краю → у шапку) + R5 бренд + R8 кольори + R9 заголовок/контекст + «Powrót do kiosku»/селектор табору — пакет [F-KSK-2]; DoD = візуальний AI-гейт [T-5] (перший прогін мусить ловити R4b); ~3-5 дн.
2. ~~R6 форми wypoczynku (+2 опції MEN)~~ ✅ 2026-07-04 (test_vacation_forms, PR#20). 2b. ~~R6.1 wizard губив vacation_form при створенні~~ ✅ 2026-07-04: лендинг на event.vacation_form (нове поле, повний каталог MEN) + onchange-префіл kuratorium notification з гардом каталогу; тест у test_role_organizator_create_camp (PR#24).
3. R7 мікрокопі — дочистити, ~0.5 дн.
4. ~~R10 compute_sudo~~ ✅ 2026-07-04 (test_compute_sudo_consistency, модуль-wide гард).
5. BEP-розрив продажі→ціна [F-FIN-3] — ~1 дн. (перевірити флоу через майстер).
6. ~~Karta wypadku п.9 opis-поле [F-KAM-2]~~ ✅ закрито 2026-07-04 (тест `test_card_report_renders_16_points_with_opis`; було внутрішнє протиріччя канону — §4.6 ✅ vs черга тут).
7. ~~Auto-refusal cron верифікація [F-KKW-6]~~ ✅ 04.07 (test_auto_refusal_cron, 3/3). 7b. **Auto-refusal REFUND** — реалізувати справжнє повернення (зараз placeholder-лог у _schedule_refund) — ~0.5-1 дн.
8. Attachment-ACL PDF + тест [F-RODO-2] — ~1 дн.
9. Картка-еталон фірми + брендинг company [F-KKW-7] — ~1 дн.
10. Пакет документів виховника (кейс Даніеля) [F-REC-3] — ~1-2 дн.
11. Teczka ZIP one-click [F-DOC-2] + надсилання інспектору [F-DOC-3] — ~2-3 дн.
12. Евіденція бухгалтеру [F-FIN-2] — залишок XLSX+кнопка панелі, ~0.5-1 дн (PDF+email+cron уже Є — див. [F-FIN-2]).
13. DM-чат виховник↔батьки [F-COM-4] — ~2-3 дн.
14. Публічна форма заявок: honeypot/rate-limit [N-4] — ~1 дн.
15. Звена + лідери [GAP-2] — ~1-2 дн.
16. Retention-cron [F-DOC-4], UODO-export [F-RODO-6], SMS-адаптери PL [P-3], термінологічний шар [R-5] — після cutover.
17. **REUSE-МІГРАЦІЯ (аудит 04.07; звіт docs/reuse-audit/2026-07-04/; kanban). ПОЛІТИКА Community-only (рішення власника 04.07): кроки з OCA СКАСОВАНО** — support-запити й розстрочки лишаються нашим кодом (робочі; ~834 LOC підтримуємо самі). Актуальний план, кожен крок = окреме ТЗ + «ок»: (1) ~~злити внутрішні дублікати~~ — ✅ **ЗАВЕРШЕНО 05.07, 6/6 пар** (PR#32 `camp.analytics.snapshot` · PR#34 `camp.daily.report` · PR#35 `camp.menu.day` · PR#36 `camp.diet.profile` · PR#37 `camp.program.structured` · PR#38 `camp.staff.training.record`; data-міграції 17.0.4.1.5–.7; ⚠️ на staging прогнано лише pair4 — pair5/6 `-u` чекає, див. loop-статус 05.07); (2) SMS-шаблони → sms.template + лояльність → loyalty.card (стандарт Community, уже в depends); (3) рекрутація → hr_recruitment (стандарт Community); (4) ⚪ story → website_blog + review → rating (ТЕЖ стандарт Community — політика Community-only їх НЕ скасовує; випали з плану 04.07 мовчки — рішення власника: мігрувати чи явно лишити свій код). Зачеплені вимоги отримують reuse-мітку в місці визначення.
18. **‼ БЛОКЕР перед `-u` staging (адверсарне ревʼю 06.07, 2 незалежні агенти):** data-міграції reuse S1 (п.17 крок 1) мають дефекти, невидимі для CI ([T-2] сліпа зона — CI ставить модуль з нуля):
    - (а) **pair4 `migrations/17.0.4.1.5/post-migrate.py:26`** — legacy-колонки diet (`translate=True` → jsonb) читаються як сирий текст: `CONCAT_WS(d.dietary_restrictions, d.notes)` → diet-нотатки дітей (art.9) стають подвійно загорнутим JSON-сміттям. Фікс: `->>'en_US'` на READ-боці. ✅ [ПЕРЕВІРЕНО 07.07: `ssh staging-campscout` психл — `ir_module_module.latest_version='17.0.4.1.1'`, `camp_diet_profile`=0 рядків, `camp_participant_diet`(legacy)=0 рядків] попереднє «pair4 УЖЕ виконано на staging 05.07» — СПРОСТОВАНО: міграції .5-.8 на staging ЩЕ НЕ застосовані, обидві таблиці порожні → псування НЕ сталось (нема з чого псувати), а не «перевірено й чисто». Ремедіація потрібна лише в майбутньому `-u`, не заднім числом.
    - (б) **pair6 `migrations/17.0.4.1.7/post-migrate.py:129-150`** — дублікати в межах одного джерела (MEN-поновлення: expired-2024 + certified-2026 однієї людини) гинуть мовчки: `ORDER BY id` + ON CONFLICT DO NOTHING лишає НАЙСТАРІШИЙ запис; ir_model_data-мітка загубленого чіпляється до чужого рядка (повторна міграція не добере). + лічильник конфліктів — мертвий код (лог завжди «0», маскує втрату). Фікс: дедуплікація перед вставкою (certified>completed, свіжіший issue_date) + живий лічильник.
    - (в) **pair5 `migrations/17.0.4.1.6/post-migrate.py:167-221`** — stored computes NULL після raw INSERT: `name`/`display_name` (= `_rec_name`!), `day_number`, `day_count` → мігровані програми/дні БЕЗ НАЗВ у всьому UI; рамковий день NULL (пастка `_check_sleep_duration` при першому редагуванні). Фікс: дозаповнити SQL-ом або `env[...]._compute_*`.
    - Мінори (не блокери): переклади pl_PL губляться при розпакуванні `->en_US` (pair4/5); `certificate_number` втратив unique; expiry-cron не фліпає мігровані `completed`; сироти chatter/attachments legacy-моделей (краху нема — толерується ядром). (а)+(б) = блокери цілісності даних; (в) — видимий користувачу дефект.

19. **ФАКТИЧНИЙ СТАН робочого дерева і ПЛАН добивання п.18 (звірено 07.07 `git diff`+`py_compile`, не лише зі слів попередньої сесії — та казала «фікс 2 скелет, фікс 3-5 не зроблено», перевірка показала більше):**
    - **Код готовий (некомічено, робоче дерево):** (а) pair4 READ-бік `migrations/17.0.4.1.5/post-migrate.py` — `->>'en_US'` + COALESCE на pl_PL, обидві мови зберігаються; (б) pair6 дедуплікація `migrations/17.0.4.1.7/post-migrate.py` — кандидати з обох джерел групуються за (partner, bucket), переможець за пріоритетом стану (certified>completed>expired>in_progress>enrolled) → свіжіший `issue_date` → Source B над A → вищий legacy id; програний запис лишає chatter-слід + ir_model_data-мітку на РЕАЛЬНИЙ виграний рядок (не мовчки); (в) pair5 backfill `migrations/17.0.4.1.6/post-migrate.py` — `name`/`day_count`/`day_number`/`display_name` дораховуються через ORM (`_compute_*`+`flush_recordset`) для щойно створених записів; рамковий день (wake_time..lights_out) отримує ORM-дефолти замість NULL. + repair-міграція `migrations/17.0.4.1.8/post-migrate.py` (нова, версія маніфесту бампнута на .8) — лагодить УЖЕ уражені pair4-записи на БД, де стара міграція виконалась (шукає `notes->>'en_US' LIKE '{%'`, ідемпотентна). Усі 4 міграції — `py_compile` OK.
    - **Тести дописані на РЕАЛЬНІЙ jsonb-схемі** (не синтетичний TEXT, який власне й ховав INC-215 у CI): `tests/test_legacy_program_migration.py` (`test_migration_backfills_stored_computes_and_frame_day_defaults`), `tests/test_training_migration.py` (`test_migration_dedup_same_source_duplicate_keeps_strongest_state`, `_create_legacy_schema` з колонками `theme jsonb`/`activity_name jsonb`/`location jsonb`), `tests/test_analytics_snapshot.py` розширено (+166/−19).
    - **НЕ зроблено — план (у цьому порядку, кожен пункт розблоковує наступний):**
      1. ✅ Прогнано 07.07 [ПЕРЕВІРЕНО: `docker run odoo:17.0 ... -d test_camp --test-enable --stop-after-init`]: **1 failed, 0 error(s) of 238 tests**. Провал — `TestAdminDashboard.test_dashboard_renders_for_organizator` (шукає укр. маркер «Кабінет Організатора», рендер віддав пол. «Panel Organizatora» — мовний мисматч тесту, НЕ повʼязаний з INC-215/reuse-міграціями, існував до цих правок, окремий пункт беклогу). Усі INC-215-тести (`test_migration_backfills_stored_computes_and_frame_day_defaults`, `test_migration_dedup_same_source_duplicate_keeps_strongest_state`, 2× `test_migration_lossless_and_idempotent`) відпрацювали БЕЗ FAIL — фікси pair4/5/6 підтверджені на реальній БД, не лише py_compile.
      2. ✅ SQL-перевірка staging ЗРОБЛЕНА 07.07 [ПЕРЕВІРЕНО: ssh staging-campscout]: `ir_module_module.latest_version='17.0.4.1.1'`, `camp_diet_profile`=0, legacy `camp_participant_diet`=0 — pair4 на staging ще НЕ котився (попередній запис «вже виконано 05.07» був хибний), шкоди немає. Repair-міграція 17.0.4.1.8 стане потрібною лише якщо десь інде вже накотили стару .5 без фіксу — на цьому staging не актуально.
      3. Коміт БЕЗ AI-підпису (commit-msg hook INC-214 вже стоїть у цьому репо — перевірить сам).
      4. Коміт data-міграцій вимагає трейлера `Rehearsed-On: <дата/база>` (pre-push hook INC-215) — заповнити РЕАЛЬНОЮ датою/базою прогону з п.1, не заднім числом.
      5. Лише після 1-4 зелені — «запуши».
    - **Статус (а)(б)(в) змінено з 🔴 на 🟡:** код написаний і компілюється, але «зелений тест-сьют на реальній БД» + «staging безпечний» ще НЕ підтверджені цим ходом — не заявляти «готово» до п.1-2.

---

# 9. Процес розробки і гейти

*Пояснення розділу: як ведеться робота, щоб «зелене» було правдою. Джерела: SDLC-процедура (it-project/23), 12-TZ §9, master §21.*

**[PR-1] Конвеєр (творець≠гейт):** діагностика (Explore) → ADR (рядок `Native Odoo:` обов'язковий + platform-reviewer approve) → виконавець → 2 незалежні гейти паралельно (Odoo-reviewer код + QA-Playwright стенд) → CTO fix-forward → PR → CI (Lint+test-gate+e2e) → merge. Кожен REJECT реальний (доведено: соло дало б хибне «зелено» двічі за 02.07). · ✅ діє.

**[PR-2] Verification Iron Law:** «готово/працює» лише з fresh-доказом у тому ж ході (exit code / вивід / рядок); experiential login-as кожною роллю без помилки/сирого поля = частина DoD; adversarial judge (інша модель) + ≥1 programmatic-критерій. · ✅ діє.

**[PR-3] #4ZONES:** Mac → GitHub → staging → prod; жодних правок на серверах; `-u`/restart/deploy — за «ок»; секрети — heredoc, BP-010; людина-в-петлі: deploy, фінал RODO, бізнес-рішення, слова/тон, ціна/VAT. · ✅ діє.

**[PR-4] Правила Odoo-буднів:** clear .pyc перед -u (RCA stale-.pyc); post_init_hook ≠ upgrade (migrations/ для існуючих БД); `-u` не перезаписує переклади (--i18n-overwrite); groups= на root tree/form невалідні в Odoo 17; XML-ID стандартних модулів звіряти в ir_model_data; No-Manual-DB; **asset-only зміни (scss/js/xml-шаблони) ВИМАГАЮТЬ бампу версії маніфеста** — deploy-staging має gated -u, без бампу бандли лишаються старими (RCA R4b 04.07: код на staging новий, рендер старий). · ✅ зафіксовано (уроки INC-014..021, R1/R2).

**[PR-5] Definition of Done фічі:** форма показує всі поля і ЗБЕРІГАЄТЬСЯ; юр-документи заповнюються повністю + workflow; списки з group-by по табору; i18n повний без mixed-language; IA-меню не бреше; авто-розрахунки підключені; кожен кабінет прогнано на staging роллю; mobile-audit для /my/*; ux-гейт [N-1]. · ✅ діє (04-TZ §C, розширено).

**[PR-6] REUSE-ГЕЙТ (аудит 04.07 + політика Community-only, рішення власника 04.07):** джерело перевикористання — ЛИШЕ стандартні модулі Odoo Community (OCA виключено: AGPL несумісна з OPL-1-продажем; «нема стандартного або кривий/костильний → пишемо свій модуль», дослівно власник). ПЕРЕД створенням будь-якої нової моделі/фічі — письмовий доказ «аналога НЕМА» у стандарті Community 17 (пошук + читання маніфесту/моделі кандидата, не думка LLM); є аналог → inherit-надбудова замість власного коду. Доказ — рядок у PR-описі/ADR. **Канонічний антиприклад (власник, 04.07): написали ВЛАСНУ рекрутацію (camp.staff.vacancy/application, 413 LOC), хоча Odoo має hr_recruitment з коробки — так більше НЕ робимо.** Підстава: reuse-аудит виявив 1 898 LOC дубляжу готового + 1 282 LOC самодублікатів (docs/reuse-audit/2026-07-04/REUSE_AUDIT.md). · ✅ діє з 04.07.

---

# 10. Success criteria / Prod-gate

*Пояснення: що має бути правдою, щоб сезон-2027 поїхав на порталі. ЗАКОН: prod лише після P1.4-виконання + human QA green.*

- [ ] 🔴 **P1.4:** міграція виконана НА ПРОДІ за [M-4] з нулем втрат за [M-5].
- [x] Правові моделі P2 (karta wzór2026, incident §11-12, RSPTS §13) — ✅.
- [x] Тести критичних шляхів P3 (43 файли, зріз 06.07; CI зелений на main 05.07) — ✅; [ ] 🟡 coverage зведено: **69%** (docs/QUALITY_AUDIT_2026-07-04.md); до цілі ≥70% ~90 інструкцій (кандидати в аудиті).
- [x] R2 merged + staging двомовний — ✅ 04.07 (PR#17, deploy run 28699005633, psql-проба).
- [ ] 🔴 Пакет max-захисту [F-RODO-7] (шифрування at-rest, офсайт-бекап, ротація) — DoD-блокер art.9-прода.
- [ ] 🔴 Human QA green по всіх ролях на staging + UAT sign-off ([T-4]).
- [ ] 🟡 Auto-refusal cancel-ланцюг ✅ 04.07 (refund-заглушка — §8 7b); art9-ізоляція ✅ 04.07 (PR#17 leak-тести); ЛИШАЄТЬСЯ: BEP-живлення ([F-FIN-3]) + attachment-ACL ([F-RODO-2]).
- [ ] 🟡 Mobile-audit всіх /my/* і кіосків ([N-2]).
- [ ] ⚪ Interpretacja indywidualna VAT (людина; можна паралельно, до прод-калькулятора).
- [ ] CHANGELOG биті посилання виправити (P5.3, дрібне).
- [ ] 🔴 DR-drill проведений: RTO ≤4 год / RPO ≤1 год ([GAP-6]) — ДО cutover (був блокер лише в §12, у гейті не значився).
- [ ] 🔴 Observability-мінімум прода ([GAP-1]: Sentry прод + uptime + backup-age/disk алерти в Telegram) — ДО cutover.
- [ ] 🔴 Візуальний AI-гейт [T-5] у CI; перший прогін ловить R4b (регресійний еталон).
- **Дедлайн усього гейта ([B-3]):** прод приймає реєстрації сезону-2027 не пізніше **01.09.2026** (цільова 01.08.2026).
- Після cutover: uninstall legacy — окреме вікно після feature-parity ([M-4]).

---

## 10a. План до 17.07.2026 — рубіж «staging feature-complete + демо клієнту»

*Рішення власника 07.07: 17.07 — НЕ повний prod-cutover (§10 лишається на 01.08/01.09), а менший рубіж: kiosk-UI+ключові фічі готові й показані на staging. P1.4-міграція, DR-drill, RODO-шифрування, observability-мінімум — СВІДОМО поза цим рубежем, ідуть далі до офіційного гейта.*

**У СКОУПІ до 17.07 (10 календарних днів):**

| Дні | Пункт | Джерело/оцінка | Хто |
|---|---|---|---|
| 07.07-10.07 (4 дн) | **[F-KSK-2] Kiosk desktop R4/R4b + бренд R5/R8/R9** — mobile-layout на десктопі, langbar→шапка, «Powrót do kiosku»/селектор табору | [ПЕРЕВІРЕНО §8 п.1] оцінка власника 3-5 дн, беру верхню межу | Claude+агенти |
| 10.07-11.07 (1 дн, паралельно з kiosk) | **Refund реальний [§8 7b]** — замінити _schedule_refund заглушку на справжнє повернення | [ПЕРЕВІРЕНО §8 п.7b] 0.5-1 дн | Claude |
| 11.07-12.07 (1 дн) | **Attachment-ACL PDF [F-RODO-2]** + тест | [ПЕРЕВІРЕНО §8 п.8] ~1 дн | Claude |
| 12.07 (0.5 дн) | **BEP-розрив продажі→ціна [F-FIN-3]** | [ПЕРЕВІРЕНО §8 п.5] ~1 дн (стиснено) | Claude |
| 13.07 (1 дн) | **Mobile-audit /my/* і kiosku [N-2]** | [ПРИПУЩЕННЯ] 1-2 дн, беру нижню межу | Claude+ux-review skill |
| 13.07 (паралельно, 0.5 дн) | R7 мікрокопі дочистити + coverage 69%→70% | [ПЕРЕВІРЕНО §8 п.3, §10] | Claude |
| 14.07 (1 дн) | **Візуальний AI-гейт [T-5]** у CI — після kiosk-фіксу, щоб еталон ловив САМЕ виправлений вигляд | [ПЕРЕВІРЕНО §10] нижня межа оцінки 1-2 дн | Claude |
| 15.07 (1 дн) | **Внутрішній QA-прохід усіх 6 ролей на staging** (НЕ формальний UAT sign-off — це вже до §10) + фікс знайденого | [ПРИПУЩЕННЯ] | власник+Claude |
| 16.07 (1 дн) | Буфер на непередбачене + підготовка демо-матеріалів/сценарію | — | власник+Claude |
| 17.07 | **Демо клієнту** | — | власник |

**СВІДОМО ПОЗА скоупом 17.07 (лишається до 01.08/01.09, §10):** P1.4 prod-міграція, RODO max-захист [F-RODO-7] (шифрування/офсайт-бекап/ротація), Human QA formal UAT sign-off, DR-drill, observability-мінімум прода, reuse-міграція кроки 2-4 (SMS/рекрутація/story→Community), решта §8 черги пп.10-16 (teczka ZIP, DM-чат, retention-cron тощо).

**Ризик плану:** буфер лише 1 день на 10; kiosk-пакет (найбільший, 4 дні) на критичному шляху — будь-яка затримка тут зсуває AI-гейт і QA-прохід. Якщо kiosk піде довше оцінки — перше, що ріжеться, це mobile-audit (13.07) або AI-гейт (14.07), НЕ QA-прохід (15.07) чи демо.

---

# 11. Відкриті питання (⚪ рішення власника)

1. Markup ≥5% — жорсткий constraint чи лише default ([F-VAT-1])?
2. Merge гілки `chore/sellable-license-cleanup` + фікс LICENSE-текстів rodo/sms_base ([P-2]) — коли?
3. zadarma в пакеті поставки: лишити (kw_* вичищено) чи виключити ([P-1])?
4. ~~Прибирати Co-Authored-By з модульних репо надалі — політика ([P-2])?~~ — ✅ ВИРІШЕНО: зупинено going-forward, історія не переписується ([P-2]); з 04.07 гейт INC-210 блокує AI-підписи в нових комітах.
5. Міграційні Q2-Q6, Q8-Q10 ([M-7]).
6. GitHub-репо `fayna-campscout` vs модуль `fayna_camp_portal` — перейменувати репо?
7. Звена: чи існує окрема категорія «зовнішня молодь 16-17 не-учасники» ([GAP-2])?
8. Дата interpretacji indywidualnej до KIS ([F-VAT-2]) — хто подає і коли.
9. ~~Ліцензія reuse-міграції (AGPL/OPL)~~ — ✅ ВИРІШЕНО власником 04.07: **політика Community-only** (лише стандартні модулі Community; OCA не використовуємо; нема стандартного/кривий → свій код). OCA-кроки плану скасовано, питання закрите.

---

# 12. ЧОГО НЕМАЄ ВЗАГАЛІ — і як це зробити

*Пояснення розділу (вимога власника): чесний список підсистем, яких НЕ існує (не «частково» — взагалі), щоб вони не губилися за оптимізмом. Кожен пункт — з рецептом.*

**[GAP-1] Observability-стек прода (метрики/дашборди/алерти).** Є лише Sentry на staging (fayna_sentry, ловить помилки — доведено end-to-end 01.07) і CI-нотифікації. НЕМА: Grafana/LGTM, 6 дашбордів (infra/PG/Odoo/business/security/deploy), алерт-рівнів (odoo_down>2min page; disk>85% warn), log-retention 30д/1р/7р. **Як зробити:** мінімально достатнє до cutover — Sentry на ПРОД + uptime-моніторинг (healthcheck cron + Telegram) + disk/backup-age алерти (~1 день); повний LGTM — окремий infra-проєкт після сезону (~1 тиждень, IaC у campscout-infra). **Критерій мінімуму (EARS):** WHILE прод живий, THEN логи застосунку зберігаються ≥30 днів, а падіння Odoo >2 хв / backup_age >25 год / disk >85% генерують алерт у Telegram. · Верифікація: inspect (конфіг) + test (штучний тригер алерту).

**[GAP-2] Звена (підгрупи) + дитячі лідери.** `is_subgroup_leader`/camp.subgroup у коді немає [ПЕРЕВІРЕНО: grep 0]. Вимога: виховник ділить ~20 дітей на ~3 звена, діти обирають лідерів (0 документів — вони учасники); піраміда +рівень. **Як:** легка модель camp.subgroup (або self-ref на camp.group) + прапорець на participant + вкладка у кіоску виховника; ~1-2 дні.

**[GAP-3] UAT з живими користувачами.** Жодного формального UAT-циклу з реальними kierownik/батьками не було (тільки агенти+власник). **Як:** usability-test-plan скіл → 3-5 задач на staging (створити табір; заповнити карту з телефона; знайти документ на «контролі») → sign-off у docs/TESTING.md; 0.5 дня підготовка + 1-2 сесії; ДО prod-gate. **Критерій (EARS):** BEFORE прод-деплой, THEN проведено UAT з 3-5 живими користувачами (kierownik/батьки) на staging; результати і sign-off у docs/TESTING.md; 0 критичних блокерів. · Верифікація: inspect (sign-off документ).

**[GAP-4] Регулярний security-скан прода.** Разові аудити були (IDOR закрито, ACL-аудит); систематичного OWASP ZAP weekly / зовнішнього пентесту нема. **Як:** ZAP baseline-scan у cron CI на staging URL (~0.5 дня); зовнішній пентест — за бюджетом перед SaaS-етапом.

**[GAP-5] Performance-бенчмарки.** Цілі є ([N-3]), вимірів нема. **Як:** k6/locust сценарій checkout+/my на staging + фіксація p95 у CI-артефакт; ~1 день; перед піком продажів.

**[GAP-6] Backup DR-drill.** Бекапи є, відновлення жодного разу не репетирувано end-to-end. **Як:** відновити прод-дамп у чистий контейнер + smoke; задокументувати час у RUNBOOK; ~0.5 дня; ДО cutover. **Критерій (EARS):** WHEN проводиться DR-drill, THEN прод-БД+застосунок відновлені в чисте середовище за ≤4 год (RTO) із втратою даних ≤1 год (RPO), smoke зелений. · Верифікація: inspect (звіт drill з таймінгами).

**[GAP-7] Standardy Ochrony Małoletnich (pisemne).** Юр-вимога переліку SELLABLE §2.2 п.4 — документ-політика не знайдений у репо. **Як:** юр-текст (власник/юрист) → data/regulamin-тип + підписи кадри через [F-OPS-6]-механізм regulamin acknowledgment; переважно юридична, не кодова робота.

**[GAP-8] Автоматична retention/erasure-механіка** — див. [F-DOC-4] (політика є, cron нема).

---

# 13. Команди

```bash
# Lint / format / security (джерело правди — .pre-commit-config.yaml)
pre-commit run --all-files            # ruff + ruff-format + OCA + bandit + gitleaks

# Тести (Odoo test runner, потрібна БД)
docker exec campscout_web odoo -c /etc/odoo/odoo.conf -d campscout_test \
  --test-enable --test-tags /fayna_camp_portal --stop-after-init -i fayna_camp_portal

# Локальне оновлення модуля
docker exec campscout_web odoo -c /etc/odoo/odoo.conf -d campscout \
  -u fayna_camp_portal --stop-after-init && docker restart campscout_web
# ⚠️ переклади: додавати --i18n-overwrite; перед -u: git→/mnt/addons синхронізація на стенді

# Деплой #4ZONES (Mac → GitHub → staging → prod)
# ssh campscout; cd /opt/campscout/custom-addons/fayna_camp_portal
# git pull && sudo chmod -R o+rX .   # capital X!
# odoo -u fayna_camp_portal --stop-after-init; docker restart campscout_web
```

# 14. Структура коду

```
fayna_camp_portal/
├── __manifest__.py            # 17.0.4.1.7; depends: [P-4]
├── hooks.py                   # post_init (install) — міграція ir.model.data absorbed
├── migrations/                # 17.0.4.0.0 … 17.0.4.1.7; .1.0 = мови PL/UA; .1.5-.1.7 = data-міграції reuse S1
│                              # (diet jsonb / program / training) — [PR-4]; CI їх НЕ проганяє ([T-2] сліпа зона)
├── models/                    # 27+ файлів: camp, participant, operations (найбільший, 3751 р. — беклог рефактор ≤600/файл),
│                              # emergency, incident_kamilka, incident_card, incident_notification_log,
│                              # commercial, budget, nutrition, transport, stories, staffing, recruitment,
│                              # teczka_ko, regulamin, sms/sms_notify, training (keeper camp.staff.training.record;
│                              # vozhatyi-моделі видалені в pair6), reports,
│                              # admin_access_log, staff_sms_log (immutable), *_inherit/_extensions
├── controllers/               # portal.py (/my/*), admin.py (/admin/*), kiosk.py (/camp/kiosk*), recruitment_portal.py
├── wizards/                   # camp_create_wizard (майстер+калькулятор+fiscal), staff_sms_composer
├── security/                  # groups.xml (13), ir.model.access.csv (170+), record_rules.xml
├── data/                      # cron, kamilka escalation, sms templates, config params, declaracja-текст
├── views/ (16 XML) · templates/ (portal, kiosk OWL) · static/ (scss/js/xml)
├── i18n/                      # pl_PL.po · uk_UA.po (~23k рядків кожна)
├── tests/                     # 43 test_*.py (+службові; зріз 06.07) + e2e/test_critical_paths.py — розділ 6
├── scripts/                   # populate_from_bs, migrate_bs_signatures, populate_escort_from_204,
│                              # detach_campscout_management, staging_sync.sh — розділ 7
└── docs/                      # TZ.md (ЦЕЙ КАНОН) · PLAN.md · CHANGELOG · LEGAL_REQUIREMENTS ·
                               # CABINET_STATUS · ROLES · MIGRATION_MAP/BACK · archive/
```

Повний реєстр моделей живе в коді (`grep -rh "_name = " models/ wizards/`) — канон описує вимоги і keeper-и reuse-злиттів, не дублює перелік моделей (щоб не протухав).

# 15. Traceability: джерела → розділи канону; реєстр архівів

*Пояснення: з чого зібрано цей канон і де тепер лежать джерела. Всі перелічені документи — АРХІВ (перейменовані без «TZ» у назві, з банером на канон); при конфлікті пріоритет — цей файл. (Розділ фізично перенесено на своє місце 06.07 — раніше стояв після §18.)*

| Джерело (стара назва) | Дата зрізу | Що взято | Архівна назва |
|---|---|---|---|
| CAMPSCOUT_MASTER_TZ.md (337KB) | 2026-04-22 | §0 business-рамка, life-critical, retention-матриця, BP-001..011, CI-гейти, observability-цілі, global DoD | fayna-digital-docs/contributing/archive/2026-04-22-campscout-master-spec.md |
| FAYNA_CAMPSCOUT_TZ.md | 2026-04-30 | hotel-pattern рішення, карта роутів, RBAC-матриця, SMS-система §5A, дашборд §5B, PDF-оферти §10A | .../archive/2026-04-30-campscout-one-module-spec.md |
| FAYNA_CAMP_TEMPLATE_TZ.md (per-module) | 2026-04-23 | деталізація генератора картки (схема A-G) — поглинуто через master §2.6 | .../archive/2026-04-23-camp-template-module-spec.md |
| FAYNA_CAMP_QUALIFICATION_TZ.md (per-module) | 2026-04-24 | деталізація karta/RODO art.8 — поглинуто розділом 4.4 | .../archive/2026-04-24-camp-qualification-module-spec.md |
| TZ_SPRINT_2026-06-10.md | 2026-06-10 | рішення R1-R14, pkt9-поля, групи, кабінети, фінанси R8, detach §8a | docs/archive/2026-06-10-sprint-spec.md |
| TZ_PRODUCTION_SELLABLE | 2026-06-23 | sellable-планка, аудит 79 моделей, BonSens-parity, команда агентів, рішення власника §9 | docs/archive/2026-06-23-production-sellable-spec.md |
| TZ-migracja-legacy-to-portal | 2026-06-23 | розділ 7 повністю (M0-M5, Q2-Q10, escort §5) | projects/campscout/ARCHIV-migracja-legacy-to-portal-2026-06-23.md |
| 04-TZ-v2-VERIFIKACIA | 2026-06-23 | верифіковане зроблене, DoD §C, тири 1-4 | it-project/04-ARCHIV-verifikacia-plan.md |
| 06-TZ-EPIK-MAJSTER | 2026-06-24 | епіки A-F, двошарова програма, ціноутворення, кіоск/панель/трекер, native-first вердикт | it-project/06-ARCHIV-epik-majster-tabir.md |
| 12-TZ-TECHNICAL-CONSOLIDATED | 2026-06-24 | закони §0, кіоск-патерн dnj, VAT-вердикт, declaracja, teczka, RODO-консолідація, пакет/ліцензії | it-project/12-ARCHIV-technical-consolidated.md |
| 14-TZ-CAMP-MODULE | 2026-06-24→25.06 | фінальні таблиці ролей/видимості, §13-допуск+blurred, беклог §20, мобіль, RODO-розмежування | it-project/14-ARCHIV-camp-module.md |
| 15-TZ-RODO-MODULE | 2026-06-24 | портальні стики RODO (4.5); канон модуля = fayna_rodo_compliance/docs/TZ.md | it-project/15-ARCHIV-rodo-module.md |
| REPAIR_TZ (R1-R10) | 2026-07-02 | розділ 8 | campscout-e2e-test-2026-07/ARCHIV-repair-backlog-2026-07-02.md |
| TZ_UPDATE_from_test | 2026-07-02 | знахідки тесту (BEP, opis, еталони, форми MEN) | campscout-e2e-test-2026-07/ARCHIV-test-findings-2026-07-02.md |
| PLAN.md / R2_STATUS.md | живі | статуси фаз P1-P5; робочий стан R2 | лишаються робочими документами поруч із каноном |
| BRAND_SWEEP_TZ.md | 2026-04-22 | не портал (sweep усіх модулів) — не поглинуто | лишається як є |

> **Правило надалі (уточнено 06.07):** нові вимоги — ТІЛЬКИ у цей файл (через PR). Ремонтна черга порталу — ТІЛЬКИ розділ 8 (анти-дрейф правило там же); STATUS-файли сесій = журнали БЕЗ власного статусу вимог, з посиланням сюди; kanban = крос-проєктне дзеркало з датою зрізу. Після закриття — викреслювати у тому ж PR. Жодних нових файлів зі словом «TZ» у назві.

# 16. Глосарій (словник термінів)

*Пояснення: доменна мова однозначна — вимога сеньйорського ТЗ (блок 8). Польські юридичні терміни не перекладаються в коді.*

| Термін | Значення |
|---|---|
| **Organizator** | юрособа-власник таборів (CampScout / майбутній SaaS-клієнт); найширші права |
| **Kierownik (wypoczynku)** | керівник конкретного заїзду; юридично відповідальний (Rozp. MEN); ≠ wychowawca |
| **Wychowawca** | виховник групи ≤15/20 дітей; веде dziennik; бачить art.9 лише своєї групи |
| **Instructor** | інструктор профільних (зокрема high-risk) активностей; ліцензія обов'язкова для лиж/води |
| **Turnus / заїзд** | конкретна зміна табору = `event.event`; табір-бренд = `product.template` |
| **Karta kwalifikacyjna** | юр-картка дитини (Dz.U.2026/704, Zał.6), 5 секцій + pkt 9 (медичне, art.9) |
| **Teczka KO** | тека документів заїзду для контролю Kuratorium Oświaty; view-агрегатор, не копія файлів |
| **Zgłoszenie wypoczynku** | реєстрація заїзду в кураторіумі: 21 дн (krajowy) / 14 дн (zagraniczny) до старту |
| **KRK / RSPTS (RSTPO)** | довідка про несудимість / реєстр сексуальних злочинців; гейт §13 перед допуском до дітей; KRK дійсний 12 міс |
| **Declaracja** | заява про несудимість (art.233 §1 KK) перед першим доступом до карток; раз на сезон |
| **Escort / konwój (asysta)** | індивідуальний супровід дитини (продукт 204): dozwoła + zgoda medyczna + підпис |
| **Kamilka (Ustawa)** | закон 2024 про захист дітей: SMS повз opt-out (vital interest), 5-хв ескалація, immutable лог |
| **BEP** | break-even point заїзду: мін. дітей для беззбитковості; живиться з продажів (F-FIN-3) |
| **VAT zw. / VAT-marża** | звільнення art.43 ust.1 pkt 24a (default) / режим маржі art.119 23% — перемикач per заїзд |
| **Kiosk** | плитковий інтерфейс однієї ролі (home_action) замість сирого Odoo-бекенда |
| **Strangler Fig** | міграційний патерн: портал росте ПОРУЧ з legacy, uninstall лише після parity |
| **Cutover (P1.4)** | виконання міграції на проді за розділом 7; головне відкрите плече проєкту |
| **Звено** | підгрупа ~6-7 дітей всередині групи з дитиною-лідером (GAP-2, не збудовано) |

# 17. Архітектурний контекст (C4, рівень 1)

*Пояснення: діаграма контексту — хто і що взаємодіє з системою (сеньйорський блок 7). Рівні 2-3 (контейнери/компоненти) — розділи 14 і 4; окремих діаграм свідомо не ведемо, поки команда = 1 власник + агенти.*

```
  [Батько]──/my/*──┐                        ┌──SMS──[TurboSMS API]──▶ телефони
  [Wychowawca]─kiosk┤                       ├──дзвінки/SMS──[Zadarma АТС]
  [Kierownik]──kiosk┤   ┌────────────────┐  ├──e-фактури──[KSeF (держ. API)]
  [Organizator]─Odoo┼──▶│ fayna_camp_    │──┤
  [Sales]──CRM/sale─┤   │ portal (Odoo17)│  ├──розсилки──[SendPulse]
  [Кандидат]──/jobs─┘   │  + fayna_rodo  │  └──журнал згод──(fayna_rodo_compliance)
                        │  + fayna_sms   │
  [Бухгалтер (зовн.)]◀──│  + l10n_ksef   │──оплати──[банк/Przelewy24 — вручну/imported]
   email-евіденція+KSeF └──────┬─────────┘
                               │ git push → GitHub → CI (Lint+test-gate+e2e)
  [Kuratorium Oświaty]◀─ PDF/паперово ─ teczka │ deploy: staging (Hetzner) → prod (#4ZONES)
```

# 18. API та зовнішні контракти

*Пояснення: сеньйорський блок 4. Позиція проєкту — свідома ВІДМОВА від публічного REST API.*

**[API-1] Публічного REST API НЕМАЄ — свідоме рішення (ADR 2026-07-02).** `/api/v1/*` повністю видалено: 0 споживачів (портал JS/XML, Astro-сайт, тести — все 0), мобільного застосунку нема, а `story_detail` мав IDOR повз consent-gate. Батьківські сценарії покриває нативний портал `/my/*`. Відновлення — з git-історії, лише коли з'явиться реальний споживач + OpenAPI-контракт + токен-авторизація. · ✅ Верифікація: grep `/api/v1` у коді = 0.

**[API-2] Внутрішні HTTP-контракти** (auth=user, не публічні): портал `/my/*` (QWeb, session), kiosk `/camp/kiosk/*` + `/camp/kiosk/set_lang` (json-RPC, валідація active-мов), `/admin/dashboard` + login-as (organizator-only, audit-лог). Контракти живуть у коді контролерів; OpenAPI не ведеться свідомо (немає зовнішніх споживачів). · ✅.

**[API-3] Вихідні інтеграції (клієнтські контракти):** KSeF (e-фактури, через `l10n_pl_ksef_margin`), TurboSMS (адаптер `fayna_sms_base`; PL-провайдери SMSAPI/SerwerSMS — беклог P-3), Zadarma (АТС, окремий модуль), SendPulse (розсилки; консолідація журналу згод — F-RODO-5). Кожна інтеграція в try/except — збій зовнішнього API не блокує продаж ([A-4]). · ✅ архітектура; контракти = документація вендорів.
