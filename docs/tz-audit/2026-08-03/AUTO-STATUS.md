# AUTO-STATUS — аудит ТЗ↔код дешевими API (2026-08-03)

Метод: луп deepseek-аналітик (проби git grep/read -> вердикт) + gemini-чекер (адверсарно, Creator≠Tester), 2 раунди макс. Пунктів: 149. API-викликів: 511. Зріз коду: git main @ HEAD на момент прогону.
Вердикти дешевих моделей; фінальна верифікація вибіркою — Claude (окремо).

## ⚠️ РОЗСИНХРОН ТЗ↔код — 1

### [F-RODO-4] · TZ.md:183 · ТЗ заявляє: ✅
- Чому: ТЗ заявляє ✅ з доказами, але grep показує відсутність реалізації — код не відповідає заявленому статусу.
- Доказ: models/participant.py:1055 — лише згадка 'anonymised' у docstring, без реалізації erasure
- Доказ: models/participant.py:0 — немає 'erased' логіки
- Доказ: models/commercial.py:0 — немає 'erased' або 'anonymi'
- Доказ: models/participant.py:0 — немає SendPulse sync
- Доказ: models/commercial.py:0 — немає SendPulse sync
- **Зробити:** Реалізувати erasure wizard: анонімізація res.partner, лог action='erased', SendPulse sync; захист юридичних/медичних даних
- Чекер: підтверджено: Проби підтверджують відсутність реалізації ключових функцій (erasure, anonymization, SendPulse sync) у зазначених файлах, що повністю спростовує початкову заяву ТЗ про '✅ Доказ' та обґрунтовує вердикт

## ❓ СПІРНІ (на ручну верифікацію) — 22

### [B-1] · TZ.md:48 · ТЗ заявляє: ✅
- Чому: Більшість компонентів (dziennik, kamilka, RODO, звіти, створення табору) підтверджені, але 'картки кваліфікаційні' не мають явного доказу, а частина посилань аналітика неперевірена.
- Доказ: models/camp.py:238-262 — dziennik_ids, dziennik_count, _compute_dziennik_stats — daily activity registers implemented
- Доказ: models/incident_kamilka.py:42 — severity='kamilka' selection value added
- Доказ: models/incident_kamilka.py:89-90 — _check_kamilka_required_fields — Kuratorium audit validation
- Доказ: models/camp_escort.py:106-107 — rodo_consent_id field linking to fayna.rodo.consent.log
- Доказ: models/commercial.py:538-540 — rodo_consent_id on sale.order
- Доказ: models/commercial.py:721-766 — _log_checkout_consent records RODO consent transactionally
- **Зробити:** Підтвердити наявність 'карток кваліфікаційних' (qualification cards) — проби не показали явного файлу/моделі для них; перевірити повний цикл 'продаж' (sale.order зі станами) у commercial.py.
- Чекер: відхилено 2 рази: Аналітик посилається на файли `models/camp_escort.py` та `models/commercial.py` для RODO, які не були знайдені жодною з наданих проб. Також, аналітик стверджує про існування `reports/dziennik_reports.xml`, але надана проба `grep report|pdf` у директорії `reports` не містить згадки про цей файл, що є прямим протиріччям.

### [A-1] · TZ.md:66 · ТЗ заявляє: ✅
- Чому: Відсутність 'camp.draft' у models прямо підтверджує заявлене відхилення, а наявність test_role_canon підтверджує тестовий доказ.
- Доказ: docs/TZ.md:66 — A-1 вимагає декларації 'Native Odoo: <модуль> — extend' або 'custom — бо <причина>'
- Доказ: models/recruitment.py — 0 збігів 'hr_recruitment', але це не доказ відхилення; відсутність 'camp.draft' у models (0 збігів) підтверджує заяву про відхилення
- Доказ: docs/TZ.md:66 — згадує 'camp.draft відхилено' як доказ дієвості гейта
- Доказ: tests/__init__.py:31 — test_role_canon імпортовано, що підтверджує наявність тесту
- Чекер: відхилено 2 рази: Проби не підтверджують, що «Кожна підсистема в ADR декларує: `Native Odoo: <модуль> — extend` АБО `custom — бо <законна причина>`», оскільки пошук цих фраз знаходить лише саму вимогу в TZ.md, а не фактичні декларації в інших ADR. Також, доказ щодо «рекрутацію-custom відхилено і переведено на hr_recruitment» є непереконливим.

### [P-1] · TZ.md:82 · ТЗ заявляє: ✅
- Чому: Частина залежностей (fayna_rodo_compliance, fayna_sms_base) підтверджена, але три модулі з ТЗ відсутні в коді, NOTICE.md не знайдено, деплой-скрипти не містять addons_path.
- Доказ: __manifest__.py:63-64 — залежності fayna_rodo_compliance та fayna_sms_base присутні в depends
- Доказ: __manifest__.py:22,40 — згадки fayna_sms_base та fayna_rodo_compliance в коментарях/описі
- Доказ: grep по __manifest__.py не знайшов l10n_pl_ksef_margin, fayna_sms_turbosms, zadarma_odoo — ці модулі відсутні в depends
- Доказ: grep NOTICE.md по __manifest__.py — 0 збігів, NOTICE.md не згадується в маніфесті
- Доказ: grep addons_path по tools/deploy-staging.sh та .github/workflows/deploy-staging.yml — 0 збігів, деплой-скрипти не налаштовані на комплект
- **Зробити:** 1) Додати l10n_pl_ksef_margin, fayna_sms_turbosms, zadarma_odoo до depends у __manifest__.py; 2) Додати NOTICE.md у 6 модулях (гілка chore/sellable-license-cleanup); 3) Налаштувати addons_path у деплой-скриптах для комплектної поставки
- Чекер: відхилено 2 рази: Аналітик не перевірив наявність модуля `fayna_camp_portal`, який чітко вказаний у вимозі як частина комплекту поставки. Також, проба для `NOTICE.md` перевіряла згадку в `__manifest__.py`, а не фактичну наявність файлів `NOTICE.md` у 6 модулях, як того вимагає ТЗ.

### [R-1] · TZ.md:95 · ТЗ заявляє: ✅
- Чому: 6 з 6 базових груп підтверджено, але група Parent не знайдена у пробах, а кількість груп та ACL не підтверджена повними даними.
- Доказ: security/groups.xml:215 — Organizator Wypoczynku (top-level) присутня
- Доказ: security/groups.xml:156 — Camp Sales Manager присутня
- Доказ: security/groups.xml:40 — Camp Kierownik присутня
- Доказ: security/groups.xml:168 — Camp Wychowawca (Counselor) присутня
- Доказ: security/groups.xml:197 — Camp Instructor (Activity Specialist) присутня
- Доказ: security/groups.xml:23 — Camp Medical Officer присутня
- **Зробити:** Підтвердити наявність групи Parent у security/groups.xml; підтвердити точну кількість груп (13) та ACL (170+) повним переліком; підтвердити наявність файлу test_role_canon.py
- Чекер: відхилено 2 рази: Аналітик суперечить собі, заявляючи '6 з 6 базових груп підтверджено', але одразу додаючи, що група 'Parent' не знайдена у пробах. Оскільки 'Parent' є однією з 6 базових груп, вимога щодо їх повної наявності не виконана, що робить позначку '✅' для tz_claim передчасною.

### [F-WIZ-3] · TZ.md:117 · ТЗ заявляє: ✅
- Чому: Всі ключові елементи вимоги підтверджені: поле стану, каскад при approve, website_published до/після, а відсутність camp.draft — це очікувана відхилена частина.
- Доказ: models/camp.py:279 — camp_approval_state = fields.Selection(...)
- Доказ: models/camp.py:342 — def action_approve(self):
- Доказ: models/camp.py:356 — "camp_approval_state": "approved"
- Доказ: models/camp.py:359 — "website_published": True
- Доказ: models/camp.py:331 — Event stays unpublished (website_published=False, sale_ok=False on ticket)
- Доказ: models/camp.py:617 — "camp_approval_state": "rejected"
- Чекер: відхилено 2 рази: Вимога чітко зазначає 'Каскад створення (event + ticket + product + program + групи + budget + teczka) виконується при APPROVE'. Проби та докази аналітика демонструють зміну стану та оновлення `website_published` для існуючих об'єктів (наприклад, `self.camp_program_id.sudo().write(...)`), але не показують безпосереднього створення перелічених сутностей під час `action_approve`.

### [F-REC-1] · TZ.md:145 · ТЗ заявляє: ✅
- Чому: Всі ключові елементи F-REC-1 підтверджені: власна модель vacancy, публічний роут, заявка кандидата, hire у draft з §13-гейтом, і відсутність hr_recruitment у коді.
- Доказ: models/staffing.py:6 — 'camp.staff.vacancy — легка внутрішня модель вакансії (R13: БЕЗ hr_recruitment)'
- Доказ: models/staffing.py:53 — '_name = "camp.staff.vacancy"' (модель існує)
- Доказ: controllers/recruitment_portal.py:45 — '["/camp/vacancies"]' (публічний роут існує)
- Доказ: models/recruitment.py:25 — '_name = "camp.staff.application"' (модель заявки існує)
- Доказ: models/staffing.py:185 — 'staff = self.env["camp.staff"].create(' (створення camp.staff при hire)
- Доказ: models/staffing.py:171 — 'Hire the candidate: create a DRAFT camp.staff record' (draft-статус)
- Чекер: відхилено 2 рази: Проба `{"read": "models/recruitment.py", "from": 1, "to": 50}` не містить рядок `models/recruitment.py:25` з оголошенням моделі `camp.staff.application`, яка є ключовою для підтвердження 'заявка кандидата'.

### [F-REC-1a] · TZ.md:147 · ТЗ заявляє: ✅
- Чому: Всі заявлені в ТЗ маршрути, auth="public", pdfmake та ir.attachment підтверджені пробами.
- Доказ: controllers/kadry_forms.py:26 — route /camp/kadry/campscout з auth="public"
- Доказ: controllers/kadry_forms.py:32 — route /camp/kadry/rodzice з auth="public"
- Доказ: controllers/kadry_forms.py:37 — route /camp/kadry/wilcza з auth="public"
- Доказ: controllers/kadry_forms.py:30,35,42 — кожен route викликає _serve_html з відповідним html
- Доказ: static/src/kadry/assets/pdfmake.min.js:1 — pdfmake v0.2.20 присутній
- Доказ: controllers/document_submission.py:70,174,195,276 — використання ir.attachment
- Чекер: відхилено 2 рази: Вимога містить два чіткі пункти для майбутньої роботи: «план — перенести на власну модель [camp.document.submission.log], коли `-u` запрацює» та «REUSE-ЦІЛЬ: інтегрувати з `camp.staff.vacancy`». Ці пункти не відображені у полі `todo` аналітика, що робить вердикт `DONE` передчасним.

### [F-REC-3] · TZ.md:151 · ТЗ заявляє: 🟡
- Чому: Модель і гейти сертифікатів реалізовані, але повний пакет документів виховника та 10-річний retention контрактів відсутні.
- Доказ: models/operations.py:182 — cert_ids One2many на camp.staff.cert
- Доказ: models/operations.py:218-221 — compute перевіряє krk/rps/kierownik_course/wychowawca_course
- Доказ: models/operations.py:615 — expiry_date поле для сертифікатів
- Доказ: models/operations.py:744 — перевірка not_expired по expiry_date
- Доказ: models/operations.py:1693-1707 — retention_until compute: event end + 7 years
- Доказ: models/operations.py:1112 — 7-year retention cron згадка
- **Зробити:** 1) Додати чекліст документів на camp.staff (CV/анкета/umowa zlecenia/евіденція годин/рахунок) — зараз лише cert-поля, немає повного пакету. 2) Реалізувати upload документів у кабінеті staff (ir.attachment на hr.employee/camp.staff). 3) Додати явний retention для контрактів 10 років (зараз лише 7-річний). 4) Перевірити RODO art.10 захист видимості сканів (kierownik бачить, wychowawca/sales — ні) — докази не показали record rules для сканів кадри.
- Чекер: відхилено 2 рази: Вердикт 'PARTIAL' обґрунтований, але список 'todo' аналітика неповний. Пропущено вимоги щодо 'Акцепт лише вручну Admin/Organizator' та 'Кожен перегляд сканів → audit log', які не були згадані ні в доказах, ні в задачах до виконання.

### [F-KKW-2] · TZ.md:161 · ТЗ заявляє: ✅
- Чому: Core signoff fields and route exist, but the uniqueness constraint and canvas implementation are not evidenced by the probes.
- Доказ: controllers/portal.py:297 — route /my/participants/<int:participant_id>/sign exists
- Доказ: models/camp_escort.py:103-105 — signed_date, signed_ip, signed_by fields defined
- Доказ: models/camp_escort.py:170-199 — action_sign writes signed_date, signed_ip, signed_by
- Доказ: models/participant.py:537-542 — rodo_consent_id links to RODO consent log
- Доказ: tests/__init__.py:17,42 — test_escort_signoff and test_signoff_rodo registered
- **Зробити:** Verify the 'one child × one turn = one card' uniqueness constraint (no evidence found in probes); verify canvas/native signature implementation (no JS files found in static/src/js); verify parent data prefill logic
- Чекер: відхилено 2 рази: Вердикт аналітика 'PARTIAL' є обґрунтованим, але список доказів неповний. Вимога включає 'Binary attachment', і проби містять прямий доказ цього: `models/camp_escort.py:8:(Binary base64 PNG ...)`. Аналітик не включив цей пункт до свого списку доказів, що вказує на неповний аналіз проб.

### [F-MY-1] · TZ.md:223 · ТЗ заявляє: ✅
- Чому: Більшість маршрутів /my/* присутні, але /my/consents, /my/training, /my/escort та /my/participants/new не знайдені у пробах.
- Доказ: controllers/portal.py:46 — @http.route(["/my", "/my/home"]) exists
- Доказ: controllers/portal.py:207 — @http.route("/my/participants") exists
- Доказ: controllers/portal.py:324 — @http.route("/my/loyalty") exists
- Доказ: controllers/portal.py:345 — @http.route("/my/stories") exists
- Доказ: controllers/portal.py:409 — @http.route("/my/documents") exists
- Доказ: controllers/portal.py:454 — @http.route("/my/transport") exists
- **Зробити:** Додати маршрут /my/consents (відсутній у пробах); перевірити наявність /my/training та /my/escort (не знайдені у grep); перевірити pre-contract consent-блок на /my/participants/new (маршрут не знайдено)
- Чекер: відхилено 2 рази: Аналітик посилається на `controllers/portal.py:846` як доказ наявності поля `RODO art. 6(1)(a) consent`, проте цей рядок відсутній у наданих пробах для файлу `controllers/portal.py`. Це робить частину доказів неперевіреною.

### [F-OPS-2] · TZ.md:289 · ТЗ заявляє: ✅
- Чому: Основні моделі та роути присутні, але відсутні проби для тестів, QWeb шаблонів та фактичної реалізації immutable-патерну.
- Доказ: models/transport.py:22 — _name = "camp.transport"
- Доказ: models/transport.py:114 — participant_ids = fields.Many2many(...)
- Доказ: controllers/portal.py:454 — @http.route("/my/transport", ...)
- Доказ: models/camp_escort.py:41 — _name = "camp.escort"
- Доказ: models/camp_escort.py:21 — коментар про _PROTECTED_AFTER_SIGNOFF
- Доказ: scripts/populate_escort_from_204.py:29 — логгер populate_escort_from_204
- **Зробити:** Підтвердити наявність та зміст test_escort_signoff.py; перевірити QWeb шаблони dozwoła+RODO; перевірити immutable draft→collected→signed патерн (лише коментар, не код)
- Чекер: відхилено 2 рази: Вердикт 'PARTIAL' та список 'todo' не враховують відсутність проб для багатьох полів, що явно перераховані у вимозі для моделей `camp.transport` (локації, час, транспорт, водій) та `camp.escort` (participant_id, registration_id, direction тощо). Без цих проб неможливо підтвердити, що моделі реалізовані згідно з детальною специфікацією.

### [F-OPS-4] · TZ.md:293 · ТЗ заявляє: ✅
- Чому: Модель, cron та ACL підтверджені, але QWeb-сертифікат і /my/training портал-маршрут відсутні в коді, тому вимога виконана лише частково.
- Доказ: models/training.py:73 — camp.staff.training.record згадується в даних
- Доказ: models/training.py:107 — _name = "camp.staff.training.record" (модель існує)
- Доказ: models/training.py:38 — _inherit = "slide.channel" (розширює native slide.channel)
- Доказ: data/cron.xml:46-49 — cron для expiry на keeper (перенесено)
- Доказ: security/ir.model.access.csv:63-66 — ACL/rules для моделі (admin/user/hr/portal)
- Доказ: controllers: [0 збігів] — /my/training портал-маршрут НЕ існує
- **Зробити:** 1) Створити printable QWeb-сертифікат (reports) для camp.staff.training.record — заявлено в ТЗ, але коду немає. 2) Збудувати /my/training портал-маршрут (контролер) — заявлено як 🟡 backlog, але в коді відсутній.
- Чекер: відхилено 2 рази: Аналітик невірно інтерпретував вимогу щодо `/my/training` порталу. Вимога чітко зазначає, що `/my/training` портал-маршрут НЕ збудований і НЕ має бути збудований. Відсутність збігів у пробі `controllers` підтверджує виконання цієї частини вимоги, а не її відсутність. Тому пункт `🟡 /my/training портал-кабінет — не збудовано (backlog)` у `tz_claim` та відповідний `todo` є помилковими.

### [N-4] · TZ.md:332 · ТЗ заявляє: ✅
- Чому: Частина вимог підтверджена (CI, імперсонація, видалення /api/v1), але секрети через ir.config_parameter не знайдено, а публічна форма явно 🔴 — тому статус ✅ завищений.
- Доказ: .github/workflows/ci.yml:21 — CI містить ruff, bandit, gitleaks (без safety)
- Доказ: models/admin_access_log.py:3 — імперсонація логується (RODO art.30)
- Доказ: models/art9_security.py:46 — коментар про sudo-без-юзера, але не знайдено ir.config_parameter/get_param
- Доказ: controllers — /api/v1 відсутній (0 збігів)
- Доказ: controllers/kadry_forms.py — honeypot/rate-limit/mime-whitelist відсутні (0 збігів)
- **Зробити:** Додати safety у CI; підтвердити/реалізувати зберігання секретів через ir.config_parameter; реалізувати honeypot+rate-limit+mime-whitelist у публічній формі (беклог №10)
- Чекер: відхилено 2 рази: Вердикт PARTIAL коректний, але аналітик не згадав у доказах чи todo відсутність `with_user + HMAC-патерн` для імперсонації, хоча відповідна проба дала 0 збігів. Це робить обґрунтування неповним.

### [N-5] · TZ.md:334 · ТЗ заявляє: ✅
- Чому: staging_sync.sh підтверджує нейтралізацію, але бекапи та lossless-інваріант не знайдені, тому заявлений ✅ не повністю підтверджений.
- Доказ: scripts/staging_sync.sh:2 — скрипт рефрешу staging із prod (БД + filestore) + НЕЙТРАЛІЗАЦІЯ + install fayna_camp_portal
- Доказ: tools/deploy-staging.sh — 0 збігів на 'backup'
- Доказ: docs/MIGRATION_BACK.md — 0 збігів на 'row.count|row_count|lossless'
- Доказ: tools/deploy-staging.sh — 0 збігів на 'cron.*off|mail.*off|SMS.*off'
- **Зробити:** Додати бекап перед -u/міграцією в deploy-staging.sh; додати lossless-інваріант row-count в MIGRATION_BACK.md; додати нейтралізацію mail/SMS/crons в deploy-staging.sh
- Чекер: відхилено 2 рази: Аналітик пропустив частину вимоги 'scratchpad-стенд ≠ git (синхронізувати перед -u — урок R1)' у своєму аналізі та списку todo.

### [M-2] · TZ.md:364 · ТЗ заявляє: ✅
- Чому: Скрипти існують, але ключова функція migrate_bs_signatures.py позначена DEPRECATED, а заявлені властивості (ідемпотентність, DRY_RUN, savepoints, репетиції, lossless) не підтверджені жодним доказом.
- Доказ: scripts/populate_from_bs.py:3 — існує, MIGRATION_BACK крок 4.3
- Доказ: scripts/migrate_bs_signatures.py:37 — DEPRECATED: sale.order.bs_parents_signature не існує
- Доказ: scripts/populate_escort_from_204.py:10 — існує, паттерн з populate_from_bs
- Доказ: scripts/populate_children_and_events.py:54 — функція populate_children_and_events() існує
- Доказ: scripts/populate_step2_groups_budgets.py:3 — існує, кроки 4.2+4.4
- Доказ: scripts/populate_step3_money_vacancies.py:3 — існує, крок 4.4+автоштат
- **Зробити:** 1) Видалити або переписати migrate_bs_signatures.py (DEPRECATED, суперечить ТЗ: 97→107 підписів). 2) Додати докази ідемпотентності, DRY_RUN, savepoints, репетицій на прод-копії, lossless (114 дітей, 97 підписів, detach+uninstall=0 втрат) — зараз їх немає в коді.
- Чекер: відхилено 2 рази: Вердикт аналітика суперечливий: `tz_claim: "✅"` не відповідає `PARTIAL` статусу та значному списку `todo`. Крім того, відсутня проба для скрипта `migrations/17.0.4.0.0/post-migrate.py`, який згаданий у вимозі, що робить перевірку неповною.

### [Q8-1] · TZ.md:392 · ТЗ заявляє: 🟡
- Чому: R4/R4b (desktop kiosk, langbar) підтверджені, але «Powrót do kiosku»/селектор табору відсутні, а R5/R8/R9 не мають доказів.
- Доказ: static/src/js/kiosk_app.js:75 — rpc /camp/kiosk/layout для рендеру плиток
- Доказ: static/src/scss/kiosk.scss:32,37,201 — desktop-змінні (tile min-height, gap) для R4b
- Доказ: static/src/xml/kiosk_template.xml:33-41 — langbar PL/UA у шапці (R4)
- Доказ: controllers/kiosk.py:230-258 — layout endpoint з per-role tile grid
- Доказ: static/src/xml/kiosk_template.xml — grep 'Powrót do kiosku' дав 0 збігів
- **Зробити:** Додати «Powrót do kiosku»/селектор табору (немає жодного сліду в коді); надати докази для R5 (бренд), R8 (кольори), R9 (заголовок/контекст) — у пробах їх немає.
- Чекер: відхилено 2 рази: Аналітик стверджує, що «Powrót do kiosku» не має жодного сліду в коді, але проба `controllers/kiosk.py` містить `/camp/kiosk/back_visible` та його docstring, що прямо згадує '← Powrót'. Це суперечить твердженню про повну відсутність слідів.

### [Q8-18] · TZ.md:409 · ТЗ заявляє: ✅
- Чому: Фікси (б) та (в) реалізовані, але блокер (а) — читання jsonb як сирого тексту — залишається невиправленим, тому вимога виконана лише частково.
- Доказ: migrations/17.0.4.1.5/post-migrate.py:33,39 — CONCAT_WS використовується без ->>'en_US', тобто фікс (а) НЕ застосовано
- Доказ: migrations/17.0.4.1.7/post-migrate.py:45-46,99-103 — дедуплікація з пріоритетом certified>completed та свіжішим issue_date реалізована (фікс б)
- Доказ: migrations/17.0.4.1.7/post-migrate.py:171,426 — ON CONFLICT залишається, але тепер як захист після дедуплікації
- Доказ: migrations/17.0.4.1.6/post-migrate.py:362-375 — дозаповнення _compute_name/_compute_day_count/_compute_day_number/_compute_display_name реалізовано (фікс в)
- **Зробити:** Застосувати фікс (а): у migrations/17.0.4.1.5/post-migrate.py:33,39 замінити CONCAT_WS(d.dietary_restrictions, ...) на CONCAT_WS(d.dietary_restrictions->>'en_US', ...) для коректного читання jsonb-колонки
- Чекер: відхилено 2 рази: Аналітик стверджує, що фікс (в) реалізовано (migrations/17.0.4.1.6/post-migrate.py:362-375), але не надано жодних проб (grep) для цього файлу чи згаданих методів `_compute_*`, що підтверджували б це твердження.

### [Q8-19] · TZ.md:415 · ТЗ заявляє: 🟡
- Чому: Код міграцій і тестів на місці й компілюється, але заявлені у ТЗ п.1-2 (зелений тест-сьют, staging-перевірка) не підтверджені пробами, а п.3-5 (коміт/пуш) очевидно не виконані.
- Доказ: __manifest__.py:5 — версія 17.0.4.1.8 підтверджена
- Доказ: migrations/17.0.4.1.5/post-migrate.py:34-57 — READ-бік pair4: ->>'en_US' + COALESCE pl_PL, обидві мови зберігаються
- Доказ: migrations/17.0.4.1.8/post-migrate.py:39-71 — repair-міграція: шукає notes->>'en_US' LIKE '{%', ідемпотентна
- Доказ: migrations/17.0.4.1.6/post-migrate.py:1-69 — pair5 backfill існує (частково прочитано)
- Доказ: migrations/17.0.4.1.7/post-migrate.py:33-52 — pair6 дедуплікація: групування за (partner, course), пріоритет стану, chatter-слід
- Доказ: tests/test_legacy_program_migration.py:287 — тест test_migration_backfills_stored_computes_and_frame_day_defaults існує
- **Зробити:** Підтвердити фактичний зелений прогін тестів на реальній БД (п.1 плану) та staging-перевірку (п.2) — ці докази з репо не видно; коміт/пуш (п.3-5) не зроблено.
- Чекер: відхилено 2 рази: Аналітик заявляє про існування та вміст міграцій `17.0.4.1.7`, `17.0.4.1.8` та тесту `test_legacy_program_migration.py`, але відповідні проби для цих файлів відсутні. Проба для `17.0.4.1.6` є неповною і не підтверджує деталі ORM-логіки backfill, а для `17.0.4.1.7` заявлена умова групування (`partner, course`) відрізняється від вимоги (`partner, bucket`).

### [PR-1] · TZ.md:432 · ТЗ заявляє: ✅
- Чому: Підтверджено лише частину конвеєра (ADR-гейт, QA-Playwright, test-gate, e2e), але відсутні докази для 4 з 9 заявлених етапів, тому повна дієвість конвеєра не доведена.
- Доказ: docs/TZ.md:432 — заявлено повний конвеєр: діагностика (Explore) → ADR (Native Odoo: + platform-reviewer) → виконавець → 2 гейти (Odoo-reviewer + QA-Playwright) → CTO fix-forward → PR → CI (Lint+test-gate+e2e) → merge, статус ✅ діє
- Доказ: docs/TZ.md:66 — ADR-гейт з рядком `Native Odoo:` підтверджено як дієвий (доказ: рекрутацію-custom відхилено)
- Доказ: docs/TZ.md:432 — згадка platform-reviewer approve у конвеєрі
- Доказ: docs/TZ.md:113 — QA-Playwright наскрізний тест майстра підтверджено (PR #14 merged, staging)
- Доказ: .github/workflows/ci.yml:39 — існує job 'Odoo unit tests (test-gate)'
- Доказ: .github/workflows/e2e.yml:15,35 — існує workflow e2e з запуском pytest у e2e/
- **Зробити:** Надати докази для етапів: 'діагностика (Explore)', 'Odoo-reviewer код' як окремого гейта, 'CTO fix-forward' та 'Lint' у CI — жоден із цих елементів не підтверджено наявними пробами
- Чекер: відхилено 2 рази: Аналітик помилково зазначив 'Odoo-reviewer код' як відсутній доказ, хоча `docs/TZ.md:64` прямо згадує 'код-рев'ю' та 'Odoo-platform-reviewer'. Крім того, вердикт повністю проігнорував частину вимоги 'Кожен REJECT реальний (доведено: соло дало б хибне «зелено» двічі за 02.07)'.

### [PR-2] · TZ.md:434 · ТЗ заявляє: ✅
- Чому: Заявлений статус ✅ не підтверджено конкретними доказами — лише загальні згадки 'experiential-прогони' без цитованих exit code/виводів/рядків.
- Доказ: docs/TZ.md:434 — текст PR-2 з вимогами: fresh-доказ, experiential login-as кожною роллю, adversarial judge + programmatic-критерій; позначено ✅ діє
- Доказ: docs/TZ.md:97 — згадка 'experiential-прогони конвеєра 24-25.06' без конкретики login-as кожною роллю
- Доказ: docs/TZ.md:204 — згадка 'experiential-прогони' без доказів відсутності помилок/сирих полів
- **Зробити:** Надати fresh-доказ у тому ж ході: exit code/вивід/рядок для login-as кожною роллю (батько, виховник, інструктор, керівник, організатор) без помилки/сирого поля; підтвердити adversarial judge (інша модель) + ≥1 programmatic-критерій конкретним рядком/логом
- Чекер: відхилено 2 рази: Вердикт аналітика 'PARTIAL' є занадто оптимістичним. У наданих пробах повністю відсутні докази щодо компонента 'adversarial judge (інша модель) + ≥1 programmatic-критерій', а докази для 'experiential login-as кожною роллю без помилки/сирого поля' є нечіткими та неповними.

### [PR-4] · TZ.md:438 · ТЗ заявляє: ✅
- Чому: Більшість підпунктів підтверджено, але доказ для asset-only бампу версії неповний — показано лише поточну версію без історії змін.
- Доказ: __manifest__.py:5 — version 17.0.4.1.8 присутня, але немає доказів, що вона була бампнута саме через asset-only зміни
- Доказ: hooks.py:136 — post_init_hook використовується для міграцій даних, що відповідає вимозі (post_init_hook ≠ upgrade)
- Доказ: __manifest__.py — відсутній ключ 'migrations/', що відповідає вимозі про migrations/ для існуючих БД
- Доказ: views/*.xml — groups= використовуються лише на рівні полів/кнопок, не на root tree/form, що відповідає вимозі
- **Зробити:** Підтвердити, що версія маніфеста була бампнута саме через asset-only зміни (наприклад, через git log/commit history). Проба на --i18n-overwrite не вдалася через помилку git grep.
- Чекер: відхилено 2 рази: Вердикт аналітика є 'PARTIAL', що відповідає наявним доказам. Однак, обґрунтування та список 'todo' є неповними. З 7 чітко сформульованих пунктів вимоги, 3 були повністю проігноровані (clear .pyc, XML-ID стандартних модулів звіряти, No-Manual-DB), а не лише 2, як зазначено в 'todo'. Твердження 'Більшість підпунктів підтверджено' є неточним, оскільки 5 з 7 пунктів не підтверджені повністю.

### [PR-5] · TZ.md:440 · ТЗ заявляє: ✅
- Чому: Частина вимог підтверджена (group-by, i18n, /my роути, staging, mobile), але ключові (збереження форми, workflow, авто-розрахунки, ux-гейт) не мають доказів у наданих пробах.
- Доказ: views/budget_views.xml:187 — group_by camp_season_id (по табору)
- Доказ: models/camp.py:28 — translate=True (i18n)
- Доказ: controllers/portal.py:46 — /my/home роут
- Доказ: controllers/escort_portal.py:56 — /my/escort роут
- Доказ: .github/workflows/deploy-staging.yml:47 — staging health check
- Доказ: static/src/scss/kiosk.scss:2 — mobile-first styles
- **Зробити:** Немає доказів: форма зберігається, юр-документи workflow, авто-розрахунки, IA-меню, ux-гейт N-1, mobile-audit для /my/*
- Чекер: відхилено 2 рази: Аналітик посилається на докази (`controllers/portal.py:46`, `controllers/escort_portal.py:56`, `static/src/scss/kiosk.scss:2`) для пунктів 'mobile-audit для /my/*' та 'mobile-first styles', які відсутні у наданих пробах. Це ставить під сумнів обґрунтування вердикту PARTIAL.

## 🔴 НЕ ЗРОБЛЕНО — 28

### [R-5] · TZ.md:103 · ТЗ заявляє: 🔴
- Чому: All role labels are hardcoded as 'kierownik'/'komendant' with no per-organizer-type configuration; no _get_role_label() helper exists.
- Доказ: models/_role_taxonomy.py:21 — hardcoded 'kierownik' label, no per-organizer-type dictionary
- Доказ: models/_role_taxonomy.py:40-41 — 'director' and 'leader' both map to 'kierownik', no configurable labels
- Доказ: controllers/admin.py:182 — hardcoded 'Kierownik' label in admin controller
- Доказ: templates/portal_templates.xml:70 — hardcoded 'Panel kierownika obozu' in template
- Доказ: templates/portal_templates.xml:410 — hardcoded 'Кабінет керівника табору' in template
- **Зробити:** Implement configurable role-label dictionary per organizer type (commercial camp vs scouting), add _get_role_label() helper, and replace all hardcoded labels in views/templates/controllers
- Чекер: підтверджено: Аналітик вірно визначив `NOT_DONE`. Надані докази (жорстко закодовані лейбли 'kierownik' у моделях та контролерах, а також відсутність згадок про `_get_role_label()` або конфігурований словник) прямо

### [F-WIZ-7] · TZ.md:125 · ТЗ заявляє: 🔴
- Чому: У коді немає жодних слідів реалізації is_high_risk, required license або insurance attachment — лише документація та аудит-пропозиції.
- Доказ: docs/TZ.md:125 — вимога F-WIZ-7 позначена 🔴 не реалізовано, згадуються GAP-и experiential seed та event 140 Ski Zakopane
- Доказ: docs/TZ.md:125 — описує бажаний механізм: boolean `is_high_risk` + activity-тип-тригер → вакансія instructor з required license-cert + required insurance attachment
- Доказ: docs/tz-audit/2026-07-03/TZ_IMPROVE_2026-07-03.md:31 — пропозиція DoD: WHEN event identified as 'high-risk' THEN system SHALL auto-create instructor vacancy with license requirement and insurance attachment
- Доказ: docs/tz-audit/2026-07-03/TZ_AUDIT_2026-07-03.md:92 — аудит підтверджує нечіткість умови activity-тип-тригер та відсутність повного переліку high-risk активностей
- **Зробити:** Реалізувати: boolean is_high_risk на event, activity-тип-тригер (лижі/вода), автостворення instructor-вакансії з required license-cert, required insurance attachment на event
- Чекер: підтверджено: Усі проби підтверджують вердикт аналітика: вимога явно позначена як 'не реалізовано' в TZ.md, а аудит вказує на відсутність чітких критеріїв та механізмів реалізації. Жодних слідів фактичної реалізаці

### [F-PRG-3] · TZ.md:137 · ТЗ заявляє: 🟡
- Чому: У коді немає жодного доказу блокуючого constraint на 100% заповнення програми — лише згадка відсотків у контексті знижок та явна відмова від блокування старту.
- Доказ: models/commercial.py:1976 — згадка 100% лише в help-тексті про відсотки знижки, не про заповнення програми
- Доказ: models/regulamin.py:14 — явно вказано, що непідписаний регулямін НЕ блокує старт зміни
- Доказ: models/regulamin.py:210 — коментар: NO hard block, рішення з ТЗ §4
- Доказ: models/camp.py:88 — _sql_constraints існує, але проба не показала constraint на 100% програми
- **Зробити:** Додати блокуючий чек при старті табору, який перевіряє, що програма заповнена на 100% (аналогічно до індикатора в [F-KSK-3])
- Чекер: підтверджено: Аналітик вірно інтерпретував проби: згадка '100%' стосується знижок, а не заповнення програми, а блокування старту табору явно відсутнє для інших умов. Жодна проба не підтверджує наявність блокуючого

### [F-PRG-4] · TZ.md:139 · ТЗ заявляє: 🔴
- Чому: Код повністю відсутній — лише згадка назви в шаблоні teczki, що підтверджує заявлений статус 🔴.
- Доказ: reports/teczka_report_templates.xml:113 — лише згадка назви "Program wypoczynku (Załącznik 9)" у шаблоні teczki, не окремий PDF-звіт
- Доказ: reports/ — немає жодного файлу з program_wypoczynku
- Доказ: reports/ — немає жодного ir.actions.report для програми
- Доказ: tests/ — немає test_program_pdf
- **Зробити:** Створити ir.actions.report + QWeb-шаблон для Program Wypoczynku (Załącznik 9) за wzorem MEN, аналогічно karta_report_templates.xml; додати кнопку друку PDF з форми програми; написати тест test_program_pdf.py
- Чекер: підтверджено: Проби однозначно підтверджують відсутність будь-яких згадок про `program_wypoczynku` як окремого звіту (`ir.actions.report`, файлів у `reports`, тестів), окрім однієї текстової згадки назви в іншому ш

### [F-RODO-1] · TZ.md:177 · ТЗ заявляє: ✅
- Чому: Код моделі та тестів відсутній у репозиторії, лише згадки в __init__.py, тому вимога не виконана.
- Доказ: tests/__init__.py:30 — тест test_rodo_consent_immutable згадано, але сам файл не знайдено
- Доказ: tests/__init__.py:42 — тест test_signoff_rodo згадано, але сам файл не знайдено
- Доказ: models — 0 збігів для fayna_rodo_consent_log, consent_type, hmac_hash
- **Зробити:** Створити модель fayna_rodo_consent_log з полями partner, consent_type, action, timestamp, IP, user-agent, location, hmac_hash, source; реалізувати append-only логіку з HMAC; створити тести test_rodo_consent_immutable.py та test_signoff_rodo.py
- Чекер: підтверджено: Аналітик вірно інтерпретував результати проб: відсутність збігів для моделі та її полів у 'models', а також лише згадки про тести без самих файлів у 'tests', чітко вказують на невиконання вимоги. Верд

### [F-RODO-5] · TZ.md:185 · ТЗ заявляє: 🔴
- Чому: Жодних слідів міграції, unsubscribe чи інтеграції з SendPulse у коді — вимога повністю не реалізована.
- Доказ: models/res_partner_inherit.py:15-16 — лише коментар про відкликання згоди, без коду міграції чи unsubscribe
- Доказ: grep по models: 0 збігів fayna_rodo_consent_log
- Доказ: grep по migrations: 0 збігів sendpulse_privacy_consent_log чи source.*sendpulse
- Доказ: grep по models: 0 збігів email_opt_out
- Доказ: grep по __manifest__.py: 0 збігів sendpulse
- **Зробити:** Створити migration-скрипт для перенесення даних з sendpulse_privacy_consent_log у fayna_rodo_consent_log (source='sendpulse'), додати залежність sendpulse→rodo, реалізувати unsubscribe (email_opt_out + SendPulse API) та відображення стану згоди на res.partner
- Чекер: підтверджено: Усі проби показують відсутність ключових елементів вимоги (міграційні скрипти, цільова таблиця логів, механізм відписки, залежність від SendPulse). Єдиний знайдений збіг — це коментар, який не є реалі

### [F-KSK-3] · TZ.md:215 · ТЗ заявляє: 🟡
- Чому: Жоден з ключових елементів (deadline_date, checklist_ids, progress, countdown, mail.activity) не знайдено в коді, лише частково реалізовані стани submitted/registered.
- Доказ: models/camp.py — grep 'deadline_date': 0 збігів
- Доказ: models/camp.py — grep 'progress': 0 збігів
- Доказ: models/camp.py — grep 'mail.activity': 0 збігів
- Доказ: models/camp.py — grep 'countdown': 0 збігів
- Доказ: models/teczka_ko.py:23-24 — є стани submitted/registered, але немає draft
- Доказ: models/teczka_ko.py:268-284 — є поля для submitted/registered, але немає checklist_ids
- **Зробити:** Додати deadline_date, checklist_ids, progress-поля, countdown, mail.activity генератор на models/camp.py та models/teczka_ko.py; додати стан draft до _KURATORIUM_FILED_STATES
- Чекер: підтверджено: Усі проби підтверджують відсутність або часткову реалізацію ключових елементів вимоги (deadline_date, checklist_ids, progress, countdown, mail.activity, повний перелік станів). Вердикт NOT_DONE повніс

### [F-COM-4] · TZ.md:243 · ТЗ заявляє: 🔴
- Чому: Only camp-shift discuss.channel exists; no DM parent↔educator channel, no art.9 gate, no chat widget — matches 🔴 claim.
- Доказ: models/event_channel_create.py:34 — discuss.channel inherit exists but only for event/camp shift, not DM parent↔educator
- Доказ: models/camp_group.py — 0 matches for 'channel', no DM provisioning on group assignment
- Доказ: models/art9_security.py:65 — art.9 masking left as 'focused but invasive rework (21 fields)' — not implemented
- Доказ: controllers/portal.py:434,655 — chatter only for story/support detail, no DM chat widget
- **Зробити:** Implement ADR art.9 gate, DM channel creation on group assignment, chat widget in kiosk/portal
- Чекер: підтверджено: Аналітик вірно визначив, що вимогу не виконано. Проби підтверджують відсутність DM-чату виховник↔батьки, RODO art.9 гейту та відповідного віджету, а також те, що існуючий функціонал discuss.channel ст

### [F-SALE-3] · TZ.md:253 · ТЗ заявляє: 🔴
- Чому: Код не містить жодного product.document, а ТЗ прямо вказує на відсутність мапінгу для двох таборів.
- Доказ: docs/TZ.md:253 — ТЗ заявляє: без мапінгу лишились CS-ITA-01-26 і SP_01, потрібно додати 2 product.document
- Доказ: data — grep 'product.document' дав 0 збігів, тобто в коді немає жодного product.document
- Доказ: docs/TZ.md:253 — згадка BP-CAMP-PDF-01..04, DPI 171, attached_on='inside' лише в ТЗ, не в коді
- **Зробити:** Додати 2 product.document для CS-ITA-01-26 і SP_01 за BP-CAMP-PDF-01..04 (DPI 171, attached_on='inside', per-SKU)
- Чекер: підтверджено: Вердикт аналітика 'NOT_DONE' повністю підтверджується: вимога сама заявляє про відсутність мапінгу (🔴), а проба 'grep product.document' у 'data' не виявила жодних збігів, що свідчить про невиконання н

### [F-VAT-1] · TZ.md:265 · ТЗ заявляє: ✅
- Чому: У коді немає жодної згадки про list_price, markup або action_apply_computed_price — лише VAT-маржа (art. 119), тому вимога не реалізована.
- Доказ: models/budget.py:6 — згадка лише про VAT-маржу (art. 119), не про формулу list_price
- Доказ: models/budget.py:69-74 — поля про VAT-маржу, не про калькулятор ціни
- Доказ: models/budget.py:191-193 — Marża VAT, не list_price
- Доказ: models/budget.py:283-319 — VAT-розбивки, не формула ціни
- Доказ: tests/__init__.py:26 — test_pricing_calculator лише імпортований, не знайдено вмісту
- Доказ: tests/__init__.py:10 — test_budget лише імпортований, не знайдено вмісту
- **Зробити:** Реалізувати функцію action_apply_computed_price з формулою list_price = (Σcost ÷ діти) × (1+markup) × (1+VAT), включно з markup default 5% (editable, ≥5%), обмеженням реклами ≤20% бюджету та авто-product VAT 23% для мерчу; додати тести test_pricing_calculator.py та test_budget.py з реальними перевірками
- Чекер: підтверджено: Проби не містять жодних згадок про `list_price`, `markup`, або `action_apply_computed_price`. Згадки про `VAT` стосуються лише VAT-маржі (art. 119) та обліку, а не фактору `(1+VAT)` у формулі ціни. Те

### [F-FIN-5] · TZ.md:279 · ТЗ заявляє: 🔴
- Чому: No wizard or cancellation chain found; only BEP calculation and refund stub exist, so requirement is not built.
- Доказ: models/participant.py:1668 — _schedule_refund exists as stub (per TZ §8 п.7b)
- Доказ: models/participant.py:1707 — _schedule_refund called, but no full refund chain
- Доказ: models/commercial.py:1845 — only comment about cancel/refund% per contract, no wizard
- Доказ: wizards — no matches for cancel_event/event_cancel/wizard.*cancel
- Доказ: models/budget.py:395-414 — BEP fill computation exists, but no cancellation trigger
- **Зробити:** Implement wizard 'Скасувати заїзд' on event with confirmation, chaining cancel registrations + refund (full) + notify parents (SMS CRITICAL + email) + free places + decision log; depends on refund mechanism (§8 п.7b) which is still a stub.
- Чекер: підтверджено: Вердикт аналітика 'NOT_DONE' повністю відповідає статусу вимоги '🔴 не збудовано' та наданим доказам. Відсутність wizard-а для скасування заїзду (проба 'wizard.*cancel' дала 0 збігів) та заглушка для м

### [F-VAT-4] · TZ.md:281 · ТЗ заявляє: 🔴
- Чому: Код містить лише модель vat_marza в бюджеті (розрахунок), але жодної реалізації на боці фактури/KSeF — ТЗ 🔴 підтверджено.
- Доказ: __manifest__.py — 0 збігів sale_margin
- Доказ: __manifest__.py — 0 збігів account_tax_python
- Доказ: __manifest__.py — 0 збігів l10n_pl_ksef_margin
- Доказ: models/budget.py:68 — vat_marza лише поле-прапорець категорії, не реалізація фактури
- Доказ: models/budget.py:359-364 — vat_marza використовується лише в розрахунку бюджету, не на фактурі
- Доказ: models — 0 збігів purchase_price на sale.order.line
- **Зробити:** Реалізувати: depends += sale_margin/account_tax_python/l10n_pl_ksef_margin; purchase_price на sale.order.line; VAT-marża tax через account_tax_python; позначку «Procedura marży»; стик l10n_pl_ksef_margin → KSeF; тест фактури з базою=маржа
- Чекер: підтверджено: Усі надані проби підтверджують відсутність згаданих модулів (`sale_margin`, `account_tax_python`, `l10n_pl_ksef_margin`) у залежностях та відсутність реалізації `purchase_price` на `sale.order.line`,

### [F-DOC-2] · TZ.md:305 · ТЗ заявляє: 🟡
- Чому: У коді є лише action teczka_ko (чеклист), але жодної реалізації ZIP/PDF-збірки — вимога не виконана.
- Доказ: controllers/kiosk.py:88 — є лише action teczka_ko, але жодного збірника ZIP/PDF
- Доказ: controllers — 0 збігів 'Завантажити teczkę', '_render_qweb_pdf', 'zipfile|ZipFile|make_archive'
- Доказ: reports/teczka_reports.xml — 0 збігів 'karta|program|dziennik'
- **Зробити:** Реалізувати controller-stream: кнопка «Завантажити teczkę» → збірка attachments + _render_qweb_pdf (karty/program/dziennik) → ZIP + об'єднаний PDF з титулкою-реєстром; включити всі складники (оферта, договір, фактури, karty, program, dziennik, zgłoszenie, KRK+świadectwa, PSP+sanepid+szkic, поліса, RODO-zgody).
- Чекер: підтверджено: Вердикт аналітика 'NOT_DONE' повністю підтверджується пробами. Жодна з проб не виявила реалізації кнопки 'Завантажити teczkę', функціоналу збірки ZIP-архіву, об'єднання PDF або використання `_render_q

### [F-DOC-3] · TZ.md:307 · ТЗ заявляє: 🔴
- Чому: Жодних слідів реалізації в коді — вимога повністю відсутня.
- Доказ: docs/TZ.md:307 — вимога заявлена як 🔴 не збудовано
- Доказ: wizards/ — 0 збігів по 'mail.compose.message'
- Доказ: wizards/ — 0 збігів по 'attachment_ids'
- Доказ: wizards/ — 0 збігів по 'o2m'
- Доказ: grep 'Надіслати інспектору' — тільки в ТЗ та аудит-документах, не в коді
- **Зробити:** Реалізувати wizard з o2m-чеклистом вибору attachment, кнопку «Надіслати інспектору», що відкриває mail.compose.message з вибраними файлами, та логування в chatter табору.
- Чекер: підтверджено: Проби не виявили жодних слідів реалізації ключових компонентів вимоги (wizard, mail.compose.message, o2m-чеклист, текст кнопки) у коді, що повністю підтверджує вердикт аналітика 'NOT_DONE'.

### [N-3] · TZ.md:330 · ТЗ заявляє: 🟡
- Чому: Код має graceful degradation (controllers/portal.py:420), але жодних performance-бенчмарків немає — вимога зафіксована як 🟡 з GAP-5, що підтверджується відсутністю вимірів у репо.
- Доказ: docs/TZ.md:330 — цілі зафіксовані, вимірів нема — [GAP-5]
- Доказ: docs/TZ.md:352 — 🔴 performance-бенчмарки [N-3]
- Доказ: docs/TZ.md:519 — [GAP-5] Performance-бенчмарки: цілі є, вимірів нема
- Доказ: docs/QUALITY_AUDIT_2026-07-04.md:14 — coverage 69%, ціль ≥70% не досягнута
- **Зробити:** Створити k6/locust бенчмарки для checkout, submit карти, списку 10k, звіту, cron; зафіксувати p95 у CI-артефакт на staging (docs/TZ.md:519).
- Чекер: підтверджено: Вердикт аналітика 'NOT_DONE' повністю відповідає статусу '🟡' у самій вимозі [N-3], яка чітко вказує на відсутність вимірів (бенчмарків) для продуктивності ([GAP-5]). Наведені докази (docs/TZ.md:330, 3

### [T-5] · TZ.md:354 · ТЗ заявляє: 🔴
- Чому: Жодних слідів реалізації T-5 у коді — ні скрін-тестів, ні AI-оглядача, ні в'юпорт-матриці.
- Доказ: .github/workflows/e2e.yml — 0 збігів на screenshot/viewport (grep-проба 1)
- Доказ: .github/workflows/e2e.yml — 0 збігів на ux-nielsen-reviewer/adversarial/AI review/verdict (grep-проба 2)
- Доказ: .github/workflows/e2e.yml — 0 збігів на розміри в'юпортів 1440/390/844/900 (grep-проба 3)
- Доказ: e2e/test_critical_paths.py — 0 збігів на screenshot/full-page (grep-проба 4)
- Доказ: e2e/test_critical_paths.py:67 — лише тест критичного шляху грошей, без скрін-тестів
- **Зробити:** Додати в .github/workflows/e2e.yml screenshot-джобу з Playwright (матриця 2 в'юпорти × 2 мови), інтегрувати AI-оглядача ux-nielsen-reviewer з промптом «знайди, що зламано», зберегти скріни як артефакт CI-рана, заборонити merge при FAIL
- Чекер: підтверджено: Усі проби, що стосуються ключових компонентів вимоги (скріншоти, в'юпорти, AI-оглядач, інтеграція в CI), не дали збігів. Це повністю підтверджує вердикт NOT_DONE.

### [M-2b] · TZ.md:366 · ТЗ заявляє: 🔴
- Чому: Жоден з пошукових запитів не знайшов слідів реалізації вимоги — ні мапінгу лінків, ні звірки підпису, ні лічильника 59.
- Доказ: scripts/detach_campscout_management.py:51-57 — detach працює з ir_model_data, але немає згадок про product↔event лінки чи bs_organizer_signature
- Доказ: scripts/populate_from_bs.py:3 — описує міграцію bs_* (sale_order) → camp.participant, але не згадує product↔event чи bs_organizer_signature
- Доказ: grep bs_organizer_signature в models/views: 0 збігів
- Доказ: grep product.*event|event.*product в scripts: 0 збігів
- Доказ: grep 59 в scripts: 0 збігів
- **Зробити:** Дописати мапінг product↔event лінок (42/59 → 59/59) у detach/populate скрипти та додати контрольну звірку 59/59; реалізувати звірку bs_organizer_signature з джерелом підпису організатора
- Чекер: підтверджено: Проби не містять жодних згадок про 'product↔event лінки', 'bs_organizer_signature' або '59' у відповідних файлах, що підтверджує відсутність реалізації вимоги.

### [M-3] · TZ.md:368 · ТЗ заявляє: 🔴
- Чому: Жодних слідів реалізації скрипта чи моделі fayna_rodo_consent_log у репозиторії — вимога повністю не виконана.
- Доказ: scripts — 0 збігів 'fayna_rodo_consent_log'
- Доказ: scripts — 0 збігів 'rodo_consent.py'
- Доказ: scripts — 0 збігів 'res_partner_consent'
- Доказ: scripts — 0 збігів 'bs_client_consent'
- Доказ: scripts — 0 збігів 'source=bs'
- Доказ: scripts — 0 збігів 'source=legacy'
- **Зробити:** Створити скрипт консолідації RODO-згод у fayna_rodo_consent_log з source='bs'/'legacy', включити у послідовність кроком 4, додати SQL-звірку counts.
- Чекер: підтверджено: Усі проби, що шукають ключові компоненти вимоги (скрипти, моделі, логіку консолідації), повернули 0 збігів. Це повністю підтверджує вердикт аналітика про те, що вимога не виконана.

### [M-4] · TZ.md:370 · ТЗ заявляє: 🔴
- Чому: Код міграційних скриптів існує, але сама послідовність прода не виконана — ТЗ прямо вказує 🔴, а migrate_signatures ще не реалізований (лише заглушка).
- Доказ: scripts/populate_from_bs.py:3 — існує скрипт populate_from_bs (крок 4.3 міграції)
- Доказ: scripts/populate_escort_from_204.py:10 — існує скрипт escort (патерн з populate_from_bs)
- Доказ: scripts/detach_campscout_management.py:11 — існує скрипт detach з dry-run режимом
- Доказ: scripts/migrate_bs_signatures.py:35 — скрипт migrate_signatures лише повідомляє CTO, не виконує логіку
- Доказ: docs/TZ.md:370 — сам ТЗ підтверджує 🔴 НЕ виконано (P1.4 — головне плече, що лишилось)
- Доказ: docs/TZ.md:487 — P1.4 prod-міграція свідомо поза скоупом 17.07, лишається до 01.08/01.09
- **Зробити:** Виконати повну послідовність прода: backup → install portal+rodo → populate_from_bs (dry→commit) → RODO-extract → migrate_signatures (реальна логіка, не лише повідомлення CTO) → escort → detach (dry→commit) → verify §M-5 → uninstall legacy (окреме вікно після feature-parity). Провести свіжу репетицію на свіжій прод-копії, завершити [F-RODO-7] інфра-мандат, отримати UAT sign-off.
- Чекер: підтверджено: Вердикт аналітика повністю відповідає вимозі, яка прямо заявляє «🔴 НЕ виконано». Докази підтверджують, що хоча деякі скрипти існують, ключові кроки (як-от реалізація migrate_signatures) та загальна по

### [Q8-7] · TZ.md:398 · ТЗ заявляє: 🔴
- Чому: Код _schedule_refund існує, але це лише заглушка-лог, реальний refund-механізм не реалізовано — вимога 7b залишається 🔴.
- Доказ: models/participant.py:1668 — _schedule_refund існує, але ТЗ (docs/TZ.md:169) прямо каже: 'refund — заглушка (_schedule_refund лише логує)'
- Доказ: docs/TZ.md:398 — '7b. Auto-refusal REFUND — реалізувати справжнє повернення (зараз placeholder-лог у _schedule_refund)'
- Доказ: docs/TZ.md:477 — 'Refund реальний [§8 7b] — замінити _schedule_refund заглушку на справжнє повернення'
- **Зробити:** Замінити тіло _schedule_refund (models/participant.py:1668) з простого логування на реальний механізм повернення коштів (повний refund) + запис у RODO-лог, згідно критерію EARS у docs/TZ.md:169
- Чекер: підтверджено: Вимога полягає у реалізації справжнього повернення, замінивши заглушку. Усі надані докази, включаючи саму вимогу, підтверджують, що `_schedule_refund` досі є заглушкою, а отже, реальне повернення не р

### [Q8-11] · TZ.md:402 · ТЗ заявляє: нема
- Чому: Жодних слідів реалізації ZIP-функціоналу не знайдено в жодному з ключових каталогів.
- Доказ: models — 0 збігів по teczka_zip|zip_teczka|download_zip|send_zip
- Доказ: controllers — 0 збігів по teczka_zip|zip_teczka|download_zip|send_zip
- Доказ: views — 0 збігів по teczka_zip|zip_teczka|download_zip|send_zip
- Доказ: reports — 0 збігів по teczka_zip|zip_teczka|download_zip|send_zip
- Доказ: wizards — 0 збігів по teczka_zip|zip_teczka|download_zip|send_zip
- **Зробити:** Реалізувати функціонал ZIP-архіву течки (F-DOC-2) та надсилання інспектору (F-DOC-3) — створення архіву, завантаження, відправка
- Чекер: підтверджено: Проби релевантні до вимоги та охоплюють ключові каталоги. Відсутність збігів чітко підтверджує вердикт NOT_DONE, а todo точно відображає необхідну роботу.

### [Q8-13] · TZ.md:404 · ТЗ заявляє: 🔴
- Чому: ТЗ явно вказує 🔴 не збудовано, і проби підтверджують: є лише канали для табірних змін (event_channel_create), а DM-чату виховник↔батьки немає.
- Доказ: docs/TZ.md:243 — [F-COM-4] DM-чат виховник↔батьки своєї групи: 🔴 не збудовано (єдиний великий функціональний гап епіка E)
- Доказ: models/event_channel_create.py:76 — _create_camp_discuss_channel створює discuss.channel для event.event (табірних змін), але не для DM-чату виховник↔батьки
- Доказ: models/event_channel_create.py:106 — _sync_camp_discuss_channel_members синхронізує учасників каналів табірних змін, не батьківських DM
- Доказ: controllers — 0 збігів message_post, views — 0 збігів discuss: немає чатер-віджета для батьків
- **Зробити:** Створити DM-чат виховник↔батьки своєї групи: ADR (art.9-гейт), провізія discuss.channel на призначенні групи (патерн event_channel_create), чатер-віджет у kiosk/портал
- Чекер: підтверджено: Аналітик вірно інтерпретував проби та вимогу. `TZ.md` прямо вказує, що функціонал [F-COM-4] не збудовано (🔴). Проби підтверджують, що існуючі `discuss.channel` та `message_post` використовуються для т

### [Q8-14] · TZ.md:405 · ТЗ заявляє: ⚪
- Чому: Жодних слідів реалізації honeypot або rate-limit у коді, лише текстова згадка в описі.
- Доказ: controllers — 0 збігів 'honeypot'
- Доказ: controllers — 0 збігів 'rate.limit'
- Доказ: models — 0 збігів 'honeypot'
- Доказ: models — 0 збігів 'rate_limit'
- Доказ: static — 0 збігів 'honeypot'
- Доказ: static/description/index.html:204 — згадка 'rate limiting' лише в описі, не в коді
- **Зробити:** Реалізувати honeypot та rate-limit у контролерах/моделях публічної форми заявок
- Чекер: підтверджено: Проби не виявили жодних слідів реалізації honeypot або rate-limit у коді (контролерах, моделях). Єдина згадка 'rate limiting' знайдена в описі (`static/description/index.html`), що не є реалізацією. В

### [Q8-15] · TZ.md:406 · ТЗ заявляє: 🔴
- Чому: Only role taxonomy and incidental leader fields exist; no zveno entity or dedicated leader management implemented.
- Доказ: models/_role_taxonomy.py:41 — "leader": "kierownik" (role exists, but no zveno/team_leader field)
- Доказ: models/operations.py:2704 — help=_("Camp leader assigned to this group.") (leader field on group, but no zveno structure)
- Доказ: models/operations.py:3495 — help=_("Camp leader named on this notification") (leader on notification, not zveno)
- Доказ: views/ — 0 matches for 'leader' (no UI for zveno/leader management)
- **Зробити:** Implement zveno (squad) model with leader assignment, add views for zveno management, and link participants to zveno leaders.
- Чекер: підтверджено: Проби не містять згадок про модель 'zveno' (загін/звено) або полів 'team_leader'/'leader_id', які б вказували на реалізацію структури 'звена + лідери'. Існуючі згадки 'leader' стосуються загальної рол

### [PR-6] · TZ.md:442 · ТЗ заявляє: ✅
- Чому: Код досі містить власні моделі рекрутації, які аудит прямо називає антиприкладом, а inherit-розширення стандартних моделей відсутнє.
- Доказ: models/recruitment.py:25 — _name = "camp.staff.application" (власна модель, не inherit hr.applicant)
- Доказ: models/recruitment.py:42 — "camp.staff.vacancy" (власна модель, не inherit hr.job)
- Доказ: models/recruitment.py — grep по hr.recruitment/hr.applicant: 0 збігів
- Доказ: models/recruitment.py — grep по _inherit hr.recruit/hr.applicant: 0 збігів
- Доказ: docs/reuse-audit/2026-07-04/REUSE_AUDIT.md:27-28 — аудит прямо вказує, що camp.staff.application/vacancy мають бути замінені на hr_recruitment (hr.applicant/hr.job)
- **Зробити:** Видалити власні моделі camp.staff.application і camp.staff.vacancy; замінити на inherit-надбудови над hr.applicant і hr.job зі стандартного модуля hr_recruitment (Community); додати письмовий доказ «аналога НЕМА» в PR-опис/ADR для будь-яких нових моделей.
- Чекер: підтверджено: Проби чітко показують наявність власних моделей `camp.staff.application` та `camp.staff.vacancy` без успадкування від стандартних `hr.applicant`/`hr.job`, що прямо суперечить вимозі та є канонічним ан

### [GAP-2] · TZ.md:513 · ТЗ заявляє: 🔴
- Чому: У коді повністю відсутні будь-які сліди підгруп/звень та прапорця лідера — вимога не реалізована.
- Доказ: models — grep is_subgroup_leader: 0 збігів
- Доказ: models — grep camp.subgroup: 0 збігів
- Доказ: views — grep subgroup: 0 збігів
- Доказ: controllers — grep subgroup: 0 збігів
- Доказ: security — grep subgroup: 0 збігів
- Доказ: tests — grep subgroup: 0 збігів
- **Зробити:** Реалізувати модель camp.subgroup (або self-ref на camp.group), прапорець is_subgroup_leader на participant, вкладку у кіоску виховника
- Чекер: підтверджено: Проби підтверджують відсутність згаданих у вимозі елементів коду (`is_subgroup_leader`, `camp.subgroup`, `subgroup`), що прямо вказує на нереалізованість функціоналу 'Звена (підгрупи) + дитячі лідери'

### [GAP-3] · TZ.md:515 · ТЗ заявляє: 🔴
- Чому: ТЗ сам стверджує, що UAT не проводився, і він позначений як 🔴 — код відсутній, лише опис процедури.
- Доказ: docs/TZ.md:515 — [GAP-3] UAT з живими користувачами: Жодного формального UAT-циклу з реальними kierownik/батьками не було (тільки агенти+власник)
- Доказ: docs/TZ.md:455 — [ ] 🔴 Human QA green по всіх ролях на staging + UAT sign-off ([T-4]) — чекбокс не відмічено
- Доказ: docs/TZ.md:487 — Human QA formal UAT sign-off свідомо поза скоупом 17.07 (лишається до 01.08/01.09)
- Доказ: docs/TZ.md:352 — 🔴 UAT з живими користувачами (usability-test-plan) перед prod — у переліку відомих боргів
- **Зробити:** Провести UAT-цикл з 3-5 живими користувачами (kierownik/батьки) на staging: 3-5 задач (створити табір; заповнити карту з телефона; знайти документ на «контролі»), задокументувати результати і sign-off у docs/TESTING.md, 0 критичних блокерів.
- Чекер: підтверджено: Аналітик вірно визначив статус 'NOT_DONE'. Численні докази (чекбокси, позначки 🔴, явні заяви про 'поза скоупом' та 'відомі борги') послідовно підтверджують, що формальний UAT-цикл з живими користувача

### [GAP-5] · TZ.md:519 · ТЗ заявляє: 🔴
- Чому: У ТЗ статус 🔴 (не зроблено), у коді немає жодних слідів бенчмарків — вердикт NOT_DONE.
- Доказ: .github/workflows — 0 збігів по 'k6|locust'
- Доказ: .github/workflows — 0 збігів по 'p95|percentile'
- Доказ: docs/TZ.md:352 — [T-4] прямо вказує: '🔴 performance-бенчмарки [N-3]'
- **Зробити:** Створити k6/locust сценарій для checkout+/my, запускати на staging, фіксувати p95 у CI-артефакт
- Чекер: підтверджено: Вердикт NOT_DONE повністю підтверджується: у CI-конфігураціях відсутні згадки про k6/locust та p95, а сам документ TZ.md прямо вказує на статус '🔴 performance-бенчмарки'.

## 🟡 ЧАСТКОВО — 70

### [B-5] · TZ.md:56 · ТЗ заявляє: 🟡
- Чому: Код містить переклади через _()/_t() для обох мов, але відсутні файли перекладів у i18n/, тому повна двомовність не підтверджена з репозиторію.
- Доказ: controllers/admin.py:182-185 — переклади ролей польською/українською через _()
- Доказ: controllers/admin.py:283-287 — переклади статусів польською/українською через _()
- Доказ: controllers/kiosk.py:258 — польський переклад помилки кіоску через _()
- Доказ: controllers/kiosk.py:318-337 — переклади помилок мови через _()
- Доказ: tests/http_lang.py:23 — тести підтримують pl_PL та uk_UA
- Доказ: static/src/js/kiosk_app.js:20 — імпорт _t для JS-перекладів
- **Зробити:** Підтвердити наявність активних .po файлів для pl_PL та uk_UA (не знайдено в i18n/), перевірити деплой на staging (run 28699005633) та живу двомовність на всіх екранах
- Чекер: підтверджено: Аналітик коректно визначив, що наявність функцій перекладу (`_()`, `_t()`) та згадок мов у коді свідчить про підготовку до двомовності. Однак, відсутність файлів перекладів (`.po`) у `i18n/` є критичн

### [A-2] · TZ.md:68 · ТЗ заявляє: ✅
- Чому: Більшість закону підтверджено кодом, але доказ для account.payment відсутній — лише коментар.
- Доказ: models/participant.py:100 — _inherits = {"res.partner": "partner_id"} (учасники = camp.participant наслідує res.partner)
- Доказ: models/camp.py:664 — _inherit = "product.template" (табори = product.template)
- Доказ: models/camp.py:178 — _inherit = "event.event" (події = event.event)
- Доказ: models/camp.py:279 — camp_approval_state = fields.Selection(...) (approval-стан на native event.event)
- Доказ: models/budget.py:465 — MoveLine = self.env.get("account.move.line") (фактури = account.move)
- Доказ: models/commercial.py:19 — коментар про fayna.payment.installment ← CUSTOM (оплати: лише коментар, без коду)
- **Зробити:** Надати код, який підтверджує зв'язок з account.payment (наприклад, _inherit = "account.payment" або Many2one("account.payment") у custom-моделях)
- Чекер: підтверджено: Аналітик вірно визначив, що більшість пунктів вимоги підтверджені кодом (успадкування `res.partner`, `product.template`, `event.event`, використання `account.move.line`). Також правильно вказано на ві

### [A-4] · TZ.md:72 · ТЗ заявляє: ✅
- Чому: Основний патерн try/except реалізовано, але частина вимог щодо build-перевірок (py_compile, msgfmt, XML) відсутня в CI.
- Доказ: models/staffing.py:479-535 — try/except Exception з _logger.exception у 5 місцях, коментарі 'never block a sale/registration'
- Доказ: models/staffing.py:151-153 — try/except ValueError для обробки помилок
- Доказ: models/event_channel_create.py:135,147 — try/except Exception 'never block event creation/write'
- Доказ: models — 0 збігів NotImplementedError (заборонений патерн відсутній)
- Доказ: .github/workflows/ci.yml:21 — Lint (ruff + bandit + gitleaks + OCA) присутній
- Доказ: .github/workflows/ci.yml — 0 збігів py_compile/compileall, msgfmt/i18n
- **Зробити:** Додати в CI: py_compile/compileall, перевірку XML-well-formed, msgfmt для i18n, чистий -u-лог перед 'готово'
- Чекер: підтверджено: Аналітик коректно визначив статус 'PARTIAL', оскільки частина вимог (try/except, відсутність NotImplementedError, Lint-гейт) підтверджена, а частина (py_compile, XML-well-formed, msgfmt, чистий -u-лог

### [A-5] · TZ.md:74 · ТЗ заявляє: ✅
- Чому: Пункти 1-2 підтверджені, але пункти 3-4 не перевірені наявними пробами.
- Доказ: data/cron.xml:9 — CampScout у назві крон-задач (дозволено ТЗ: бренд лишити)
- Доказ: data/sms_templates.xml:21 — CampScout у SMS-рядках (дозволено ТЗ: бренд лишити)
- Доказ: data/budget_categories.xml:8 — noupdate=1, але це конфігурація, не бізнес-дані таборів
- Доказ: grep AGPL __manifest__.py — 0 збігів (пункт 1 виконано)
- Доказ: grep Wilcza|Ferie|Durdom|BS data/ — 0 збігів назв таборів (пункт 2 виконано)
- **Зробити:** Надати докази для пунктів (3) нуль copyleft copy-paste та (4) чисті межі модулів — grep-проби по ліцензійних заголовках файлів та перевірка імпортів між модулями
- Чекер: підтверджено: Аналітик коректно ідентифікував, що пункти (1) та (2) вимоги підтверджені наданими пробами, а пункти (3) та (4) потребують додаткових доказів, що виправдовує вердикт PARTIAL та сформований todo.

### [P-2] · TZ.md:84 · ТЗ заявляє: 🟡
- Чому: Основна вимога (OPL-1 у manifest, відсутність AGPL) виконана, але два модулі мають невідповідний LICENSE, а скрипт make-release.sh відсутній.
- Доказ: __manifest__.py:47 — "license": "OPL-1" знайдено в manifest
- Доказ: __manifest__.py — AGPL не знайдено (0 збігів)
- Доказ: LICENSE:1 — текст LICENSE містить "Odoo Proprietary License v1.0 (OPL-1)"
- Доказ: docs/TZ.md:84 — згадка про LGPL у fayna_rodo_compliance/LICENSE і fayna_sms_base/LICENSE (не перевірено в цьому репо)
- Доказ: DevJournal/scripts — make-release.sh не знайдено (0 збігів)
- **Зробити:** Перевірити та замінити LICENSE у fayna_rodo_compliance і fayna_sms_base на OPL-1 (чужі репо, потребує окремого ок); створити/перевірити make-release.sh; перевірити відсутність Co-Authored-By: Claude у нових комітах
- Чекер: підтверджено: Вердикт аналітика 'PARTIAL' точно відображає стан вимоги. Проби підтверджують наявність OPL-1 у manifest та відсутність AGPL, а також виявляють відсутність `make-release.sh`. Пункти `todo` коректно ох

### [P-3] · TZ.md:86 · ТЗ заявляє: 🔴
- Чому: Частково реалізовано роутинг за префіксом, але відсутні адаптери, provider_type, баланс — вимога не виконана повністю.
- Доказ: models/sms.py:3-5 — є routing та multi-provider routing (UA → TurboSMS, PL → secondary)
- Доказ: models/sms.py:38-48 — є модель fayna.sms.routing.rule (prefix → provider)
- Доказ: models/sms.py:92-97 — є dispatcher з routing через fayna.sms.routing.rule → fayna.sms.provider
- Доказ: models/sms.py:129-130 — є пошук active routing rule
- Доказ: grep 'provider_type' models — 0 збігів, немає розширення provider_type
- Доказ: grep 'class.*Provider.*Adapter|provider.*adapter' models — 0 збігів, немає класів-адаптерів
- **Зробити:** Створити абстрактний клас sms.provider.base (якщо відсутній), адаптери для SMSAPI.pl та SerwerSMS.pl, розширити provider_type, додати баланс per адаптер, тести з mock HTTP
- Чекер: підтверджено: Аналітик вірно визначив, що роутинг частково реалізовано, але ключові елементи вимоги 'доробити' — розширення `provider_type`, нові адаптери (SMSAPI.pl/SerwerSMS.pl) та баланс per адаптер — відсутні,

### [P-4] · TZ.md:88 · ТЗ заявляє: ✅
- Чому: Кастомні модулі підтверджено, але стандартні модулі з ТЗ не знайдено в __manifest__.py — можливо, вони вказані в іншому форматі або файлі.
- Доказ: __manifest__.py:63 — "fayna_rodo_compliance" присутній у залежностях
- Доказ: __manifest__.py:64 — "fayna_sms_base" присутній у залежностях
- Доказ: __manifest__.py — grep по fayna_sms_turbosms: 0 збігів (відсутній)
- Доказ: __manifest__.py — grep по стандартних модулях (base, mail, portal, website, website_sale, event, event_sale, sale, sale_management, account, loyalty, sms, website_rating): 0 збігів
- **Зробити:** Підтвердити наявність стандартних модулів (base, mail, portal, website, website_sale, event, event_sale, sale, sale_management, account, loyalty, sms, website_rating) у залежностях __manifest__.py — grep не знайшов жодного з них
- Чекер: підтверджено: Вердикт 'PARTIAL' є обґрунтованим, оскільки проби підтвердили наявність кастомних модулів та відсутність виключеного, але не змогли знайти стандартні модулі, що відповідає заявленому 'todo'.

### [R-2] · TZ.md:97 · ТЗ заявляє: ✅
- Чому: Core kiosk and login-as are implemented, but candidate-as-hr.applicant and volunteer role exclusion show no code evidence.
- Доказ: controllers/kiosk.py:230-236 — /camp/kiosk/layout route returns per-role tile grid
- Доказ: controllers/kiosk.py:262-267 — /camp/kiosk/toggle_visible route for Odoo toggle
- Доказ: controllers/admin.py:557-580 — /admin/login-as TRUE session switching with impersonator_uid
- Доказ: controllers/admin.py:631-655 — /admin/stop-impersonation fully reversible
- Доказ: tests/__init__.py:32 — test_role_instructor imported
- Доказ: models/recruitment.py — 0 matches for hr.applicant (candidate as native model NOT implemented)
- **Зробити:** Implement hr.applicant-based candidate model (currently 0 matches in models/recruitment.py); verify volunteer role exclusion in _role_taxonomy.py (0 matches for volunteer/волонтер)
- Чекер: підтверджено: Вердикт аналітика обґрунтований: основні елементи кіоску та функціонал 'login-as' підтверджені доказами. Відсутність реалізації кандидата на базі `hr.applicant` та непідтверджене виключення ролі волон

### [R-3] · TZ.md:99 · ТЗ заявляє: 🟡
- Чому: Правила для wychowawca і kierownik підтверджені, але відсутні правила для medyk, sprzedawca та батька (rodzic), що не відповідає повній піраміді видимості.
- Доказ: security/record_rules.xml:77 — wychowawca: domain_force [('group_id.wychowawca_ids', 'in', [user.id])] (своя група)
- Доказ: security/record_rules.xml:278 — wychowawca: [('wychowawca_ids', 'in', [user.id])] (своя група)
- Доказ: security/record_rules.xml:64 — kierownik: rule_participant_kierownik_own (весь табір)
- Доказ: security/record_rules.xml:288 — kierownik: rule_camp_group_kierownik_own (весь табір)
- Доказ: security/record_rules.xml:872 — NOTE: group_system (admin/organizator) bypasses all record rules (організатор = все)
- **Зробити:** Додати record rules для ролей medyk (art.9 всього табору) та sprzedawca (свої ліди/клієнти + каталог + заповнюваність). Перевірити наявність правила для батька (rodzic==user) — grep 'rodzic' дав 0 збігів.
- Чекер: підтверджено: Вердикт аналітика 'PARTIAL' та список 'todo' точно відображають відсутність правил для ролей 'батько', 'медик' та 'продавець', що підтверджується пробами. Докази для 'виховник', 'керівник' та 'організ

### [R-4] · TZ.md:101 · ТЗ заявляє: ✅
- Чому: Більшість ролей (батько, виховник, медик, керівник, організатор, продавець) покриті record rules + field groups + attachment-ACL, але доступ інструктора не підтверджено жодним доказом.
- Доказ: security/record_rules.xml:661 — record rules для camp.program.structured/day/line (ADR Фаза A)
- Доказ: security/record_rules.xml:862 — own record rules (own camp / own group / own children)
- Доказ: views/participant_views.xml:76 — Section II Medical restricted до group_medical_officer
- Доказ: views/participant_views.xml:93 — поле з groups=medical_officer,kierownik
- Доказ: models/art9_security.py:70-74 — ir.attachment ACL ховає PDF з медичними даними
- Доказ: models/art9_security.py:12 — згадка продавця/організатора в коментарі
- **Зробити:** Додати явні record rules або field groups для ролі інструктора (доступ до статусу та safety-флагів своїх занять) — зараз у art9_security.py немає жодного згадування instructor
- Чекер: підтверджено: Вердикт аналітика є обґрунтованим. Він точно ідентифікує відсутність доказів для ролі інструктора, що виправдовує статус 'PARTIAL' та вказаний 'todo'. Надані докази підтверджують використання record r

### [F-WIZ-2] · TZ.md:115 · ТЗ заявляє: ✅
- Чому: Кодова частина (валідація в action_next та action_create_camp) є, але вимога про умовний required у view не виконана.
- Доказ: wizards/camp_create_wizard.py:849 — _STEP_REQUIRED словник визначено
- Доказ: wizards/camp_create_wizard.py:857 — валідація за _STEP_REQUIRED у action_next
- Доказ: wizards/camp_create_wizard.py:855 — action_next існує
- Доказ: wizards/camp_create_wizard.py:674 — action_create_camp існує
- Доказ: views — 0 збігів required="step==..."
- **Зробити:** Додати умовний required="step=='...'" у view-шаблонах (зараз відсутній)
- Чекер: підтверджено: Вердикт аналітика 'PARTIAL' повністю відповідає наданим пробам. Кодова частина вимоги підтверджена, а відсутність 'required="step==..."' у view-шаблонах чітко зафіксована і винесена в 'todo'.

### [F-WIZ-4] · TZ.md:119 · ТЗ заявляє: ✅
- Чому: Код реалізує валідацію сну та генерацію кістяка, але відсутній підвечірок, що є частиною вимоги.
- Доказ: models/operations.py:1976 — метод _check_sleep_duration з валідацією нічної тиші
- Доказ: models/operations.py:1978-1987 — перевірка lights_out > wake_time та розрахунок сну ≥9 год
- Доказ: models/operations.py:2104 — метод _generate_skeleton для генерації кістяка
- Доказ: models/operations.py:2137-2178 — генерація сніданку, обіду, вечері, але НЕ підвечірку
- Доказ: tests/test_program_skeleton.py:48-67 — тести валідації сну ≥9 год
- Доказ: tests/test_program_skeleton.py:71-80 — тести генерації кістяка на 7 днів
- **Зробити:** Додати генерацію 'підвечірку' (afternoon snack) у метод _generate_skeleton, оскільки зараз генеруються лише сніданок, обід та вечеря.
- Чекер: підтверджено: Аналітик вірно ідентифікував усі реалізовані частини вимоги, включаючи валідацію сну, генерацію кістяка, сніданку, обіду, вечері, підйому/відбою та вільних годин. Також коректно виявлено відсутність г

### [F-WIZ-5] · TZ.md:121 · ТЗ заявляє: ✅
- Чому: Код реалізує ліміти груп (20/15/2) та round-robin для wychowawcy, але відсутній доказ round-robin поділу дітей при резервації.
- Доказ: models/camp_group.py:40 — docstring: max 20 children (15 when any child is <10)
- Доказ: models/camp_group.py:504-531 — capacity limit 15/20 logic
- Доказ: models/camp_group.py:539,596 — disabled count limit ≤2
- Доказ: models/camp_group.py:329,334 — round-robin assignment of wychowawcy to groups (not children)
- Доказ: tests/test_camp_group.py:79,83 — tests for capacity 20 and 21st raises
- Доказ: tests/test_phase_d_split.py:5 — tests for <10 never in group-20, reserve, promotion, round-robin wychowawcy
- **Зробити:** Реалізувати round-robin поділ саме дітей при резервації (авто-групи N=ceil(seats/20) з round-robin розподілом дітей по групах), а не лише призначення wychowawcy. Додати тести, що підтверджують round-robin розподіл дітей.
- Чекер: підтверджено: Проби підтверджують реалізацію лімітів груп (20/15/2) та round-robin для вихователів. Відсутність доказів round-robin поділу дітей при резервації та автоматичного створення N=ceil(seats/20) груп повні

### [F-WIZ-6] · TZ.md:123 · ТЗ заявляє: ✅
- Чому: Каталог форм додано в обидва Selection, але заявлений повний функціонал не виконано через втрату значення у action_create_camp (R6.1).
- Доказ: wizards/camp_create_wizard.py:91-92 — додано polkolonia та zielona_szkola у Selection vacation_form
- Доказ: models/operations.py:3378-3379 — додано polkolonia та zielona_szkola у Selection vacation_form
- Доказ: wizards/camp_create_wizard.py:696 — vacation_form передається у створення події
- Доказ: models/operations.py:3402-3412 — onchange синхронізує event.vacation_form з полем форми
- Доказ: tests/__init__.py:46 — тест test_vacation_forms підключено
- **Зробити:** Виправити R6.1: у action_create_camp перенести обране vacation_form у відповідне місце (наприклад, у event або notification), щоб значення не губилося і kuratorium notification створювався з правильним типом форми
- Чекер: підтверджено: Проби підтверджують додавання необхідних форм до обох Selection полів, що відповідає частині вимоги про 'повний перелік MEN'. Аналітик коректно ідентифікував функціональну проблему (R6.1) та позначив

### [F-WIZ-8] · TZ.md:127 · ТЗ заявляє: 🟡
- Чому: Підтверджено лише image_1920 та alt-атрибути; крок фото у wizard, product.image та og:image не верифіковані.
- Доказ: wizards/camp_create_wizard.py:122 — logo_image = fields.Image(...) — контейнерне поле для фото у wizard
- Доказ: wizards/camp_create_wizard.py:760-762 — Logo → product.template.image_1920 при наявності camp_program_id
- Доказ: templates/portal_camp_day.xml:127 — t-att-alt для фото у шаблоні
- Доказ: templates/portal_templates.xml:139 — t-attf-alt для зображень
- **Зробити:** Перевірити наявність кроку «Фото» у wizard (окремий крок каскаду) та наявність product.image (галерея) та og:image/website meta — у пробах не знайдено
- Чекер: підтверджено: Вердикт 'PARTIAL' обґрунтований. Докази підтверджують наявність `image_1920` та `alt` атрибутів, а `todo` чітко вказує на відсутні елементи вимоги: крок 'Фото' у wizard, `product.image` (галерея) та `

### [F-PRG-1] · TZ.md:133 · ТЗ заявляє: ✅
- Чому: Код підтверджує наявність поля та блокування запису виховника, але немає доказів, що саме керівник може встановлювати is_locked.
- Доказ: models/operations.py:2539 — is_locked = fields.Boolean(...)
- Доказ: models/operations.py:2614 — if line.is_locked or line.owner_role == "kierownik": (блокування для виховника)
- Доказ: tests/test_phase_c_wychowawca.py:175 — тест на блокування запису виховника на locked
- **Зробити:** Додати/підтвердити обмеження, що is_locked може встановлювати лише керівник (наприклад, перевірка owner_role при set, окремий метод або constraint).
- Чекер: підтверджено: Вердикт аналітика обґрунтований: наявність поля та логіка блокування для виховника підтверджені, а відсутність доказів щодо встановлення `is_locked` лише керівником чітко зазначена як `todo`.

### [F-PRG-2] · TZ.md:135 · ТЗ заявляє: 🟡
- Чому: Логіка та UI-поля is_rain_plan реалізовані, але рендер на картці товару відсутній у шаблонах (0 збігів), що відповідає заявленому 🟡 статусу.
- Доказ: models/camp.py:391 — is_rain_plan=False у фільтрі пошуку Plan A
- Доказ: models/camp.py:455 — фільтрація програм за is_rain_plan
- Доказ: models/operations.py:1905 — поле is_rain_plan Boolean
- Доказ: models/operations.py:1998 — суфікс '(Rain Plan)' у відображенні
- Доказ: wizards/camp_create_wizard.py:911,922 — створення записів з is_rain_plan=False/True
- Доказ: views/operations_views.xml:628, views/program_views.xml:16,47,233 — поле у формах
- **Зробити:** Додати рендер обох програм (звичайної та дощової) на картці товару у шаблонах
- Чекер: підтверджено: Вердикт аналітика 'PARTIAL' повністю відповідає наданим доказам. Логіка та UI-поля 'is_rain_plan' реалізовані, що підтверджується численними збігами у моделях, операціях та візардах. Однак, відсутніст

### [F-REC-2] · TZ.md:149 · ТЗ заявляє: ✅
- Чому: Гейт і blurred-механіка реалізовані, але відсутні ключові елементи флоу (стани staff та кнопка допуску), тому вимога виконана частково.
- Доказ: models/operations.py:231 — метод _check_rspts_before_admission існує (гейт §13)
- Доказ: controllers/recruitment_portal.py:155-174 — blurred-механіка для pending_admission реалізована
- Доказ: controllers/recruitment_portal.py:250 — KRK upload присутній
- Доказ: controllers/recruitment_portal.py:279 — admission gate перевіряє KRK/RSPTS
- Доказ: models/staffing.py — немає збігів на 'staff=active' або 'staff=draft' (стани не знайдено)
- Доказ: controllers/recruitment_portal.py — немає збігів на 'ДОПУСК' (кнопка не знайдена)
- **Зробити:** 1) Додати стани staff=draft/staff=active у models/staffing.py; 2) Додати кнопку «ДОПУСК» у recruitment_portal.py; 3) Додати Playwright-крок для blurred-UX e2e-скріна (як зазначено в ТЗ)
- Чекер: підтверджено: Аналітик коректно визначив наявні та відсутні елементи вимоги на основі наданих проб. Вердикт 'PARTIAL' та перелік 'todo' обґрунтовані.

### [F-REC-4] · TZ.md:153 · ТЗ заявляє: 🟡
- Чому: Код має лише базовий опис, але відсутні ставки, поля вимог та механізм overstaffing — частково реалізовано.
- Доказ: models/recruitment.py:26 — _description = "Camp staff application" (опис є, але не поля description/requirements)
- Доказ: models/staffing.py:284 — згадка overstaffing лише як spam-guard повідомлення, не як прапорець рішення людини
- Доказ: models/recruitment.py — 0 збігів для wychowawca/kierownik/instruktor, rate/stawka/salary, hr.job
- **Зробити:** Додати поля description/requirements та ставку (rate) до моделі вакансії (hr.job); реалізувати прапорець overstaffing як рішення людини при скасуванні реєстрацій; перевірити ставки в калькуляторі
- Чекер: підтверджено: Вердикт аналітика 'PARTIAL' повністю підтверджується наданими пробами, які показують відсутність ключових елементів вимоги (ставок, полів вимог, функціоналу overstaffing) та наявність лише базового оп

### [F-KKW-1] · TZ.md:159 · ТЗ заявляє: ✅
- Чому: Частково реалізовано: wzor_version, більшість pkt9 полів, PESEL checksum, fn_* поля, але відсутні деякі поля та emergency contacts.
- Доказ: models/participant.py:285 — wzor_version field exists (Selection)
- Доказ: models/participant.py:300-364 — allergy_meds, allergy_pollen, allergy_food, allergy_insect_venom, motion_sickness, orthodontic_appliance, wears_glasses, wears_contact_lenses, diet_vegetarian, emotional_expression_issues, group_functioning_issues fields exist
- Доказ: models/participant.py:1400-1408 — _check_pesel_validity with regex and checksum validation
- Доказ: models/participant.py:900-1029 — fn_* proxy fields exist (fn_client_consent, fn_parents_signature, fn_event_product_id, etc.)
- Доказ: tests/test_karta_2026.py:43-60 — test_default_wzor_is_2026 and test_pkt9_fields_store verify wzor_version and pkt9 fields
- **Зробити:** Додати поля: permanent_meds, chronic_diseases, diet_lowcal, fear_of_heights, hydrophobia, vacc_diphtheria_year, vacc_other (не знайдені в пробах). Додати emergency contacts (2 набори + relation) — не знайдено в пробах. Перевірити наявність тестів test_karta_pdf.py.
- Чекер: підтверджено: Аналітик коректно визначив часткову реалізацію вимоги, вказавши на наявність wzor_version, більшості полів pkt 9, fn_* полів та PESEL-валідації. Також чітко перелічені відсутні поля pkt 9, emergency c

### [F-KKW-3] · TZ.md:163 · ТЗ заявляє: 🟡
- Чому: Механізми 1-2 частково підтверджені (immutable PDF через protected fields + append-only журнал), але HMAC і user-agent відсутні, хеш PDF не підтверджено.
- Доказ: models/participant.py:509-557 — qualification_signed, qualification_signed_date, qualification_signed_ip, qualification_signed_by, qualification_signature, qualification_signed_by_name — фіксація timestamp, IP, хто, але немає user-agent
- Доказ: models/participant.py:14-15 — protected fields + amendment flow (new signed record + archive) — механізм amendment-copy підтверджено
- Доказ: models/participant.py:542 — поле 'Link to the RODO consent log entry created at signing' — вказує на consent log, але сам журнал не знайдено в models
- Доказ: models/sms.py:11,34 — hashlib використовується тільки для SMS-нормалізації, не для хешу PDF
- Доказ: tests/test_rodo_consent_immutable.py:40-77 — тести підтверджують append-only write() guard, але не HMAC і не user-agent
- **Зробити:** 1) Додати HMAC до append-only журналу fayna_rodo_consent_log (модель не знайдена в models/ — можливо в іншому модулі). 2) Додати поле user-agent при фіксації підпису. 3) Додати поле signed_pdf_hash + запис хешу PDF у момент підпису (мех.3).
- Чекер: підтверджено: Вердикт аналітика 'PARTIAL' обґрунтований. Проби підтверджують відсутність `fayna_rodo_consent_log` моделі, HMAC, хешу PDF та user-agent при фіксації підпису, що відповідає вимозі. Механізм amendment-

### [F-KKW-4] · TZ.md:165 · ТЗ заявляє: 🟡
- Чому: Constraint реалізовано в коді (models/operations.py:2980-3006), але відсутній тест, що підтверджує його роботу, тому статус 🟡 відповідає дійсності.
- Доказ: models/operations.py:2980 — @api.constrains("risk_water", "risk_heights", "dziennik_id") — constraint існує
- Доказ: models/operations.py:2992 — blocked = participants.filtered("hydrophobia") — блокування для hydrophobia
- Доказ: models/operations.py:3004 — blocked = participants.filtered("fear_of_heights") — блокування для fear_of_heights
- Доказ: models/operations.py:2994 — raise ValidationError(...) — кидається ValidationError при блокуванні
- Доказ: models/operations.py:3006 — raise ValidationError(...) — кидається ValidationError при блокуванні
- **Зробити:** Додати автоматизований тест, який перевіряє, що запис учасника з hydrophobia/fear_of_heights у водні/висотні заняття викликає ValidationError
- Чекер: підтверджено: Докази (models/operations.py:2980-3006) чітко показують наявність @api.constrains, перевірку на 'hydrophobia'/'fear_of_heights' та викидання ValidationError, що повністю відповідає вимозі. Запропонова

### [F-KKW-5] · TZ.md:167 · ТЗ заявляє: ✅
- Чому: Основна функціональність згод (4a/4b) реалізована з toggle та логуванням, але HTML-тексти розміщені не на res.company, відсутня роздільність двох цілей фото, і RODO-лог не знайдено.
- Доказ: models/participant.py:833 — image_consent_state Selection поле (Dodatek 4a)
- Доказ: models/participant.py:874 — marketing_consent Boolean поле (Dodatek 4b)
- Доказ: models/participant.py:1915 — sign_image_consent() з RODO-логом (рядок 1940)
- Доказ: models/participant.py:1963 — update_marketing_consent() toggle з RODO-логом (рядок 1982)
- Доказ: models/participant.py:2393 — image_consent_body Html поле, але в participant.py, не res.company
- Доказ: models/participant.py:2402 — marketing_consent_body Html поле, але в participant.py, не res.company
- **Зробити:** 1) Перенести/додати поля image_consent_body та marketing_consent_body на res.company (зараз на participant). 2) Додати окремі згоди для внутрішнього показу vs публічного маркетингу (зараз лише один image_consent_state). 3) Перевірити наявність RODO-log моделі (grep 'rodo_log' не дав збігів).
- Чекер: підтверджено: Аналітик коректно визначив статус 'PARTIAL', оскільки основні механізми згод 4a та 4b реалізовані, але є чіткі невідповідності вимозі щодо розрізнення цілей фото, розміщення HTML-текстів згод на res.c

### [F-KKW-6] · TZ.md:169 · ТЗ заявляє: 🟡
- Чому: Cron, логіка скасування та RODO-поля присутні, але тест відсутній, а refund залишається заглушкою — відповідає заявленому 🟡 з залишком 🔴.
- Доказ: data/cron.xml:8 — cron_auto_refusal_unsigned існує (щоденний ir.cron)
- Доказ: models/participant.py:1668 — _schedule_refund визначено
- Доказ: models/participant.py:1707 — _schedule_refund викликається в auto-refusal логіці
- Доказ: models/participant.py:1102 — auto_refusal_refused_at поле існує
- Доказ: models/participant.py:1705 — auto_refusal_refused_at встановлюється
- Доказ: models/participant.py:1748 — фільтр по auto_refusal_refused_at = False (пошук непідписаних)
- **Зробити:** Створити тест test_auto_refusal_cron (згаданий у ТЗ як верифікований 04.07, але файл відсутній). Реалізувати реальний refund-механізм замість заглушки _schedule_refund (лише логує).
- Чекер: підтверджено: Вердикт аналітика точно відображає статус вимоги: cron та логіка скасування присутні, але тест, який мав би це верифікувати, відсутній, а механізм refund є заглушкою, що відповідає заявленому 🟡 з зали

### [F-KKW-7] · TZ.md:171 · ТЗ заявляє: 🔴
- Чому: Код частково використовує дані компанії (підпис), але повноцінного фірмового еталона з брендом/лого/реквізитами не знайдено.
- Доказ: reports/karta_report_templates.xml:274-275 — використовується підпис компанії (camp_organizer_signature), але не бренд/лого/реквізити
- Доказ: reports/karta_report_templates.xml:405-406 — те саме: лише підпис, без фірмового стилю
- Доказ: views/res_company_views.xml:6-13 — є модель res.company з полем підпису, але не знайдено QWeb-стилізації для еталона
- Доказ: grep karta_report: 0 збігів у reports — окремого файлу karta_report немає
- **Зробити:** Додати QWeb-стилізацію для фірмового еталона (бренд/лого/реквізити) у karta_report_templates.xml; перевірити наявність конфігурації res.company на staging
- Чекер: підтверджено: Вердикт аналітика обґрунтований: проби показують використання лише підпису компанії (`camp_organizer_signature`), але не повного бренду, лого чи реквізитів, як вимагає ТЗ. Відсутність збігів для 'logo

### [F-RODO-2] · TZ.md:179 · ТЗ заявляє: 🟡
- Чому: Record rule на ir.attachment існує, але тест HTTP-ізоляції, який є критерієм приймання, відсутній у репозиторії
- Доказ: security/record_rules.xml:886 — record rule `rule_attachment_participant_medical_write` існує
- Доказ: security/record_rules.xml:890 — domain_force на res_model='camp.participant'
- Доказ: models/art9_security.py:70 — _inherit = 'ir.attachment'
- Доказ: tests/test_art9_http_isolation.py — файл відсутній (0 збігів на grep)
- **Зробити:** Створити тест test_art9_http_isolation.py, який симулює прямий URL /web/content/<id> для karta-PDF чужим користувачем (бухгалтер/чужий батько) і перевіряє 0 успішних спроб; підтвердити, що record rule на ir.attachment реально блокує HTTP-доступ
- Чекер: підтверджено: Вердикт аналітика точно відображає стан вимоги: record rule існує, але критичний тест `test_art9_http_isolation.py`, який є критерієм приймання, відсутній, що підтверджується пробами. Запропоноване to

### [F-RODO-3] · TZ.md:181 · ТЗ заявляє: ✅
- Чому: Код містить declaracja/RSTPO, але тест на блокування відсутній, тому вимога виконана частково.
- Доказ: models/operations.py:302 — коментар про самопідписану декларацію RSTPO
- Доказ: models/operations.py:3749 — згадка RSTPO як mandatory per Ustawa Kamilka
- Доказ: views/operations_views.xml:34-42 — §13 gate з confirm про declaracja
- Доказ: tests: 0 збігів declaracja|RSTPO — тесту на блокування немає
- **Зробити:** Додати тест, що без підтвердженої declaracji доступ до карток заблоковано (обидві гілки: до і після підтвердження), згідно з критерієм EARS.
- Чекер: підтверджено: Докази аналітика чітко вказують на наявність згаданих у вимозі концепцій ('declaracja', 'RSTPO', '§13 gate') у коді, а також підтверджують відсутність тесту на блокування, що відповідає заявленому 'PA

### [F-RODO-6] · TZ.md:187 · ТЗ заявляє: 🔴
- Чому: QWeb-звіти та consent_log реалізовані, але відсутня кнопка в UI, XLSX-формат і фільтри, тому вимога виконана частково.
- Доказ: reports/escort_rodo_report_templates.xml:13 — QWeb шаблони RODO-звітів (escort_data, medical_consent, escort_person)
- Доказ: reports/escort_rodo_reports.xml:8 — ir.actions.report для RODO-звітів
- Доказ: models/participant.py:1542 — використання consent_log для запису згоди
- Доказ: reports/budget_reports.xml:3 — XLSX замінено на PDF QWeb, XLSX-звітів немає
- Доказ: templates — кнопка «Завантажити RODO-звіт» не знайдена
- **Зробити:** Додати кнопку «Завантажити RODO-звіт» для organizator; реалізувати XLSX-формат (зараз лише PDF); додати фільтри per-partner/per-camp/дата
- Чекер: підтверджено: Аналітик вірно визначив статус PARTIAL, оскільки QWeb-звіти та використання consent_log підтверджені, але відсутність кнопки в UI, XLSX-формату та фільтрів чітко доведена пробами.

### [F-KAM-1] · TZ.md:195 · ТЗ заявляє: ✅
- Чому: Ескалація, резервний контакт і immutable log реалізовані, але вимога про SMS всім subscribers навіть при opt-out не підтверджена кодом — grep по opt-out дав 0 збігів.
- Доказ: models/incident_kamilka.py:42 — severity='kamilka' selection_add
- Доказ: models/incident_kamilka.py:109-155 — _cron_kamilka_escalate: 5-min escalation, backup_partner, SMS template
- Доказ: models/incident_kamilka.py:166-167 — _kamilka_pick_backup_partner: deputy_kierownik > organizator
- Доказ: models/incident_notification_log.py:6,26,106 — immutable notification log for Kuratorium
- Доказ: data/cron_kamilka_escalation.xml:13-17 — ir.cron calling model._cron_kamilka_escalate()
- **Зробити:** SMS на ВСІХ subscribers навіть при opt-out — у коді немає жодного згадування opt-out/opt_out/optout (grep: 0 збігів у incident_kamilka.py). Потрібно додати логіку, яка ігнорує opt-out для severity='kamilka' (GDPR art.6.1.d).
- Чекер: підтверджено: Аналітик вірно визначив вердикт 'PARTIAL' та обґрунтував 'todo' пункт. Проба на 'opt-out' дійсно не виявила збігів у `incident_kamilka.py`, що підтверджує відсутність логіки ігнорування відмови від ро

### [F-KAM-2] · TZ.md:197 · ТЗ заявляє: ✅
- Чому: Підтверджено лише рендер 16 пунктів карти з opis, але реєстр §12 (колонки, агрегація, Lp., immutable, PDF) не верифіковано.
- Доказ: models/incident_card.py:263 — поле opis_wypadku існує
- Доказ: models/incident_card.py:428 — гейт перевірки opis_wypadku в action_confirm
- Доказ: reports/incident_report_templates.xml:17 — шаблон report_incident_card_document існує
- Доказ: tests/test_incident_card.py:274 — тест 16 пунктів з opis
- Доказ: tests/test_incident_card.py:297 — тест рендеру opis у реєстрі
- **Зробити:** Надати докази для: 10 колонок реєстру, авто-агрегації, Lp., immutable після закриття турнусу, PDF для KO — жоден із цих аспектів не підтверджено пробами
- Чекер: підтверджено: Докази підтверджують заявлені аналітиком частини вимоги щодо Karta Wypadku (§11), а список TODO коректно визначає непідтверджені аспекти Rejestr Wypadków (§12).

### [F-KAM-3] · TZ.md:199 · ТЗ заявляє: 🟡
- Чому: Механізм sla_breaches і бейдж реалізовані, але відсутні тести та не підтверджено окремі computed-поля для всіх часових інтервалів SLA.
- Доказ: models/emergency.py:265 — sla_breaches = fields.Char( — поле існує
- Доказ: models/emergency.py:492 — rec.sla_breaches = ",".join(breaches) — заповнення списком порушень
- Доказ: models/emergency.py:908-926 — incident_sla_breach_count computed поле з підрахунком
- Доказ: views/emergency_views.xml:13 — decoration-danger з sla_breaches != '' — червоний бейдж у списку
- Доказ: views/emergency_views.xml:150 — фільтр SLA Breaches
- Доказ: tests/ — 0 збігів sla_ — тестів немає
- **Зробити:** Додати тести для SLA-розрахунку; перевірити наявність computed полів для кожного часового інтервалу (0-10с, 0-2хв, 2-15хв, 15-30хв, 30хв-24г, 24г-7д, 7-21д) — grep не знайшов sla_0_10, sla_2_15 тощо
- Чекер: підтверджено: Вердикт аналітика 'PARTIAL' точно відображає стан: механізм `sla_breaches` та візуальний індикатор (червоний бейдж) присутні, але відсутні окремі `computed booleans` для кожного часового інтервалу SLA

### [F-KSK-1] · TZ.md:204 · ТЗ заявляє: ✅
- Чому: Ядро кіоску (layout, toggle, back, set_lang) підтверджено, але відсутні докази для kiosk_app.js/kiosk_template.xml та login-as функціоналу організатора.
- Доказ: controllers/kiosk.py:230-235 — /camp/kiosk/layout endpoint exists and returns per-role tile grid
- Доказ: controllers/kiosk.py:262-267 — /camp/kiosk/toggle_visible endpoint exists (toggle «↔ Odoo»)
- Доказ: controllers/kiosk.py:279-284 — /camp/kiosk/back_visible endpoint exists (back to fullscreen kiosk)
- Доказ: controllers/kiosk.py:299-304 — /camp/kiosk/set_lang endpoint exists (PL/UA switcher)
- Доказ: static/src/js/kiosk_odoo_toggle_systray.js:53 — OWL systray toggle component exists
- Доказ: controllers/kiosk.py:250-258 — role check: non-kiosk users get error message
- **Зробити:** Перевірити: (1) kiosk_app.js та kiosk_template.xml — файли не знайдено за вказаними шляхами (можливо інші назви/шляхи); (2) login-as/impersonation для організатора — не знайдено в controllers/kiosk.py; (3) організаторський dashboard-redirect (commit 093cab4) — не підтверджено в пробах
- Чекер: підтверджено: Аналітик вірно визначив статус 'PARTIAL', оскільки ключові компоненти ядра (`kiosk_app.js`, `kiosk_template.xml`) та функціонал `login-as` для організатора, згадані у вимозі, не підтверджені пробами.

### [F-KSK-2] · TZ.md:206 · ТЗ заявляє: 🟡
- Чому: R4 та R4b підтверджені кодом, але R5-R9 та беклог §18.4 не мають жодних доказів у репозиторії.
- Доказ: static/src/xml/kiosk_template.xml:67 — row-cols-lg-3 g-3 g-md-4 w-100 (R4 сітка 3×3 присутня)
- Доказ: static/src/scss/kiosk.scss:85-89 — max-width: 960px з телефонним override (R4 max-width 960 по центру)
- Доказ: static/src/xml/kiosk_template.xml:18 — коментар про перенесення langbar з position-absolute (R4b виправлення)
- Доказ: static/src/xml/kiosk_template.xml:0 збігів — CampScout (R5 бренд відсутній)
- Доказ: static/src/xml/kiosk_template.xml:0 збігів — BEP/marże/Teczka KO/Raport §2.11 (R7 мікрокопі відсутні)
- Доказ: static/src/xml/kiosk_template.xml:0 збігів — Nowy obóz (R8 головний CTA відсутній)
- **Зробити:** Додати: (1) лого CampScout у header (R5); (2) мікрокопі для BEP/marże, Teczka KO, Raport §2.11 (R7); (3) акцент лише на Nowy obóz + палітра (R8); (4) заголовок з user/event context + бейджі (R9); (5) беклог 14-TZ §18.4: '← Powrót do kiosku', селектор табору, full-width поля форм.
- Чекер: підтверджено: Вердикт аналітика повністю відповідає наданим пробам та вимогам. Підтверджені пункти (R4, R4b) мають відповідні збіги, а відсутні (R5, R7, R8) — нульові збіги, що коректно інтерпретовано. Список todo

### [F-KSK-4] · TZ.md:217 · ТЗ заявляє: 🟡
- Чому: Частина вимоги (Kuratorium, sanepid, PSP, нагадування) реалізована, але ключовий елемент 🟡 — hr_recruitment stages — відсутній, тому 🟡 не досягнуто.
- Доказ: models/staffing.py:6 — коментар: 'camp.staff.vacancy — легка внутрішня модель вакансії (R13: БЕЗ hr_recruitment)' — прямо вказує на відсутність hr_recruitment.
- Доказ: models/recruitment.py:246 — згадка '[recruitment] Could not send portal invite' — існує якась recruitment-логіка, але без 'stage'.
- Доказ: models/recruitment.py — grep 'stage' дав 0 збігів — немає стадій найму (hr_recruitment stages).
- Доказ: models/operations.py:3279 — клас CampKuratoriumNotification (Zgłoszenie Wypoczynku) — трекер Kuratorium присутній.
- Доказ: models/operations.py:3657 — клас KuratoriumChecklist — чекліст Kuratorium присутній.
- Доказ: models/operations.py:600 — ('sanepid', 'Zaświadczenie sanepid') — sanepid присутній.
- **Зробити:** Додати hr_recruitment stages (модель стадій найму) та консолідований трекер-вигляд для кабінету керівника (KRK, співбесіди, наповнення дітьми) з нагадуваннями.
- Чекер: підтверджено: Аналітик вірно ідентифікував, що ключовий елемент `hr_recruitment stages` для досягнення `🟡` відсутній, що підтверджується відсутністю збігів `stage` у `recruitment.py` та коментарем `БЕЗ hr_recruitme

### [F-MY-2] · TZ.md:225 · ТЗ заявляє: ✅
- Чому: PL-версія підтверджена для 6 з 7 пунктів, але 'Lojalność' не має структурного доказу, а UA-версія заявлена як незавершена.
- Доказ: templates/portal_templates.xml:225 — Karta dziecka присутній у шаблоні
- Доказ: templates/portal_templates.xml:237 — Płatności i faktury присутній у шаблоні
- Доказ: templates/portal_templates.xml:249 — Wiadomości присутній у шаблоні
- Доказ: templates/portal_templates.xml:261 — Dokumenty / Zgody присутній у шаблоні
- Доказ: templates/portal_templates.xml:276 — Zarezerwuj obóz присутній у шаблоні
- Доказ: templates/portal_templates.xml:427 — portal_stories (Stories) присутній у шаблоні
- **Зробити:** 1) Додати доказ присутності 'Lojalność' у templates/portal_templates.xml (або підтвердити його відсутність); 2) UA-версія заявлена як після merge R2 — перевірити чи merge відбувся
- Чекер: підтверджено: Аналітик вірно визначив статус 'PARTIAL', оскільки, незважаючи на заявлену '✅ PL-версію' у вимозі, відсутній структурний доказ для 'Lojalność' у шаблонах. Також коректно відзначено статус UA-версії та

### [F-MY-3] · TZ.md:227 · ТЗ заявляє: 🟡
- Чому: Record-rule видимість виховника підтверджена тестами, але сам блок у батьківському кабінеті не знайдено в коді.
- Доказ: security/record_rules.xml:77 — rule_participant_wychowawca_own: wychowawca sees participants where user.id in group_id.wychowawca_ids
- Доказ: security/record_rules.xml:278 — rule_camp_group_wychowawca_own: wychowawca sees own camp groups
- Доказ: tests/test_phase_d_split.py:316-364 — test_d4_wychowawca_sees_art9_own_children verifies wychowawca visibility of own children
- Доказ: templates/portal_templates.xml:71 — portal template shows 'Panel wychowawcy' for wychowawca group
- **Зробити:** Немає доказів, що блок «Twój wychowawca» відображається у /my для батька. Потрібен скрін кабінету батька з призначеним виховником.
- Чекер: підтверджено: Вердикт 'PARTIAL' та 'todo' аналітика є коректними. Надані докази підтверджують видимість дітей для виховника ('навпаки'), але відсутні докази відображення блоку 'Twój wychowawca' у кабінеті батька, щ

### [F-MY-4] · TZ.md:229 · ТЗ заявляє: 🟡
- Чому: Public-зріз daily.report реалізовано (whitelist + рендер), але мобільний upload з камери не знайдено в коді, що відповідає заявленому 🟡 статусу.
- Доказ: controllers/portal.py:27 — whitelist of camp.daily.report fields exposed to parents
- Доказ: controllers/portal.py:170 — search_count on camp.daily.report
- Доказ: controllers/portal.py:526 — camp.daily.report only CAMP_DAY_PUBLIC_REPORT_FIELDS
- Доказ: controllers/portal.py:555 — search on camp.daily.report
- Доказ: templates/portal_camp_day.xml:8 — daily.report whitelist as plain dicts
- Доказ: tests/__init__.py:44 — test_story_photo_consent_gate registered
- **Зробити:** Перевірити/додати мобільний upload фото з capture=camera (у templates/portal_camp_day.xml збігів немає); верифікувати портальний рендер daily.report на практиці
- Чекер: підтверджено: Вердикт аналітика точно відповідає заявленому статусу `🟡` у вимозі. Надані докази підтверджують реалізацію public-зрізу `daily.report` та наявність `consent-gate` для stories, а відсутність збігів для

### [F-MY-5] · TZ.md:231 · ТЗ заявляє: 🟡
- Чому: Поля opt-in існують і поважаються SMS-системою, але UI для їх зміни відсутній — вимога виконана частково.
- Доказ: models/res_partner_inherit.py:25 — sms_opt_in Boolean поле існує
- Доказ: models/res_partner_inherit.py:34 — sms_opt_in_marketing Boolean поле існує
- Доказ: models/sms_notify.py:89 — фільтрація по sms_opt_in перед відправкою
- Доказ: controllers: 0 збігів /my/preferences — сторінки немає
- Доказ: templates: 0 збігів preferences — UI немає
- **Зробити:** Додати блок налаштувань SMS у /my/account або consents (контролер + шаблон), щоб батько міг перемкнути sms_opt_in/sms_opt_in_marketing
- Чекер: підтверджено: Вердикт аналітика точно відображає стан: поля opt-in існують і використовуються, але UI для їх налаштування відсутній, що підтверджується відсутністю збігів у контролерах та шаблонах. Todo чітко вказу

### [F-COM-1] · TZ.md:237 · ТЗ заявляє: ✅
- Чому: Основна функціональність (поля, шаблони, нотифікації, wizard) реалізована, але тест cost-guard відсутній.
- Доказ: models/participant_sms_extension.py:20 — child_mobile field exists
- Доказ: models/participant_sms_extension.py:27 — sms_consent field exists (RODO art.7)
- Доказ: models/sms_notify.py:83 — sms_notify with priority and opt-in bypass logic
- Доказ: models/sms_notify.py:226 — dispatched SMS template logging
- Доказ: data/sms_child_templates.xml:13-43 — templates for Збір/Підйом/Відбій/НЕГАЙНО (Kamilka)
- Доказ: data/cron_kamilka_escalation.xml:14 — 5-minute Kamilka escalation cron
- **Зробити:** Додати прямий тест SMS cost-guard (заявлено в TZ.md §5 як прогалина, тестів не знайдено)
- Чекер: підтверджено: Аналітик коректно ідентифікував наявність всіх ключових функціональних елементів вимоги (поля, шаблони, логіка пріоритетів/згоди, wizard) та обґрунтував вердикт `PARTIAL` через відсутність прямого тес

### [F-COM-2] · TZ.md:239 · ТЗ заявляє: 🟡
- Чому: Wizard, immutable-лог і retention 7y підтверджені, але ліміти (ir.config_parameter), тест на ліміт і місячний звіт у дашборді відсутні в коді.
- Доказ: models/staff_sms_log.py:17 — _name = "camp.staff.sms.log" (модель існує)
- Доказ: models/staff_sms_log.py:91 — raise UserError(_("SMS log is immutable (audit retention 7y).")) (immutable + retention 7y)
- Доказ: wizards/staff_sms_composer.py:73-79 — Recipients (preview) + recipient_count поле
- Доказ: wizards/staff_sms_composer.py:120 — cost_estimate_pln = (wiz.recipient_count or 0) * cost_per_segment (cost preview)
- Доказ: models/staff_sms_log.py:7 — 7-year retention enforced at model layer
- **Зробити:** 1) Додати тест на ліміт 100/300 SMS (ir.config_parameter) — заявлено 🟡. 2) Додати місячний звіт у дашборді — проби не знайшли жодних доказів (grep monthly|report|dashboard = 0 збігів). 3) Перевірити наявність лімітів 100/300 та cost 0.05 — grep ir.config_parameter та 100|300|0.05 = 0 збігів.
- Чекер: підтверджено: Вердикт аналітика повністю відповідає наданим пробам та вимозі. Всі підтверджені пункти мають відповідні збіги в пробах, а всі заявлені 'todo' пункти дійсно не знайшли підтвердження в пробах, що випра

### [F-COM-3] · TZ.md:241 · ТЗ заявляє: 🟡
- Чому: Канал з kierownik+staff створюється і є приватним, але архівація через 30 днів відсутня в коді, а story-модель явно винесена в інший addon.
- Доказ: models/event_channel_create.py:76-77 — _create_camp_discuss_channel creates one discuss.channel per event missing one
- Доказ: models/event_channel_create.py:55 — collects partner ids of (kierownik + staff) for one shift
- Доказ: models/event_channel_create.py:6 — sync a private group chat in Discuss containing the kierownik plus every staff
- Доказ: models/event_channel_create.py:12 — channel_type='group' = private multi-user chat
- Доказ: models/auto_subscribe_extensions.py:38-39,57-58,83-84,140-141,162-163 — five models override _message_auto_subscribe_followers
- Доказ: models/auto_subscribe_extensions.py:81 — _inherit = "camp.incident.report" (incident model covered)
- **Зробити:** 1) Додати auto-subscribe для camp.story (батьки заїзду) — зараз явно винесено в інший addon. 2) Перевірити/реалізувати архів каналу через +30 днів після заїзду — в event_channel_create.py немає жодного згадування про 30 днів чи архівацію. 3) Верифікувати повну матрицю auto-subscribe по 8 моделях — знайдено лише 5 override-ів.
- Чекер: підтверджено: Вердикт аналітика точно відображає стан вимоги: частина функціоналу реалізована та підтверджена пробами (створення каналу, учасники, приватність, auto-subscribe для інцидентів), а частина відсутня або

### [F-SALE-1] · TZ.md:249 · ТЗ заявляє: ✅
- Чому: Основний потік продажу підтверджено, але SKU-коди відсутні в коді, тому вимога виконана частково.
- Доказ: models/commercial.py:1077 — визначено метод _init_camp_registrations
- Доказ: models/commercial.py:716 — виклик _init_camp_registrations з order_line
- Доказ: models/commercial.py:835 — визначено метод _fayna_get_or_create_participant
- Доказ: models/commercial.py:912 — виклик _fayna_get_or_create_participant
- Доказ: tests/test_registration_seats.py:1-50 — тест для ADR-2 seats/registration
- Доказ: tests/test_campscout.py:1-50 — тест для portal values
- **Зробити:** Додати SKU-коди CS-* та TCS-*-NN-YY у models/commercial.py (або відповідні дані), оскільки grep не знайшов жодного збігу.
- Чекер: підтверджено: Аналітик правильно визначив, що основний потік продажу підтверджено пробами та тестами, але відсутність збігів для SKU-кодів `CS-*` та `TCS-*-NN-YY` у `models/commercial.py` вказує на часткове виконан

### [F-SALE-2] · TZ.md:251 · ТЗ заявляє: ✅
- Чому: Основна генерація картки реалізована і протестована, але вимога про відображення обох програм (normal+rain) на картці не підтверджена кодом — лише на рівні моделі даних.
- Доказ: models/camp.py:380 — метод _generate_product_card існує
- Доказ: models/camp.py:409-413 — structured program days → camp_daily_routine (Html)
- Доказ: models/camp.py:415-419 — activity lines → camp_activities_ids (m2m)
- Доказ: models/camp.py:421-425 — activity lines → camp_highlights (Html bullet points)
- Доказ: models/camp.py:225 — модель даних підтримує 'normal + rain plan' для shift
- Доказ: tests/test_card_generator.py:6-12 — тести покривають daily_routine, highlights, list_price, graceful skip, idempotency
- **Зробити:** Показати в коді, що обидві програми (normal + rain) фактично обробляються в _generate_product_card і виводяться на картку — зараз лише модель даних (camp.py:225) підтримує обидві програми, але генерація для rain-програми не доведена.
- Чекер: підтверджено: Аналітик вірно визначив, що докази підтверджують існування генератора та обробку більшості елементів картки. Проте, вимога щодо відображення обох програм (normal+rain) на картці не доведена кодом, а л

### [F-SALE-6] · TZ.md:259 · ТЗ заявляє: ✅
- Чому: Роути та HTML-шаблон для zwrot підтверджені, але ключовий PDF/Telegram/email пайплайн та шаблон oferta_ferie2027 не підтверджені пробами.
- Доказ: controllers/kadry_forms.py:44 — @http.route(["/camp/zwrot"], type="http", auth="public", website=False, methods=["GET"])
- Доказ: controllers/kadry_forms.py:50 — @http.route(["/camp/oferta/ferie2027"], type="http", auth="public", website=False, methods=["GET"])
- Доказ: static/src/kadry/zwrot.html:1-45 — HTML-шаблон для /camp/zwrot існує (title, форма, стилі)
- **Зробити:** Підтвердити реалізацію client-side PDF → сервер+Telegram+email пайплайну для /camp/zwrot (JS-код у zwrot.html, обробник на сервері, інтеграція з Telegram/email). Перевірити наявність static/src/kadry/oferta_ferie2027.html.
- Чекер: підтверджено: Вердикт аналітика 'PARTIAL' є точним. Надані докази підтверджують існування HTTP-роутів з `auth="public"` для обох сторінок та наявність HTML-шаблону для `/camp/zwrot`. TODO-пункти коректно вказують н

### [F-VAT-2] · TZ.md:267 · ТЗ заявляє: ✅
- Чому: Основний механізм vat_mode з дефолтом 'zw' реалізовано, але частина вимог (zlecenie поза VAT, підпис 'zwolniona', мерч 23%) не підтверджена жодною пробою.
- Доказ: wizards/camp_create_wizard.py:285 — vat_mode = fields.Selection(...)
- Доказ: wizards/camp_create_wizard.py:423 — vat_mode = rec.vat_mode or "zw" (default zw)
- Доказ: wizards/camp_create_wizard.py:446-458 — _compute_vat_mode derives from fiscal position, falls back to _VAT_MODE_DEFAULT
- Доказ: views/staffing_views.xml:304 — vat_mode widget radio in view
- **Зробити:** Додати докази/реалізацію для: 1) 'Кадра zlecenie = поза VAT' (немає згадок у пробах), 2) 'Підпис «zwolniona», НЕ «маржа 0%»' (немає тексту 'zwolniona' у models/views), 3) мерч 23% (немає доказів).
- Чекер: підтверджено: Аналітик коректно визначив, що основний механізм `vat_mode` у wizard з дефолтом `zw` реалізовано, що підтверджується наданими доказами з `camp_create_wizard.py`. Також вірно ідентифіковано відсутність

### [F-VAT-3] · TZ.md:269 · ТЗ заявляє: 🟡
- Чому: Фіскальні позиції та vat_mode реалізовано, але відсутні поля KRS/zaliczki та QWeb колонтитули для документів.
- Доказ: wizards/camp_create_wizard.py:265 — fiscal_position_id = fields.Many2one(...) з дефолтом через _default_fiscal_position()
- Доказ: wizards/camp_create_wizard.py:455-456 — vat_mode обчислюється з fiscal_position_id через _classify_fiscal_position()
- Доказ: data/fiscal_positions.xml:17,27,37 — три записи account.fiscal.position (zw, marza, standard)
- Доказ: models/camp.py:0 збігів — немає полів vat_marża, KRS, zaliczki/advance
- Доказ: reports/*.xml — лише header_line/header_spacing, немає QWeb header/footer з даними фірми
- **Зробити:** Додати поля KRS, zaliczki/advance до моделі camp; реалізувати QWeb header/footer в офертах/фактурах/договорах з даними фірми (№ wpisu, VAT-marża, KRS); перевірити ланцюг «форма → колонтитули»
- Чекер: підтверджено: Аналітик коректно визначив часткову реалізацію вимоги: фіскальні позиції та логіка vat_mode присутні, але відсутні поля для KRS/zaliczki та реалізація QWeb колонтитулів з даними фірми в документах, що

### [F-FIN-1] · TZ.md:271 · ТЗ заявляє: 🟡
- Чому: Категорії та частково аналітика є, але upload-фактур і автостворення аналітики на турнус не реалізовано.
- Доказ: models/budget.py:235 — account.analytic.account згадується в моделі budget
- Доказ: models/budget.py:554 — спроба отримати account.analytic.account, але з fallback-повідомленням про недоступність
- Доказ: models/budget.py:53 — camp.budget.category визначено як модель
- Доказ: models/budget.py:736 — camp.budget.category використовується в budget
- Доказ: models/staffing.py:451 — camp.budget.category використовується в staffing
- Доказ: controllers/kiosk.py — немає upload-роута для фактур
- **Зробити:** Додати upload-роут для фактур у кіоск керівника; перевірити/реалізувати автостворення аналітики на event-create
- Чекер: підтверджено: Вердикт аналітика точно відображає стан вимоги: наявність категорій та частково аналітики підтверджено, а відсутність функціоналу завантаження фактур та автостворення аналітики також чітко зафіксовано

### [F-FIN-2] · TZ.md:273 · ТЗ заявляє: 🟡
- Чому: PDF-частина підтверджена кодом, але XLSX-формат і кнопка не знайдені в пробах.
- Доказ: models/budget.py:587 — визначено метод action_print_evidence
- Доказ: models/budget.py:594 — визначено метод action_send_evidence_to_ksiegowa
- Доказ: models/budget.py:711 — виклик action_send_evidence_to_ksiegowa (cron)
- Доказ: reports/budget_evidence_templates.xml:8 — шаблон report_camp_budget_evidence
- Доказ: __manifest__.py:109 — підключено reports/budget_evidence_templates.xml
- **Зробити:** XLSX-формат евіденції та кнопка на панелі [F-KSK-3]
- Чекер: підтверджено: Аналітик коректно ідентифікував підтверджену PDF-частину вимоги за наданими пробами (наявність методів, шаблону та його підключення), а також чітко визначив залишок (XLSX-формат та кнопка) відповідно

### [F-FIN-3] · TZ.md:275 · ТЗ заявляє: ✅
- Чому: Formula, guard, and warning are implemented and tested, but the known gap (sale.order does not feed przychód/price_per_child) remains unfixed, so the requirement is only partially done.
- Доказ: models/budget.py:373 — denominator = rec.price_per_child - var; guard denominator <= 0 at :374
- Доказ: models/budget.py:828 — _onchange_website_published_bep_warning defined
- Доказ: tests/test_bep_activation_warning.py:59-67 — below-BEP publish warns but does not block
- Доказ: models/budget.py:132 — price_per_child field exists
- Доказ: models/budget.py:7-9 — przychód only in comments, no field/compute
- Доказ: models/budget.py:grep sale.order — 0 matches
- **Зробити:** Implement automatic przychód/price_per_child computation from confirmed sale.order linked to event; add test verifying new SO updates BEP panel; re-run SQL audit to reduce 69 zero-przychód sale.order records to 0.
- Чекер: підтверджено: Докази повністю підтверджують вердикт аналітика. Формула BEP, її guard та механізм попередження підтверджені кодом та тестами. Відсутність інтеграції `sale.order` для обчислення `przychód` також підтв

### [F-FIN-4] · TZ.md:277 · ТЗ заявляє: 🟡
- Чому: Zestawienie-звіти (report_budget_zestawienie + report_season_budgets) підтверджені в коді, але Rejestr faktur лишився TODO-коментарем.
- Доказ: reports/budget_report_templates.xml:15 — template id="report_budget_zestawienie" існує
- Доказ: reports/budget_report_templates.xml:175 — template id="report_season_budgets" існує
- Доказ: reports/budget_report_templates.xml:7 — NOTE: Rejestr faktur za miesiąc (P_PMarzy / l10n_pl_ksef_margin) — TODO
- Доказ: models/budget.py:422 — mapping; part of the Rejestr faktur step
- **Зробити:** Збудувати Rejestr faktur za miesiąc (шаблон звіту) та заповнення P_PMarzy через l10n_pl_ksef_margin — разом з [F-VAT-4]
- Чекер: підтверджено: Вердикт аналітика точно відповідає вимозі та наданим доказам. Два звіти (`Zestawienie obozu` та `Zestawienie obozów`) підтверджені наявністю шаблонів, а `Rejestr faktur за місяць` та заповнення `P_PMa

### [F-OPS-1] · TZ.md:287 · ТЗ заявляє: 🟡
- Чому: Основні моделі (diet.profile, menu.day, meal.plan) підтверджені, але агрегат для кухні не знайдено, а файл алергенів не містить даних.
- Доказ: models/nutrition.py:147 — _name = "camp.diet.profile" (модель існує)
- Доказ: models/nutrition.py:464 — _name = "camp.menu.day" (модель існує)
- Доказ: models/nutrition.py:266 — _name = "camp.meal.plan" (модель існує)
- Доказ: models/nutrition.py:387 — _name = "camp.meal.plan.line" (модель існує)
- Доказ: data/camp_allergens.xml — 0 збігів 'allergen' (файл не містить алергенів або відсутній)
- Доказ: views/nutrition_views.xml:64-102 — view/action для camp.diet.profile
- **Зробити:** Додати/підтвердити агрегат-витяг для кухні (зведення дієт/алергій по табору) — view або метод; перевірити наявність data/camp_allergens.xml з EU-14 алергенами
- Чекер: підтверджено: Вердикт аналітика обґрунтований: основні моделі та їх UI підтверджені, а відсутність даних про алергени у файлі та непідтверджений агрегат для кухні коректно відзначені як TODO, що відповідає статусу

### [F-OPS-5] · TZ.md:295 · ТЗ заявляє: ✅
- Чому: Підтверджено snapshot, report, view-as, лог та R10, але відсутні докази самого /admin/dashboard з 7 секціями — вимога заявлена як ✅, тому це DRIFT у бік завищення статусу.
- Доказ: models/reports.py:48 — _name = "camp.analytics.snapshot" (модель існує)
- Доказ: models/reports.py:281 — _name = "camp.marketing.report" (модель існує)
- Доказ: controllers/admin.py:391 — with_user(target_user) для ACL (view-as реалізовано)
- Доказ: models/admin_access_log.py:27 — _name = "camp.admin.access.log" (лог існує)
- Доказ: models/reports.py:317-334 — compute_sudo=True на групі _compute_metrics (R10)
- Доказ: models/regulamin.py:126 — compute_sudo=True для _compute_ack_stats (R10)
- **Зробити:** Надати докази існування /admin/dashboard з 7 секціями (бізнес, тривоги, активні табори, команда, комунікації, маркетинг+SMS-costs, audit) — контролер, шаблон або тест, що підтверджує структуру дашборду
- Чекер: підтверджено: Аналітик коректно ідентифікував наявні докази для `camp.analytics.snapshot`, `camp.marketing.report`, `view-as` (`with_user`), `camp.admin.access.log` та реалізації R10 (`compute_sudo=True` і тест). Т

### [F-OPS-6] · TZ.md:297 · ТЗ заявляє: ✅
- Чому: Всі основні компоненти (модель, workflow, PDF) реалізовані, але обмеження учасників ≤20 не підтверджено жодним доказом.
- Доказ: models/operations.py:2637 — _name = "fayna.camp.dziennik" (модель існує)
- Доказ: models/operations.py:2838 — raise UserError(_("Only draft dzienniki can be activated.")) (activate workflow)
- Доказ: models/operations.py:2847 — raise UserError(_("Only active dzienniki can be submitted.")) (submit workflow)
- Доказ: models/operations.py:2867-2869 — report = self.env.ref("fayna_camp_portal.action_report_dziennik") (PDF)
- Доказ: reports/dziennik_reports.xml:27-35 — ir.actions.report для fayna.camp.dziennik (PDF)
- Доказ: models/operations.py:2730-2731 — relation="fayna_camp_dziennik_participant_rel" (учасники є)
- **Зробити:** Реалізувати обмеження кількості учасників ≤20 для dziennik (немає доказів у коді).
- Чекер: підтверджено: Аналітик коректно визначив статус 'PARTIAL', навівши чіткі докази для реалізованих частин вимоги (модель, workflow, PDF, плани, записи, нотатки) та точно вказавши відсутній елемент (обмеження учасникі

### [F-DOC-1] · TZ.md:303 · ТЗ заявляє: ✅
- Чому: Native-частина (sale.order, account.move, teczka.ko, program.structured) підтверджена, але RODO та HR-компоненти відсутні, а інші елементи (оферта, поліса, opinia) не мають доказів.
- Доказ: models/teczka_ko.py:32 — _name = "camp.teczka.ko" (zgłoszenie=teczka.ko)
- Доказ: models/operations.py:1873 — _name = "camp.program.structured" (program=camp.program.structured)
- Доказ: models/commercial.py:534 — _inherit = "sale.order" (umowa=sale.order)
- Доказ: models/commercial.py:1576 — generate_installments для fayna.payment.installment (рати)
- Доказ: models/commercial.py:1730 — "account.move" (фактури)
- Доказ: models/budget.py:457 — account.move.line (фактури)
- **Зробити:** Додати/підтвердити: 1) fayna_rodo_compliance (0 збігів у models); 2) hr.employee attachments + staff cert (0 збігів у models); 3) оферта=product+QWeb; 4) поліса=attachment на event+move; 5) opinia PSP/sanepid=attachment; 6) karta=participant; 7) dziennik; 8) umowa=sign
- Чекер: підтверджено: Аналітик коректно визначив підтверджені елементи вимоги (teczka.ko, camp.program.structured, sale.order, account.move, рати) та чітко перерахував усі відсутні докази у списку 'todo', що відповідає вер

### [F-DOC-4] · TZ.md:309 · ТЗ заявляє: 🟡
- Чому: Retention policy is partially implemented (retention_until fields and archive methods exist) but the auto-cron with to_erase flag, claims check, and erasure logging is missing.
- Доказ: models/operations.py:1693-1709 — retention_until computed as end + 7 years
- Доказ: models/participant.py:1049-1170 — retention_until computed as max(anchors) + 7 years
- Доказ: models/operations.py:524,533,1132 — archive methods for records >7 years old
- Доказ: data/cron.xml:8-95 — multiple ir.cron records exist but none named for retention erasure
- Доказ: models/commercial.py:277 — RODO erasure for referral data only
- **Зробити:** Build the actual auto-erasure cron: create ir.cron that flags records with to_erase, checks active claims (pause during court case), logs erasure, and handles all document types (medical, journal, reports, staff docs, signatures, umowy 10y, KSeF 5y, stories 2y, marketing consents, qualifications permanent). Current code only computes retention_until but never triggers deletion.
- Чекер: підтверджено: Аналітик коректно визначив, що політика частково зафіксована (існують поля `retention_until` та методи архівування), але автоматичний крон для повного циклу видалення (з `to_erase` прапором, перевірко

### [F-I18N-1] · TZ.md:315 · ТЗ заявляє: ✅
- Чому: Endpoint і UI-селектор підтверджені, але persist на res.users.lang не доведено через відсутність збігів у models/res_users_inherit.py — потрібна додаткова проба на повний код контролера.
- Доказ: controllers/kiosk.py:299 — endpoint /camp/kiosk/set_lang присутній
- Доказ: controllers/kiosk.py:304 — метод kiosk_set_lang визначено
- Доказ: controllers/kiosk.py:324 — валідація мови (rejected non-bilingual)
- Доказ: controllers/kiosk.py:336 — валідація активної мови
- Доказ: templates/portal_templates.xml:84 — portal.language_selector у шаблоні
- Доказ: models/res_users_inherit.py — 0 збігів 'lang' (persist на res.users.lang НЕ знайдено)
- **Зробити:** Знайти/підтвердити код, що зберігає вибір мови на res.users.lang (можливо в іншому файлі, напр. models/res_users.py або в самому контролері — перевірити рядки 304-336 повністю)
- Чекер: підтверджено: Аналітик вірно визначив, що ключова частина вимоги про збереження вибору мови на `res.users.lang` не підтверджена наданими пробами, що виправдовує вердикт 'PARTIAL' та відповідний 'todo'.

### [F-I18N-2] · TZ.md:317 · ТЗ заявляє: ✅
- Чому: POT і PO файли існують і містять переклади, але grep по templates/ не знайшов жодного виклику _()/_lt, що ставить під сумнів повноту вимоги.
- Доказ: i18n/fayna_camp_portal.pot:7 — POT-Creation-Date 2026-07-02, регенерований
- Доказ: i18n/fayna_camp_portal.pot:19 — code-reference model:res.groups,comment:fayna_camp_portal.group_camp_hr
- Доказ: i18n/uk_UA.po:227 — msgid "# Actions" присутній у перекладі
- Доказ: i18n/pl_PL.po:227 — msgid "# Actions" присутній у перекладі
- Доказ: templates — 0 збігів _lt|_\(|translation, що суперечить вимозі "всі UI-рядки через _()/_lt"
- **Зробити:** Перевірити, чи всі UI-рядки в templates/ обгорнуті _()/_lt — grep дав 0 збігів, що вказує на відсутність викликів перекладу в шаблонах; можливо, шаблони порожні або рядки хардкоджені
- Чекер: підтверджено: Вердикт 'PARTIAL' обґрунтований, оскільки проби підтверджують регенерацію POT/PO файлів та наявність перекладів, але відсутність викликів `_()`/`_lt` у шаблонах (0 збігів) прямо суперечить ключовій ча

### [F-I18N-3] · TZ.md:319 · ТЗ заявляє: ✅
- Чому: Частина вимог підтверджена (help=, глосарій), але ключові інваріанти (--i18n-overwrite, --fix, po-pretty-format, en_US) не підтверджені через помилки проб або відсутність збігів.
- Доказ: .github/workflows/ci.yml:5 — згадка про .pre-commit-config.yaml як джерело правди
- Доказ: docs/user-guide/GLOSSARY.md:11-12 — розрізнення wychowawca/kierownik
- Доказ: views/budget_views.xml:21,27,34,55,63,85,90,116,138,264 — help= на полях
- Доказ: views/group_views.xml:39 — help= на полях
- Доказ: views/operations_views.xml:66 — help= на полях
- Доказ: views/regulamin_views.xml:44,59,90 — help= на полях
- **Зробити:** Перевірити наявність --i18n-overwrite у деплой-скриптах (проба не вдалась через помилку git grep); перевірити наявність --fix у .pre-commit-config.yaml (проба не знайшла); перевірити po-pretty-format (0 збігів); перевірити en_US у i18n (0 збігів)
- Чекер: підтверджено: Аналітик коректно визначив, які частини вимоги підтверджені (глосарій, використання help=) та які потребують подальшої перевірки (i18n-overwrite, --fix, po-pretty-format, en_US), а також вказав на про

### [N-2] · TZ.md:328 · ТЗ заявляє: 🟡
- Чому: Частково реалізовано: фото-upload і маршрути /my/* є, але відсутні touch-цілі 44px і WCAG AA контраст, а систематичний mobile-audit не підтверджено.
- Доказ: static/src/css/portal.css:11 — border-bottom: 1px solid #f0f0f0 (низький контраст, не WCAG AA)
- Доказ: static/src/css/portal.css:21 — background: #d6d6d6 (сірий фон, контраст не підтверджено)
- Доказ: static/src/css/portal.css:32 — linear-gradient(90deg, #dcdcdc 0%, #e9e9e9 50%, #dcdcdc 100%) (світлі тони, контраст не підтверджено)
- Доказ: templates/portal_recruitment.xml:265-266 — <input type="file" name="photo" accept="image/*"/> (фото-upload присутній)
- Доказ: controllers/portal.py:46,207,324,345,409,454,632 — маршрути /my/* присутні
- **Зробити:** Додати touch-цілі ≥44px (в CSS немає min-height/min-width:44px); забезпечити WCAG AA контраст (поточні кольори #f0f0f0, #d6d6d6, #dcdcdc не відповідають); провести систематичний mobile-audit на реальному телефоні для всіх /my/* екранів (в коді немає доказів проведення)
- Чекер: підтверджено: Вердикт аналітика 'PARTIAL' добре обґрунтований: наявність фото-upload та маршрутів /my/* підтверджено, тоді як відсутність доказів для touch-цілей ≥44px, WCAG AA контрасту та систематичного mobile-au

### [T-1] · TZ.md:342 · ТЗ заявляє: ✅
- Чому: Всі заявлені групи тестів присутні в tests/__init__.py, але точна кількість 43 файлів не підтверджена пробами.
- Доказ: tests/__init__.py:19-20 — test_karta_2026, test_karta_pdf присутні
- Доказ: tests/__init__.py:6-7,17-18,30,42-43 — правові тести (test_art9_access, test_art9_http_isolation, test_escort_signoff, test_incident_card, test_rodo_consent_immutable, test_signoff_rodo, test_staffing) присутні
- Доказ: tests/__init__.py:31-40 — 10 test_role_* файлів (test_role_canon, test_role_instructor, test_role_kierownik_dziennik, test_role_organizator_create_camp, test_role_parent_cabinet, test_role_parent_image_consent, test_role_parent_portal, test_role_public_vacancies, test_role_wychowawca_day_note, test_role_wychowawca_note)
- Доказ: tests/__init__.py:9-11,13,22-28 — доменні тести (test_bep_activation_warning, test_budget, test_camp_group, test_card_generator, test_native_approval, test_phase_c_wychowawca, test_phase_d_split, test_pricing_calculator, test_program_skeleton, test_registration_seats) присутні
- Доказ: tests/__init__.py:5,21,45 — reuse-міграційні тести (test_analytics_snapshot, test_legacy_program_migration, test_training_migration) присутні
- **Зробити:** Підтвердити точну кількість тест-файлів (43) через `ls tests/test_*.py` — проби показали лише наявність у __init__.py, але не повний список файлів
- Чекер: підтверджено: Аналітик коректно визначив, що проби підтверджують наявність більшості заявлених тест-файлів у `tests/__init__.py` за категоріями, але не підтверджують точну кількість у 43 файли, як вимагає ТЗ. Верди

### [T-2] · TZ.md:348 · ТЗ заявляє: ✅
- Чому: Lint і test-gate підтверджені, але module-upgrade dry-run і branch protection не знайдені в .github/workflows/ci.yml
- Доказ: .github/workflows/ci.yml:21 — name: Lint (ruff + bandit + gitleaks + OCA)
- Доказ: .github/workflows/ci.yml:39 — name: Odoo unit tests (test-gate)
- Доказ: .github/workflows/ci.yml:94 — Гейт (греп логу + exit code) — у tools/run_odoo_tests.sh
- Доказ: .github/workflows/ci.yml:108 — odoo:17 /mnt/addons/fayna_camp_portal/tools/run_odoo_tests.sh
- **Зробити:** Додати module-upgrade dry-run job у CI workflow; додати branch protection конфігурацію (required_status_checks, up-to-date, review) у workflow або окремий файл
- Чекер: підтверджено: Аналітик коректно ідентифікував наявність Lint та test-gate, а також відсутність module-upgrade dry-run та конфігурації branch protection у файлі ci.yml, що відповідає вердикту PARTIAL. TODO-пункти сф

### [T-3] · TZ.md:350 · ТЗ заявляє: ✅
- Чому: Код підтверджує лише виправлення networkidle, але відсутні докази решти заявлених функцій (8 кроків, двомовність, скріни, автоматичний запуск).
- Доказ: e2e/test_critical_paths.py:34 — page.wait_for_url використовується замість networkidle
- Доказ: e2e/test_critical_paths.py:30-32 — коментарі підтверджують виправлення networkidle-антипатерну
- Доказ: .github/workflows/e2e.yml:12 — workflow_dispatch (ручний запуск), не автоматичний на staging
- Доказ: .github/workflows/e2e.yml:27-35 — E2E запускається через pytest, але немає доказів 8 кроків майстра чи двомовності
- Доказ: e2e/test_critical_paths.py — grep 'UA' дав 0 збігів, немає доказів тестів двомовності
- Доказ: Немає жодного доказу скріншотів (screenshot) у коді чи workflow
- **Зробити:** 1) Додати/підтвердити тести 8 кроків майстра; 2) Додати тести двомовності (UA kiosk, кабінет); 3) Додати скріншоти в тести; 4) Розглянути автоматичний запуск на staging (зараз workflow_dispatch)
- Чекер: підтверджено: Вердикт аналітика обґрунтований: проби чітко підтверджують виправлення networkidle-антипатерну, але не містять жодних доказів щодо 8 кроків майстра, двомовності чи скріншотів, як зазначено у вимозі. П

### [T-4] · TZ.md:352 · ТЗ заявляє: 🟡
- Чому: Частина боргів закрита (auto-refusal cron ✅, coverage-аудит існує), але UAT, sign-off, coverage-ціль і кілька прямих тестів не виконані.
- Доказ: tests/__init__.py:8 — test_auto_refusal_cron присутній (підтверджено ✅ з ТЗ)
- Доказ: docs/QUALITY_AUDIT_2026-07-04.md:1 — аудит coverage існує, але в пробі немає цифри 69%
- Доказ: docs/TZ.md:452 — coverage 69%, ціль ≥70%, дельта ~90 інструкцій
- Доказ: docs/TZ.md:515 — GAP-3: UAT не проведено, sign-off відсутній
- Доказ: docs/TESTING.md — 0 збігів 'sign-off' (немає документації UAT)
- Доказ: .github/workflows/deploy-staging.yml — staging деплой існує, але це не UAT-процедура
- **Зробити:** Провести UAT з 3-5 живими користувачами на staging, задокументувати кроки та sign-off у docs/TESTING.md; підняти coverage з 69% до ≥70% (~90 stmts); додати прямі тести для Kamilka-ескалація cron, SMS cost-guard, declaracja-блокування, attachment-ACL PDF; виконати pytest-матрицю RODO, performance-бенчмарки
- Чекер: підтверджено: Вердикт аналітика точно відображає статус вимоги: 'PARTIAL' та '🟡' відповідають наявності як виконаних, так і невиконаних пунктів. Докази підтверджують кожен пункт, а список 'todo' є вичерпним і корек

### [Q8-8] · TZ.md:399 · ТЗ заявляє: 🟡
- Чому: TZ заявляє про 100% pass тесту HTTP-ізоляції, але в tests/ його немає — статус 🟡 виправданий, оскільки доказ проходження відсутній у репозиторії.
- Доказ: docs/TZ.md:179 — [F-RODO-2] заявлено: (2) attachment-ACL на PDF — 🟡 record-rule на ir.attachment з медвмістом не підтверджено тестом; але далі: ✅ HTTP-ізоляція ВИРІШЕНА 04.07 (PR#17): ... test_art9_http_isolation = 100% pass
- Доказ: security/record_rules.xml:842-888 — існує record rule на ir.attachment (model_id base.model_ir_attachment) для karta-PDF
- Доказ: tests/__init__.py:30,42 — тести test_rodo_consent_immutable та test_signoff_rodo присутні, але test_art9_http_isolation НЕ знайдено в tests/
- **Зробити:** Підтвердити наявність та проходження тесту test_art9_http_isolation (файл не знайдено в tests/); якщо тест існує в іншому місці — вказати шлях, інакше додати його
- Чекер: підтверджено: Вердикт аналітика обґрунтований. Хоча TZ.md:179 заявляє про '✅ HTTP-ізоляція ВИРІШЕНА' та 'test_art9_http_isolation = 100% pass', проби не знаходять файл цього тесту в каталозі 'tests/'. Це виправдову

### [Q8-9] · TZ.md:400 · ТЗ заявляє: нема
- Чому: Є розширення res.company та використання company в кількох місцях, але branding (логотип компанії) не реалізовано в моделі res.company — лише в staffing.
- Доказ: models/participant.py:2370 — _inherit = "res.company" (розширення моделі компанії)
- Доказ: views/res_company_views.xml:12-13 — форма res.company з секцією CampScout
- Доказ: models/participant.py:2377 — поле для підпису організатора в Settings → Companies
- Доказ: models/operations.py:2818 — auto-derived organizer name з company_id
- Доказ: static/src/kadry/ferie2027.html:161 — SVG логотип (umbrella) в шаблоні
- Доказ: models/budget.py:634-645 — використання company.email/name в email_from
- **Зробити:** Перевірити наявність поля logo в res.company (не знайдено в models/participant.py, лише в staffing_views.xml як logo_image для заходу). Можливо потрібно додати branding-поля (логотип, кольори) до res.company.
- Чекер: підтверджено: Вердикт PARTIAL обґрунтований: є розширення моделі res.company та використання даних компанії, що відповідає 'Картка-еталон фірми'. Однак, 'брендинг company' (динамічний логотип/кольори в моделі res.c

### [Q8-12] · TZ.md:403 · ТЗ заявляє: 🟡
- Чому: PDF+email+cron підтверджено, але XLSX і кнопка панелі відсутні — залишок з ТЗ не виконано.
- Доказ: docs/TZ.md:273 — [F-FIN-2] заявлено: PDF-частина Є, ЗАЛИШОК: XLSX-формат + кнопка на панелі
- Доказ: reports/budget_evidence_templates.xml:8 — шаблон report_camp_budget_evidence існує (PDF)
- Доказ: reports/budget_reports.xml:19-24 — action_report_camp_budget_evidence зареєстровано
- Доказ: reports/budget_reports.xml:3 — коментар: XLSX замінено на PDF QWeb, без report_xlsx залежності
- Доказ: models: [0 збігів xlsx] — XLSX-формат не реалізовано
- Доказ: controllers: [0 збігів xlsx] — кнопка панелі для XLSX не знайдена
- **Зробити:** Реалізувати XLSX-формат евіденції (залежність report_xlsx або аналог) та додати кнопку на панелі [F-KSK-3]
- Чекер: підтверджено: Вердикт аналітика коректно відображає статус: PDF-частина вимоги виконана (підтверджено TZ та наявністю шаблонів), тоді як XLSX-формат та відповідна кнопка відсутні, що підтверджується відсутністю збі

### [Q8-17] · TZ.md:408 · ТЗ заявляє: ✅
- Чому: Усі 6 пар міграцій присутні в коді, але ТЗ вимагає підтвердження прогану на staging для пар 5/6, а кроки (2)–(4) не підтверджені пробами.
- Доказ: migrations/17.0.4.1.2/post-migrate.py:3 — Reuse S1 пара 1: camp.stats.snapshot → camp.analytics.snapshot
- Доказ: migrations/17.0.4.1.3/post-migrate.py:3 — Reuse S1 пара 2: camp.journal → camp.daily.report
- Доказ: migrations/17.0.4.1.4/post-migrate.py:3 — Reuse S1 пара 3: camp.nutrition (legacy) → camp.menu.day
- Доказ: migrations/17.0.4.1.5/post-migrate.py:3 — Reuse S1 пара 4: camp.participant.diet → camp.diet.profile
- Доказ: migrations/17.0.4.1.6/post-migrate.py:4 — camp.program.structured (+camp.program.day +camp.program.activity.line)
- Доказ: migrations/17.0.4.1.7/post-migrate.py:6 — camp.staff.training.record (keeper, extends native slide.channel — ADR-001)
- **Зробити:** Підтвердити на staging прогін пар 5/6 (camp.program.structured, camp.staff.training.record) з `-u` — у ТЗ зазначено, що на staging прогнано лише pair4, pair5/6 чекає; також перевірити, чи виконані кроки (2)–(4) (SMS-шаблони, рекрутація, story/review) — у пробах їх немає.
- Чекер: підтверджено: Аналітик коректно визначив статус 'PARTIAL', оскільки вимога містить суперечливу інформацію про завершення (✅ ЗАВЕРШЕНО, але ⚠️ на staging прогнано лише pair4). Також вірно відзначено відсутність проб

### [PR-3] · TZ.md:436 · ТЗ заявляє: ✅
- Чому: Staging-деплой автоматизовано і підтверджено, але prod-частина #4ZONES, human-approval gate та обробка секретів heredoc/BP-010 не підтверджені наявними пробами.
- Доказ: .github/workflows/deploy-staging.yml:3 — CD: повна автоматизація того ж безпечного сценарію, що в tools/deploy-staging.sh.
- Доказ: .github/workflows/deploy-staging.yml:14 — Активація: push у гілку `staging` АБО ручний запуск (workflow_dispatch).
- Доказ: .github/workflows/deploy-staging.yml:23 — branches: [staging]
- Доказ: .github/workflows/deploy-staging.yml:31 — Safe staging deploy (clear .pyc + gated migration + wait-for-green + rollback)
- Доказ: .github/workflows/deploy-staging.yml:47 — URL="https://staging.campscout.eu/web/health"
- Доказ: .github/workflows/deploy-staging.yml:84 — ✅ DEPLOY OK — staging green.
- **Зробити:** Додати workflow для prod-деплою (зараз є лише staging), перевірити наявність human-approval gate для deploy (у staging workflow не знайдено явного approval step), підтвердити heredoc/BP-010 для секретів у deploy-скриптах.
- Чекер: підтверджено: Вердикт аналітика 'PARTIAL' обґрунтований: проби підтверджують лише частину вимоги (staging-деплой), тоді як відсутність prod-деплою, явного human-approval gate та конкретних доказів використання here

### [GAP-8] · TZ.md:525 · ТЗ заявляє: 🔴
- Чому: Cron-механіка існує (data/cron.xml + методи в operations.py), але не всі методи з cron.xml знайдено в моделях, тому частково виконано.
- Доказ: data/cron.xml:8-12 — ir.cron cron_auto_refusal_unsigned з кодом model._cron_auto_refusal_scan()
- Доказ: data/cron.xml:21-25 — ir.cron cron_qualification_reminders з кодом model._cron_auto_refusal_reminders()
- Доказ: data/cron.xml:34-38 — ir.cron cron_installment_overdue з кодом model._cron_mark_overdue()
- Доказ: data/cron.xml:51-55 — ir.cron cron_expire_camp_staff_training_records з кодом model._cron_expire_training_records()
- Доказ: data/cron.xml:66-70 — ir.cron ir_cron_daily_report_archive з кодом model.cron_archive_old_reports()
- Доказ: data/cron.xml:79-83 — ir.cron cron_daily_analytics_snapshot з кодом model._cron_take_daily_snapshot()
- **Зробити:** Перевірити чи всі cron-записи в data/cron.xml мають відповідні методи в моделях (наприклад _cron_auto_refusal_scan, _cron_auto_refusal_reminders, _cron_mark_overdue, _cron_expire_training_records, _cron_take_daily_snapshot, _cron_send_monthly_evidence) — grep не показав їх визначення в models/.
- Чекер: підтверджено: Аналітик вірно визначив наявність механіки `ir.cron` та методів, що стосуються retention/archiving, що відповідає вимозі 'Автоматична retention/erasure-механіка'. Зазначений `todo` є обґрунтованим, ос

### [API-3] · TZ.md:655 · ТЗ заявляє: ✅
- Чому: Архітектура інтеграцій зафіксована (✅), але KSeF-частина (F-VAT-4) і SendPulse-консолідація (F-RODO-5) позначені 🔴 у ТЗ — отже повний обсяг API-3 не виконано.
- Доказ: docs/TZ.md:655 — заявлено ✅ архітектура; контракти = документація вендорів
- Доказ: docs/TZ.md:70 — l10n_pl_ksef_margin, fayna_sms_base, zadarma_odoo згадані як горизонтальні модулі
- Доказ: __manifest__.py:64 — fayna_sms_base у depends
- Доказ: docs/TZ.md:185 — F-RODO-5: SendPulse консолідація журналу 🔴 не виконана
- Доказ: docs/TZ.md:281 — F-VAT-4: KSeF-експорт P_PMarzy 🔴 не збудовано (sale_margin/l10n_pl_ksef_margin відсутні в depends)
- Доказ: docs/TZ.md:183 — F-RODO-4: SendPulse-sync не верифіковано 🟡
- **Зробити:** Закрити F-VAT-4 (KSeF P_PMarzy через l10n_pl_ksef_margin) та F-RODO-5 (міграція журналів SendPulse→fayna_rodo_consent_log); верифікувати SendPulse sync (F-RODO-4).
- Чекер: підтверджено: Вердикт PARTIAL обґрунтований: архітектура інтеграцій заявлена як ✅, що відповідає вимозі. Однак, докази чітко вказують на невиконані (🔴) або неперевірені (🟡) частини інтеграцій KSeF (F-VAT-4) та Send

## ❔ ПРОБИ НЕ ДАЛИ ВІДПОВІДІ — 3

### [F-SALE-5] · TZ.md:257 · ТЗ заявляє: ✅
- Чому: Проби показують наявність поля та його використання в моделі й шаблоні, але не підтверджують ключові вимоги ТЗ: єдине джерело, оновлення обома шляхами, parity з BonSens.
- Доказ: models/commercial.py:1151 — поле seats_available існує в моделі
- Доказ: models/commercial.py:1155 — коментар про суму seats_available
- Доказ: models/commercial.py:1203 — total_seats = sum(upcoming.mapped("seats_available"))
- Доказ: templates/portal_templates.xml:325 — відображення camp.seats_available
- Доказ: tests/test_registration_seats.py — 0 збігів з seats_available
- Доказ: controllers — 0 збігів
- **Зробити:** Потрібно перевірити: 1) чи seats_available читається саме з event.event.ticket.seats_available (а не з іншого поля), 2) чи обидва шляхи покупки оновлюють цей лічильник, 3) parity з BonSens
- Чекер: підтверджено: Вердикт аналітика 'UNCLEAR' є обґрунтованим. Надані проби не підтверджують ключові аспекти вимоги, такі як єдине джерело (event.event.ticket.seats_available), оновлення лічильника обома шляхами покупк

### [M-1] · TZ.md:362 · ТЗ заявляє: ✅
- Чому: Проби не дають доказів про фактичні дані на проді — лише код скриптів, без SQL-верифікації.
- Доказ: __manifest__.py:38 — згадка campscout_management лише як архітектурний опис, не як інстальований модуль
- Доказ: scripts/populate_from_bs.py:64-168 — код працює з bs_child_name, але немає доказів про кількість записів (124 child, 122 consent)
- Доказ: scripts/populate_from_bs.py — немає згадок product.template, attribute.value, qualification_pdf
- **Зробити:** Потрібні SQL-проби: кількість записів у product.template, attribute.value, views, menus, events, tickets, child, consent, qualification_pdf, sale.signature; перевірка інсталяції campscout_management
- Чекер: підтверджено: Аналітик правильно зазначає, що надані проби (grep по файлах) не підтверджують фактичні кількості записів на проді, які заявлені у вимозі. Також відсутні SQL-проби, незважаючи на заявлену 'SQL-верифік

### [Q8-5] · TZ.md:396 · ТЗ заявляє: 🟡
- Чому: Проби показують наявність sale.order/line інтеграцій та pricing calculator, але немає доказів, що BEP-розрив продажі→ціна реалізований саме через майстер — флоу не простежується.
- Доказ: models/commercial.py:534 — sale.order _inherit exists (loyalty gate + BANDA issuance + RODO consent)
- Доказ: models/commercial.py:945 — sale.order.line _inherit exists (auto-link camp event + promo pricing)
- Доказ: models/commercial.py:963-976 — line has product_id, ticket match by product_id
- Доказ: models/commercial.py:1089-1106 — promo pricing logic writes sale_order_line_id and sale_order_id
- Доказ: models/budget.py:178-228 — BEP fields and fill_vs_bep computation exist
- Доказ: models/budget.py:828-851 — BEP warning at activation (non-blocking)
- **Зробити:** Потрібно перевірити флоу продажі→ціна через майстер: чи wizard кроки включають sale.order creation і чи ціна з sale.order.line коректно передається в wizard (немає прямих доказів зв'язку sale.order з wizard).
- Чекер: підтверджено: Аналітик вірно вказав, що проби підтверджують наявність окремих компонентів (sale.order, BEP-логіка, wizard), але не демонструють повний флоу 'продажі→ціна через майстер' та його зв'язок з BEP-розриво

## 🌐 ЛИШЕ STAGING/PROD (з репо не перевірити) — 16

### [B-2] · TZ.md:50 · ТЗ заявляє: —
- Чому: перевіряється лише на staging/prod або поза кодом

### [B-3] · TZ.md:52 · ТЗ заявляє: —
- Чому: перевіряється лише на staging/prod або поза кодом

### [B-4] · TZ.md:54 · ТЗ заявляє: —
- Чому: перевіряється лише на staging/prod або поза кодом

### [B-6] · TZ.md:58 · ТЗ заявляє: —
- Чому: перевіряється лише на staging/prod або поза кодом

### [F-RODO-7] · TZ.md:189 · ТЗ заявляє: —
- Чому: перевіряється лише на staging/prod або поза кодом

### [N-1] · TZ.md:326 · ТЗ заявляє: —
- Чому: перевіряється лише на staging/prod або поза кодом

### [M-5] · TZ.md:372 · ТЗ заявляє: —
- Чому: перевіряється лише на staging/prod або поза кодом

### [M-6] · TZ.md:374 · ТЗ заявляє: —
- Чому: перевіряється лише на staging/prod або поза кодом

### [M-7] · TZ.md:376 · ТЗ заявляє: —
- Чому: перевіряється лише на staging/prod або поза кодом

### [Q8-3] · TZ.md:394 · ТЗ заявляє: —
- Чому: перевіряється лише на staging/prod або поза кодом

### [Q8-6] · TZ.md:397 · ТЗ заявляє: —
- Чому: перевіряється лише на staging/prod або поза кодом

### [Q8-16] · TZ.md:407 · ТЗ заявляє: —
- Чому: перевіряється лише на staging/prod або поза кодом

### [GAP-1] · TZ.md:511 · ТЗ заявляє: —
- Чому: перевіряється лише на staging/prod або поза кодом

### [GAP-4] · TZ.md:517 · ТЗ заявляє: —
- Чому: перевіряється лише на staging/prod або поза кодом

### [GAP-6] · TZ.md:521 · ТЗ заявляє: —
- Чому: перевіряється лише на staging/prod або поза кодом

### [GAP-7] · TZ.md:523 · ТЗ заявляє: —
- Чому: перевіряється лише на staging/prod або поза кодом

## ✅ ГОТОВО (підтверджено кодом) — 9

### [A-3] · TZ.md:70 · ТЗ заявляє: ✅
- Чому: All fayna_camp_* references point to fayna_camp_portal (the new module), and migration comments confirm old modules were deprecated and code moved here.
- Доказ: models/__init__.py:43 — camp.story migrated from fayna_camp_stories (TZ §9 step 4)
- Доказ: models/__init__.py:46 — camp.transport migrated from fayna_camp_transport (TZ §16 Phase 6)
- Доказ: models/__init__.py:49 — Reports & analytics migrated from fayna_camp_reports (TZ §16 Phase 7)
- Доказ: models/auto_subscribe_extensions.py:22 — model lives in sibling addon fayna_camp_stories which is NOT a dependency
- Доказ: models/auto_subscribe_extensions.py:60 — references fayna_camp_portal.group_camp_organizator (new module)
- Чекер: підтверджено: Проби підтверджують, що `fayna_camp_portal` є центральним модулем для нового функціоналу, а старі `fayna_camp_*` модулі згадуються у контексті міграції або як не-залежності, що відповідає вимозі 'жодн

### [F-WIZ-1] · TZ.md:113 · ТЗ заявляє: ✅
- Чому: Код реалізує всі 8 кроків майстра, включаючи калькулятор ціни та MEN-класифікацію, з підключенням через кіоск-плитку.
- Доказ: wizards/camp_create_wizard.py:67-77 — step field defines 8 steps: type, basics, logo, dates, accommodation, frame_day, program, capacity
- Доказ: wizards/camp_create_wizard.py:350 — _compute_price_per_child method implements price calculator
- Доказ: wizards/camp_create_wizard.py:513 — action_apply_computed_price applies calculated price
- Доказ: controllers/kiosk.py:53-54 — kiosk tile 'Nowy obóz' links to action_camp_create_wizard
- Доказ: wizards/camp_create_wizard.py:97 — MEN classification field present
- Доказ: tests/__init__.py:34 — test_role_organizator_create_camp test imported
- Чекер: підтверджено: Докази чітко підтверджують реалізацію всіх ключових аспектів вимоги: 8 кроків майстра (що відповідає '8+ кроків' та охоплює всі заявлені концепції), MEN-класифікацію, калькулятор ціни, вхід з кіоску т

### [F-SALE-4] · TZ.md:255 · ТЗ заявляє: ✅
- Чому: Моделі, плани, генерація, UI та ACL для fayna.payment.installment повністю присутні в коді.
- Доказ: models/commercial.py:1667 — _name = "fayna.payment.installment" (модель існує)
- Доказ: models/commercial.py:1487 — _name = "fayna.payment.installment.plan" (план існує)
- Доказ: models/commercial.py:1455 — _name = "fayna.payment.installment.plan.line" (лінія плану існує)
- Доказ: models/commercial.py:1603 — return self.env["fayna.payment.installment"].create(vals_list) (генерація записів)
- Доказ: views/sale_order_installment_views.xml:18 — page name="installments" string="Raty / Розстрочка" (UI в меню)
- Доказ: security/ir.model.access.csv:61-62 — ACL для fayna.payment.installment (admin+user)
- Чекер: підтверджено: Докази аналітика чітко підтверджують, що `fayna.payment.installment.*` та пов'язані компоненти (плани, UI, ACL) існують у коді, що повністю відповідає вимозі 'ЗАЛИШЕНО'.

### [F-OPS-3] · TZ.md:291 · ТЗ заявляє: ✅
- Чому: Код повністю відповідає ТЗ: розширено loyalty.program, додано fayna_rule_type, перевизначено _program_check_compute_points, присутні banda/platinum/gold.
- Доказ: models/commercial.py:157 — _inherit = "loyalty.program" (розширення нативного loyalty.program)
- Доказ: models/commercial.py:159 — fayna_rule_type = fields.Selection(...) (додано поле fayna_rule_type)
- Доказ: models/commercial.py:669 — def _program_check_compute_points(self, programs) (override методу)
- Доказ: models/commercial.py:671 — res = super()._program_check_compute_points(programs) (виклик super)
- Доказ: models/commercial.py:45-47 — banda/platinum/gold значення (2000/1000/500)
- Доказ: models/commercial.py:337-339 — Selection з banda/platinum/gold
- Чекер: підтверджено: Усі частини вимоги (розширення loyalty.program, fayna_rule_type, override _program_check_compute_points, наявність banda/platinum/gold) підтверджені відповідними рядками коду та пробами.

### [Q8-2] · TZ.md:393 · ТЗ заявляє: ✅
- Чому: All claimed functionality (wizard field, event landing, onchange prefill, tests) is present and verified by probes.
- Доказ: models/camp.py:190 — vacation_form field on event model
- Доказ: models/operations.py:3402-3412 — _onchange_event_vacation_form prefills notification from event
- Доказ: wizards/camp_create_wizard.py:85,696 — wizard field and create vals include vacation_form
- Доказ: tests/test_vacation_forms.py:30-48 — test for full MEN catalog in selections
- Доказ: tests/test_role_organizator_create_camp.py:180-203 — test_r61_vacation_form_lands_on_event_and_notification verifies landing and prefill
- Чекер: підтверджено: Усі пункти вимоги R6.1 (поле в майстрі, збереження на подію, префіл сповіщення з onchange та гардом каталогу, а також відповідні тести) підтверджені наданими пробами та посиланнями аналітика.

### [Q8-4] · TZ.md:395 · ТЗ заявляє: ✅
- Чому: Тест test_compute_sudo_consistency існує та імпортований, а compute_sudo=True широко застосовано у всіх моделях, що відповідає заявленому статусу ✅.
- Доказ: models/regulamin.py:126 — compute_sudo=True з коментарем 'група має бути консистентна зі stored all_signed (R10)'
- Доказ: tests/__init__.py:14 — test_compute_sudo_consistency імпортовано в тестовому пакеті
- Доказ: models/commercial.py:201,355,570,582,1296,1322 — compute_sudo=True у 6 місцях
- Доказ: models/emergency.py:117,220,231,241,251,258,269,306,319,899,905,912 — compute_sudo=True у 12 місцях
- Доказ: models/incident_card.py:66,366,506,520,529 — compute_sudo=True у 5 місцях
- Доказ: models/nutrition.py:337, participant.py:1053,1067,1083, reports.py:317,322,328,334 — compute_sudo=True у 8 місцях
- Чекер: підтверджено: Докази чітко підтверджують вимогу R10 compute_sudo, включаючи пряме посилання на R10 у коментарі до compute_sudo=True та наявність відповідного тесту test_compute_sudo_consistency.

### [Q8-10] · TZ.md:401 · ТЗ заявляє: ✅
- Чому: Пакет документів виховника реалізовано: модель, звіт, views, меню та тести присутні.
- Доказ: models/teczka_ko.py:31 — class CampTeczkaKO(models.Model)
- Доказ: models/teczka_ko.py:394 — report_action for checklist
- Доказ: reports/teczka_reports.xml:8 — action_report_teczka_ko_checklist
- Доказ: views/teczka_views.xml:7 — tree view
- Доказ: views/menus.xml:181 — menu item
- Доказ: tests/test_regulamin_teczka.py:232 — test_teczka_karty_percent
- Чекер: підтверджено: Докази чітко підтверджують реалізацію 'Пакету документів виховника' (teczka_ko) через наявність моделі, звітів, інтерфейсу користувача (views, menu) та тестів, що відповідає вимозі.

### [API-1] · TZ.md:651 · ТЗ заявляє: ✅
- Чому: Усі збіги /api/v1 — лише в документації (CHANGELOG, PLAN, TZ) як історичні записи, у коді збігів немає, що відповідає заявленому статусу ✅.
- Доказ: docs/PLAN.md:72 — P4.3: api.py /api/v1/* прибрано, 0 споживачів, ADR native portal /my/*
- Доказ: docs/TZ.md:386 — /api/v1 IDOR (✅ видалено)
- Доказ: docs/TZ.md:651 — сам ТЗ підтверджує видалення, верифікація grep = 0
- Чекер: підтверджено: Проба `grep "/api/v1"` по всьому проєкту (`path: "."`) показує збіги лише в документації (CHANGELOG.md, docs/PLAN.md, docs/TZ.md). Це підтверджує, що в коді збігів немає, що відповідає критерію верифі

### [API-2] · TZ.md:653 · ТЗ заявляє: ✅
- Чому: Усі заявлені контракти (/my/*, /camp/kiosk/*, set_lang з валідацією, /admin/dashboard, login-as з audit-логом) підтверджені в коді контролерів.
- Доказ: controllers/portal.py:46 — @http.route(["/my", "/my/home"], type="http", auth="user", website=True)
- Доказ: controllers/kiosk.py:299 — @http.route("/camp/kiosk/set_lang", ...)
- Доказ: controllers/kiosk.py:336 — rejected set_lang to inactive/unknown lang (валідація active-мов)
- Доказ: controllers/admin.py:99 — @http.route("/admin/dashboard", type="http", auth="user", website=True)
- Доказ: controllers/admin.py:557 — @http.route("/admin/login-as", type="http", auth="user", website=True)
- Доказ: controllers/admin.py:577 — self._log_access("login_as", ...) (audit-лог)
- Чекер: підтверджено: Усі заявлені контракти (/my/*, /camp/kiosk/*, set_lang з валідацією, /admin/dashboard, login-as з audit-логом) підтверджені наданими пробами та вердиктом аналітика. Хоча `auth="user"` не є 'organizato

---

# ВЕРИФІКАЦІЯ CLAUDE (гейт, 2026-08-03, вибірка 9 пунктів власним grep)

## Підтверджено
- **[F-RODO-4] DRIFT — РЕАЛЬНИЙ.** Erasure-wizard на res.partner нема ні в порталі (єдиний збіг — docstring participant.py:1055), ні у fayna_rodo_compliance (тека wizards/ відсутня; є лише cron анонімізації consent-логів `_cron_anonymize_expired_consent_logs`). ✅-«доказ» у ТЗ був grep-збігом docstring — доказ не відповідав твердженню. Дія: новий пункт беклогу + виправити статус F-RODO-4 у ТЗ на 🔴 (wizard) / ✅ (лог-анонімізація).

## Спростовано (хибні мінуси дешевих аналітиків)
- **[Q8-18]** «фікс (а) не застосовано» — ХИБНО: migrations/17.0.4.1.5/post-migrate.py:33-41 містить `->>'en_US'` + COALESCE pl_PL; коміт 0717cc1 (INC-215 фікси закомічені разом з .6/.7/.8).
- **[F-RODO-1]** «моделі нема» — ХИБНО: модель у сусідньому репо fayna_rodo_compliance, портал використовує (camp_escort.py:107,181; commercial.py:539).
- **[F-VAT-1]** «калькулятора нема» — ХИБНО щодо маржі: budget.py:5-68 (дві маржі, vat_marza-категорії). Перевірити лишається стик калькулятор→list_price.
- **[R-1]** «групи Parent нема» — Parent = нативна base.group_portal (groups.xml:262) за задумом ADR-22.
- **[Q8-1]** «Powrót нема» — є /camp/kiosk/back_visible (kiosk.py:279-285); але селектор табору/бренд/кольори (R5/R8/R9) пробами не підтверджені — пакет лишається у черзі.
- **[F-MY-1]** — /my/escort існує (escort_portal.py:56, окремий контролер); /my/consents і /my/training у контролерах відсутні (це підтверджую).
- **[PR-6]** NOT_DONE — мисреад політики: власна рекрутація = ухвалений R13-півот; міграція на hr_recruitment = крок 3 черги §8 п.17 за «ок» власника.

## Системний висновок по лупу
Дешеві аналітики мають перекіс у ХИБНІ МІНУСИ з двох причин: (1) сліпа зона scope — комплект поставки = 6 репо, луп бачив лише fayna_camp_portal; (2) вузькі grep-токени. Тому: список DONE (9) — надійний (чекер гейтував докази); NOT_DONE/PARTIAL — читати як «не знайдено в ЦЬОМУ репо цими пробами», перед виконанням пункту перевіряти сусідні репо. Наступний прогін лупа: додати у file_tree() сусідні модулі комплекту.
