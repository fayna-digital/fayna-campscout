> ⚠️ **SUPERSEDED 2026-07-02** — актуальне джерело істини: єдиний `docs/TZ.md`. Цей датований зріз лишено як історію; при конфлікті — пріоритет `TZ.md`. (REPO_STANDARD: один живий ТЗ, не кілька версій.)

# ТЗ — Спринт «Повний портал таборів» (2026-06-10 … 12)

> Доповнення до [TZ.md](TZ.md) (6 областей, чинне) — ПОВНИЙ обсяг спринту, затверджений user-ом у сесії 2026-06-10.
> **Дедлайн:** сьогодні (10.06) — побудовано все; завтра (11.06) — тестування на staging; післязавтра (12.06) — міграція на prod.
> **Залізне:** 100% будується і тестується НА STAGING на живих даних; prod не чіпаємо до окремої команди міграції. Повний лог процесу → `DevJournal/projects/camp-portal-build/WORKLOG.md`; кожен крок має точку відкату (git-коміт + бекап БД перед кожним `-u`).

---

## 0. Затверджені рішення user-а (зведення сесії)

| # | Рішення |
|---|---|
| R1 | Hydrofobia / lęk wysokości → **жорстка заборона** запису на водні/висотні заняття (ValidationError, без override) |
| R2 | RSPTS — повторна верифікація **кожен сезон**; акцепт **лише вручну Admin/Organizator**; кадра/HR завантажує документи заздалегідь («готове для акцепту») |
| R3 | Kierownik **бачить скани** документів кадри свого табору (надає їх на контролі KO); акцепт — ні. Wychowawca/Sales сканів не бачать (RODO art. 10) |
| R4 | Фото дня + погода дня для батьків у /my/* — в обсязі спринту |
| R5 | Без локального docker: верифікація — lint+review локально, функціональні тести — на staging |
| R6 | Картки: **одна дитина × один турнус = одна картка**; спільні дані батьків передзаповнюються; меддані НЕ копіюються між дітьми; підпис окремо на кожну |
| R7 | Версіонування картки: `wzor_version` 2021/2026; межа **06.06.2026** (przepis przejściowy §2 — картки, передані батькам до 06.06, чинні в старому wzorze, незмінні) |
| R8 | Фінанси: **дві маржі** — VAT (art. 119, лише koszty «dla bezpośredniej korzyści turysty») і бізнесова (включно з **рекламою**, кадрою, overhead). Прапорець на категорії витрат |
| R9 | Дедлайн vs якість → скоуп ріжемо, якість ні (developer-loop) |
| R10 | Кабінетів **7** + 4 ролі-надбудови (див. §3) |
| R11 | Продаж лишається через sale.order + event_sale; квитки = шар місткості; гаджети = окремі позиції зі звичайним VAT |
| R12 | Зарплата wychowawcy — ставка за турнус, конфігурована (дефолт у налаштуваннях) |
| R13 | Вакансії — легка внутрішня модель (без залежності hr_recruitment); скасування реєстрацій НЕ авто-закриває найняту кадру (прапорець overstaffing) |
| R14 | Zestawienie для księgowej за marzec–maj — ПІЗНІШЕ, новими звітами |

## 1. Правові моделі (джерела — RAG-база kku, дослівні wzory)

### §10 Карта кваліфікаційна wzór 2026 (Dz.U. 2026/704)
- Джерело: `doc-kku-dzu-2026-704-karta-kwalifikacyjna-nowy-wzor.md` (повний текст).
- `wzor_version` Selection('2021','2026') на картці; старі підписані — immutable, PDF у старому layout.
- Нові структуровані поля pkt 9 (II розділ): `allergy_meds`, `allergy_pollen`, `allergy_food`, `allergy_insect_venom` (bool+notes), `motion_sickness`, `permanent_meds` (text: лік+дозування), `chronic_diseases` (text), `orthodontic_appliance`, `glasses`, `contact_lenses` (bool), `diet_lowcal`, `diet_vegetarian` (bool), `emotional_expression_issues`, `group_functioning_issues` (bool+notes), `fear_of_heights` (bool), `hydrophobia` (bool); щеплення: `vacc_tetanus_year`, `vacc_diphtheria_year`, `vacc_other` (text).
- Медполя — field-level groups (RODO art. 9): parent (своя дитина), wychowawca (своя група), kierownik (свій табір), medical officer.
- **R1-блокада:** constraint при записі участі в активність типу water/heights, якщо `hydrophobia`/`fear_of_heights` → ValidationError.
- PDF QWeb: рендер 1:1 офіційного wzór (розділи I–VI), версія залежить від `wzor_version`.
- Бонус розпорядження: водні поля на activity — `kąpielisko_hours_ok` (купання лише в години regulaminu / від сходу до заходу), ratownik+wychowawca обов'язкові (розширення §7-валідації).

### §13 RSPTS (Ustawa Kamilka, art. 21 ustawy 16.05.2016)
- На `camp.staff`: `rspts_status` (pending/verified/rejected), `rspts_doc_krk` (binary, zaświadczenie o niekaralności), `rspts_doc_registry` (binary, potwierdzenie з RSPTS), `rspts_verified_by` (res.users, readonly), `rspts_verified_date`, `rspts_season_id` (прив'язка до сезону — R2), `rspts_notes`.
- Кнопки Akceptuj/Odrzuć — лише group_camp_admin/organizator (перевірка групи у write(), не лише в UI).
- Блокада: прив'язка staff до турнусу при статусі ≠ verified У ПОТОЧНОМУ сезоні → ValidationError з юр.текстом.
- Доступ до сканів: admin/organizator (всі) + kierownik (кадра свого табору, record rule); перегляд → audit log (патерн admin_access_log).

### §11 Karta Wypadku — ПОВНІ 16 пунктів
- Джерело: `doc-kku-karta-wypadku-pdf.md` (wzór курсу; LEGAL_REQUIREMENTS §11 виправити: 7→16 пунктів).
- Модель `camp.incident.card`: placówka/pieczęć, постраждалий (participant_id + дата нар., адреса, klasa/grupa), czynność, przeszkolenie BHP, badanie lekarskie (дата+przeciwwskazania t/n), data+czas+miejsce, rodzaj/umiejscowienie urazu, niezdolność t/n + тривалість, szczegółowy opis+przyczyna, особа nadzoru, чи була присутня (+czemu ні), godzina першої допомоги, świadkowie, środki zapobiegawcze, підписи komisji (клаузула art. 247 KK у PDF), załączniki.
- Many2one до `camp.incident.report` (не дублює workflow).

### §12 Rejestr Wypadków
- Джерело: `doc-kku-wzor-rejestru-wypadkow-2.md` — 10 колонок дослівно.
- `camp.incident.register` per турнус: авто-агрегація з §11-карток, хронологічно, Lp. авто; PDF для KO; незмінний після закриття турнусу.

### §9 Dziennik Zajęć (Załącznik 5)
- Звірити наявний `fayna.camp.dziennik` з 4-секційною структурою (1: uczestnicy grupy ≤20; 2: tygodniowe plany; 3: щоденні записи data/godzina/treść/uwagi+підпис; 4: uwagi kierownika/KO) + nagłówek (адреса, organizator, група, kierownik, wychowawcy, dati).
- Dziennik = per `camp.group` (див. §2-групи). PDF за wzorem (`doc-kku-dzienniczek-pdf`, приклад заповнення в базі).

## 2. Групи (§2 art. 92c) + кабінетна видимість

- **`camp.group`**: турнус + назва + wychowawca_ids + participant_ids + вік-мікс.
- Constraints: ≤20; якщо є дитина <10 р. → ≤15; niepełnosprawni ≤2 на групу.
- Record rule wychowawcy на participant: **лише діти своєї групи** (замінює правило «всі діти заїзду»).
- Авто-розподіл дітей по групах за віком (молодші окремо), kierownik перетасовує вручну — constraint не дасть порушити ліміт.

## 3. Кабінети (7) + надбудови (4)

| Кабінет | Обсяг |
|---|---|
| Organizator/Admin | всі табори; акцепт RSPTS; zgłoszenia; dashboard; view-as |
| Kierownik | свій табір: групи, картки + **червоний дашборд pkt 9**, dzienniki всіх, програма (edit), кадра+скани, regulaminy+підписи, wypadki, daily reports, **Teczka KO** |
| Wychowawca | своя група: діти+картки, свій dziennik+плани, програма (read), regulaminy до підпису |
| Батьки /my/* | свої діти: картки (заповнення+підпис), реєстрації, лояльність, **фото дня, погода дня**, stories, транспорт |
| Sales | ліди/реєстрації/клієнти, БЕЗ медданих |
| Instructor | свої заняття + безпекові прапорці учасників заняття (без повних карток) |
| **Księgowa/Finanse** | звіти/бюджети (див. §5), read-only + експорт |

Надбудови: Medical (art.9 повністю + izolatka §3), Nutrition, HR (онбординг кадри/документи), Emergency.

## 4. Regulaminy + Teczka KO

- **`camp.regulamin`**: тип (regulamin kolonii/kąpieli/wycieczek/ppoż/zakres czynności wychowawcy), контент/attachment, видає kierownik. Wzory — з RAG (`regulamin-obozu-kolonii`, `zakres-czyni…`, `zakres-obowiazkow-trenera…`).
- **Підписи кадри**: acknowledgment (staff × regulamin → дата+підпис); дашборд kierownika «хто не підписав»; попередження при старті турнусу.
- **Teczka KO** (кабінет kierownika): чеклист готовності за arkusz kontroli (`doc-kku-arkusz-ko`, `protokol-kontroli-2026`) — картки/dzienniki/програма/кадра+RSPTS/regulaminy/rejestr wypadków ✅/❌ + **експорт повного PDF-пакета одним кліком**.

## 5. Фінанси (кабінет Księgowa + organizator)

- **Analytic account на кожен турнус** (авто при створенні) — всі фактури (кошти й продажі) тегуються табором.
- **`camp.budget`** per турнус: категорії витрат (довідник; кожна: stały/zmienny + прапорець **«до VAT-маржі»**): ośrodek, transport, wyżywienie/доба, кадра (от автоштату §6), ubezpieczenie NNW, atrakcje, **reklama** (лише бізнес-маржа — R8), gadżety COGS, inne. Дохід: cena, реальна знижка, місткість.
- Розрахунки: **BEP (мін. дітей)**, contribution margin, **hipotetyczna marża VAT** (база заліцок!), **бізнес-маржа** (з рекламою), план vs факт (analytic), прогноз прибутку, cash-flow по датах, сезонний зріз.
- Звіти XLSX/PDF: Zestawienie obozów (przychód/koszty/обидві маржі) + Rejestr faktur за місяць (numer, kontrahent, obóz, data zapłaty, **kwota marża / kwota gadżety** — стик із `l10n_pl_ksef_margin` P_PMarzy).
- Kierownik бачить бюджет свого табору read-only **без зарплат**.

## 6. Майстер табору + події/квитки + автоштат

- **Майстер «Новий табір»** (вхід: дати, місце, місця, ціна, кошт проживання/доба, харчування/доба, ставки кадри) → генерує: event.event + **квитки event_sale** (ліміт = місця), analytic, camp.budget, каркас груп, regulaminy-шаблони, скелет програми, Teczka KO.
- **Автоштат §2**: required_wychowawcy = ceil(діти/ліміт за віком: <10р→15, інакше 20). Перетин порогу (15→16-та дитина) → **авто-вакансія** (легка модель: open→candidate→hired→RSPTS verified→assigned) + повідомлення + **рядок зарплати в бюджет** (BEP перераховується) + авто-поділ дітей на групи за віком.
- Скасування → прапорець overstaffing, рішення за людиною (R13).

## 7. Портал батьків — фото дня + погода дня

- Сторінка заїзду в /my/*: опубліковані фото (camp.story published, лише свій заїзд) + погода/активності дня (camp.daily.report published — окремий public-зріз без службових полів).
- Mobile audit обов'язковий (правило репо).

## 8. Інфраструктура даних

- **`scripts/staging_sync.sh`** (в git): pg_dump prod `campscout` + filestore (6.1G) → restore на staging → **НЕЙТРАЛІЗАЦІЯ** (вимкнути ir.mail_server, SMS dry-run, небезпечні crons: Kamilka escalation, нагадування, розсилки) → install/update `fayna_camp_portal` (на prod його НЕМАЄ — кожен рефреш = репетиція міграції) → бекап старого staging перед заміною. Cron щодоби.
- **`docs/MIGRATION_BACK.md`**: план staging→prod: люди→кабінети (батьки→Parent, кадра→ролі), діти→групи (нерозподілені — kierownikowi), фактури marzec–maj→analytic (backfill), картки→wzor_version за датою передачі (R7), idempotent+dry-run+бекап+контрольні суми+rollback.

## 9. Верифікація і Definition of Done спринту

- Кожна модель: поля+constraints → views → ACL/record rules → Odoo-тести → PDF → i18n PL/UA.
- Локально: pre-commit зелений + code-review-агент. Функціонально: тести на staging (`--test-enable --test-tags /fayna_camp_portal`) на живих даних.
- **DoD 10.06:** усе з §1–§8 закомічено в `loop/season-sprint`, pre-commit зелений, задеплоєно на staging, smoke на живих даних пройдено.
- **DoD 11.06:** Odoo-тести зелені на staging; human-QA user-а по 7 кабінетах; фікси.
- **DoD 12.06:** MIGRATION_BACK dry-run чистий → міграція на prod за командою user-а.

## 8a. Звільнення даних від campscout_management (ПІДТВЕРДЖЕНО 10.06 на staging)
Модуль володіє бізнес-даними (ir_model_data): 24 product.template (всі табори), 3 event.event+3 tickets (noupdate), 21 product.attribute.value, homepage_v2+8 ir.ui.view, website.page. Джерело: data/*.xml (31 record).
**Обов'язковий крок MIGRATION_BACK (до будь-якого uninstall):** DELETE FROM ir_model_data WHERE module='campscout_management' AND model IN ('product.template','product.product','product.attribute','product.attribute.value','event.event','event.event.ticket','website.page') → записи стають незалежними нативними даними. Кастомні views (homepage, legal, mail layout) — переносяться як шаблони fayna_camp_portal. Крок репетирується щодобовим рефрешем.
**Правило:** у fayna_camp_portal БІЗНЕС-записів у XML НЕМАЄ — табори/події/квитки створює лише майстер (нативні таблиці).
