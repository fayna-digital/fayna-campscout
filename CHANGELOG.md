# Changelog

All notable changes to `fayna_camp_portal` are documented here.

## 17.0.4.1.7 — 2026-07-05
- Reuse S1 пара 6 (найбільша, 713 LOC): три системи обліку тренінгів кадри злиті в одну — keeper `camp.staff.training.record` (extends native `slide.channel`, website_slides вже в depends — ADR-001/Community-only). Видалено `fayna.vozhatyi.training(+module+certificate)` та `vozhatyi.training.record` (models/training_vozhatyi.py, views/training_vozhatyi_views.xml, 16 ACL-рядків, 6+3 record-rules — усе прибрано). Keeper отримав: `online_platform` course type, `session_start_date/end_date/location/instructor_id` (офлайн-логістика), printable QWeb-сертифікат (`action_print_certificate`), portal ACL+record rules (штат на umowa zlecenie часто без internal-акаунту). Module-level гранулярність НЕ перенесена окремою моделлю — вже нативно покрита `slide.channel`/`slide.slide` (сильніший reuse). Бонус-фікс: keeper мав `expired` стан і ручну action_expire(), але жодного cron, що його вмикав, — мертва функція; тепер `_cron_expire_training_records` підключений (data/cron.xml), консолідує обидва легасі expiry-crons в один. migrations/17.0.4.1.7: SQL+ORM (get-or-create 5 slide.channel-каналів по типу курсу) перенос за ir_model_data-мітками + `ON CONFLICT` на unique_partner_channel (ідемпотентно); notes/модулі — chatter-провенанс. git grep сиріт = 0 (крім provenance-коментарів і синтетичного lossless-тесту).

## 17.0.4.1.6 — 2026-07-05
- Reuse S1 пара 5: legacy camp.program (+camp.program.activity, обидві були UI-сиротами — 0 menuitem, 0 тестів) злито в camp.program.structured (+camp.program.day +camp.program.activity.line): state-machine (draft→approved→scheduled→ongoing→completed→cancelled), theme/incidents/photos/staff_ids/description/participant_count/is_published/weather_plan перенесені на день; risk_water/risk_heights + time-order constraint перенесені на activity.line. camp.schedule.entry НЕ мігрується/НЕ видаляється — grep-доказ на ітерації показав окрему живу фічу (product-template маркетинговий «типовий день», не event-instance план); STEP1_TZ дозволяє корегувати keeper на ітерації. migrations/17.0.4.1.6: SQL-перенос за ir_model_data-мітками (ідемпотентно), model/views/2 ACL-рядки видалені, git grep сиріт = 0 (крім migrations/ і синтетичного lossless-тесту).

## 17.0.4.1.5 — 2026-07-05
- Reuse S1 пара 4: camp.participant.diet злито в camp.diet.profile (dietary_restrictions+notes → notes, алергени через m2m; migrations/: перенос + display_name; ФІКС: додано ACL nutrition officer на keeper — цю роль раніше пускала лише видалена модель; модель/views/action/ACL видаленої моделі прибрані, сиріт 0 поза i18n).

## 17.0.4.1.4 — 2026-07-04
- Reuse S1 пара 3: legacy camp.nutrition злито в camp.menu.day (порт diet-лічильників/allergy_notes/state+tracking/prepared_by/confirm-флоу; migrations/: мапінг snacks→afternoon_snack, notes-злиття; ACL кухні/керівника; НОВЕ menuitem «Jadłospis dzienny» — обидві моделі були UI-сиротами).

## 17.0.4.1.3 — 2026-07-04
- Reuse S1 пара 2: camp.journal злито в camp.daily.report (active+7р retention-cron перенесені й ПІДКЛЮЧЕНІ — у журналі архів-метод був мертвий без ir.cron; autofill camp.report → з денних рапортів; migrations/: записи → kierownik_notes, вкладення перепідвішені; model/views/ACL/rules/menu видалені, сиріт 0).

## 17.0.4.1.2 — 2026-07-04
- Reuse S1 пара 1: camp.stats.snapshot злито в camp.analytics.snapshot (total_capacity перенесено, migrations/-перенос даних, cron/ACL/views видалені, git grep сиріт = 0).
- FIX: щоденний analytics-cron мовчки падав 100% (домен по неіснуючих полях camp.participant.event_id/qualification_state; ValueError ковтався try/except) — знайдено новим тестом keeper'а.

## [17.0.3.0.0] — 2026-06-23 … 2026-06-25 — Native parent signoff + escort + kiosk + relicense

### Added
- **camp.escort** — Indywidualna asysta / konwój: модель, кабінет `/my/escort` (форма+canvas-підпис), двомовні PL/UA звіти dozwoła+RODO (art.13), zgoda na pomoc medyczną. Q9 `escort_required` конфіг.
- **Нативний підпис картки батьками** — `/my/participants/<id>` (detail+submit+sign), canvas signature pad → `sign_qualification`, read-only+PDF після підпису. Виводить стару bs-форму (Strangler).
- **Підпис організатора** — `res.company.camp_organizer_signature` + рендер у karta-звіті.
- **Тести критичних шляхів** — 26 requirement-driven (signed_by=real-parent, ACL write=0, ownership, immutability, RODO-лог, escort). `tests/test_signoff_rodo.py` + escort/registration/rodo.
- **Kiosk shell (TZ §4)** — повноекранний кіоск-режим (`views/kiosk_views.xml`, `kiosk_app.js`, `kiosk.scss`, systray-перемикачі kiosk↔Odoo + back) для роботи кадри на турнусі з планшета.
- **Тултіпи абревіатур (UX recognition-not-recall)** — PL-розшифровки в views: KRK → «Zaświadczenie o niekaralności (KRK)», RPS → «Rejestr Sprawców Przestępstw na tle seksualnym (RPS)», BEP → «Próg rentowności (BEP)», KO → «Kuratorium Oświaty», VAT-marża → «procedura VAT marża art. 119».

### Changed
- **Перехід на OPL-1** — `LICENSE` переписано на Odoo Proprietary License v1.0 (модуль bespoke для CampScout, без redistribution/SaaS). Manifest `license="OPL-1"` + © Fayna Digital / Volodymyr Shevchenko у заголовках. README/Tech Stack/badge приведено до OPL-1, прибрано застарілі version-рядки (17.0.2.0.0 → 17.0.3.0.0).
- **i18n pl_PL** — оновлено польські переклади (374+ рядків), заголовки кабінету батьків `/my/*` польською.

### Fixed
- **Юр-доказ підпису:** `signed_by` = справжній батько (не superuser) через `signed_by_id` + controlled-sudo після ownership-check. Латентний баг (підпис не працював для portal-user через ACL write=0 + read на res.partner дитини).
- **/my/documents 500** → graceful guard на `KeyError` (legal.document.version може бути не встановлено, Strangler).
- **Дашборд організатора** — фікс рендеру `/admin/dashboard` (KPI-карти + drill-down).
- Биті лінки кабінету: `/my/bookings`→`/my/orders`, `/my/participants/new`→бронювання, +`/my/support` routes.
- Картка переведена на `cs-*` візуальні патерни кабінету + mobile-first.

### Notes
- Верифіковано end-to-end на staging (прод-копія): підпис як portal-user, рендер обох станів, усі 9 /my/* routes=200, 26 тестів PASS, ruff clean.
- ADR-2: seats-from-sales НЕ реплікуємо (нативні реєстрації покривають; verified 209 open regs).
- Migration scripts (lossless, rehearsed): populate_from_bs / migrate_bs_signatures / populate_escort_from_204 / detach_campscout_management.


Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html) — Odoo `17.0.MAJOR.MINOR.PATCH`.

> **Нотатка (2026-06-08):** частина файлових посилань у записах нижче вказує на дорефакторні імена
> (`camp_participant.py`, `sms_dispatcher.py`, `camp_incident.py`, `admin_dashboard.py`, `sms_broadcast_wizard.py`).
> Файли відтоді перейменовано — актуальні: `participant.py`, `sms.py`, `incident_kamilka.py`, `admin.py`,
> `wizards/staff_sms_composer.py`. Історичні записи лишено як знімок; виправлення посилань — у [PLAN.md](docs/PLAN.md) P5.3.

---

## [Unreleased]

### Changed
- Приведення до REPO_STANDARD: `docs/TZ.md` переписано зі scaffold-шаблону на spec-driven (6 областей) з реальним змістом 27 моделей; додано `docs/PLAN.md` (dependency graph + фази P1–P5 + checkpoints); CLAUDE.md — банер #4ZONES; `.gitignore` — ігнор секретів. Doc-only, код не змінювався.

---

## [17.0.2.0.0] - 2026-04-30

Major release: hotel-pattern consolidation + 6-role RBAC + native chat + SMS three-tier + admin dashboard + Ustawa Kamilka.

### Added
- Module renamed from `fayna_campscout` to `fayna_camp_portal` ([TZ §9](../fayna-digital-docs/contributing/FAYNA_CAMPSCOUT_TZ.md))
- 6 role groups: Organizator (top-level PL Rozp. MEN 30.03.2016), Sales, Kierownik, Wychowawca, Instructor, Parent — plus orthogonal Medical Officer opt-in ([security/groups.xml](security/groups.xml))
- Record rules per model (~15 rules) for fine-grained access scope ([security/record_rules.xml](security/record_rules.xml))
- Field-level `groups=` on medical fields (allergies, medications, doctor_notes) ([models/participant.py](models/participant.py))
- Auto-subscribers on 6 models via `_message_auto_subscribe_followers` ([models/](models/))
- `discuss.channel` auto-create per `event.event` (camp shift staff team chat) ([models/event_channel_create.py](models/event_channel_create.py))
- SMS three-tier (CRITICAL/IMPORTANT/INFO) via `fayna_sms_base.dispatcher` -> `fayna_sms_turbosms` ([models/sms.py](models/sms.py))
- 12 SMS templates (6 staff + 6 child broadcast) ([data/sms_templates.xml](data/sms_templates.xml))
- Wychowawca SMS broadcast wizard with cost guard (100/300 monthly limits) ([wizards/staff_sms_composer.py](wizards/staff_sms_composer.py))
- `camp.staff.sms.log` immutable broadcast audit (7y retention) ([models/staff_sms_log.py](models/staff_sms_log.py))
- Ustawa Kamilka 2024 special handling: `severity='kamilka'` bypasses opt-in, 5-min escalation cron, immutable `camp.incident.notification.log` ([models/incident_card.py](models/incident_card.py), [data/cron.xml](data/cron.xml))
- `event.event.deputy_kierownik_id` backup contact for escalation ([models/event_backup_contact.py](models/event_backup_contact.py))
- `camp.participant.child_mobile` + `sms_consent` (RODO art.7 explicit consent) ([models/participant.py](models/participant.py))
- `/admin/dashboard` with 7 KPI sections ([controllers/admin.py](controllers/admin.py))
- 4 view-as routes (`/admin/as-{kierownik,wychowawca,instructor,parent}`) ([controllers/admin.py](controllers/admin.py))
- `camp.admin.access.log` immutable RODO art.30 audit (7y retention) ([models/admin_access_log.py](models/admin_access_log.py))
- `res.users._get_login_action()` override -> organizator lands on dashboard ([models/res_users_inherit.py](models/res_users_inherit.py))
- Portal chatter on `/my/participants/<id>`, `/my/stories/<id>`, `/my/loyalty`, `/my/support/<id>` ([controllers/portal.py](controllers/portal.py))
- Migrated 4 absorbed models: `camp.story` (from `fayna_camp_stories`), `camp.transport` (from `fayna_camp_transport`), `camp.analytics.snapshot` + `camp.marketing.report` + `camp.stats.snapshot` (from `fayna_camp_reports`), 4 vozhatyi models (from `fayna_camp_vozhatyi_school`) ([models/](models/))
- Polish translation `pl_PL.po` (374 msgids, ~100% coverage) ([i18n/pl_PL.po](i18n/pl_PL.po))
- Ukrainian translation `uk_UA.po` (374 msgids, ~100% coverage) ([i18n/uk_UA.po](i18n/uk_UA.po))
- App icon (CampScout brand orange logo, 150x150 PNG) ([static/description/icon.png](static/description/icon.png))

### Changed
- Manifest `name` -> "Портал CampScout" (was "Fayna CampScout") ([__manifest__.py](__manifest__.py))
- Manifest `version` -> `17.0.2.0.0` (was `17.0.1.0.0`) ([__manifest__.py](__manifest__.py))
- Wizard SMS broadcast routes via `fayna.sms.dispatcher` (our wrapper) instead of native Odoo `sms.api` — replaces dependency on third-party `kw_sms_turbosms` ([wizards/staff_sms_composer.py](wizards/staff_sms_composer.py))
- New manifest depend: `fayna_sms_base` (our multi-provider SMS layer) ([__manifest__.py](__manifest__.py))

### Fixed
- INC-014: model load order — `operations` before `emergency` in `models/__init__.py` (`camp.staff` must exist before emergency `_inherit`) ([models/__init__.py](models/__init__.py))
- INC-015: `post_init_hook` idempotent — DELETE source rows before UPDATE to prevent `UniqueViolation` on `ir_model_data` ([hooks.py](hooks.py))
- INC-016: `selection_add` `ondelete='cascade'` for kamilka severity (was invalid `'set default'` / `'severe'`) ([models/incident_card.py](models/incident_card.py))
- INC-017: `camp.journal` field is `author_id` (was incorrectly `staff_id` in record rule) ([security/record_rules.xml](security/record_rules.xml))
- INC-018: `is_published` -> `website_published` in `event.event` domain (Odoo 17 stored field name) ([controllers/portal.py](controllers/portal.py))
- Removed orphan reference to deleted `fayna_camp_qualification.portal_participant_detail` template ([templates/](templates/))

### Removed
- Dependency on `kw_sms_turbosms` / `kw_sms_api` (Kitworks Systems third-party paid module) — replaced by Fayna stack `fayna_sms_base` + `fayna_sms_turbosms` ([__manifest__.py](__manifest__.py))
- 16 absorbed `fayna_camp_*` modules (consolidated into single hotel-pattern module per [TZ §9](../fayna-digital-docs/contributing/FAYNA_CAMPSCOUT_TZ.md))

### Security
- Audit logs `camp.admin.access.log` and `camp.staff.sms.log` are IMMUTABLE (override `write` and `unlink` to raise `UserError`) ([models/admin_access_log.py](models/admin_access_log.py), [models/staff_sms_log.py](models/staff_sms_log.py))
- View-as uses `with_user()` (preserves ACL/record rules) — NOT `sudo()` (would bypass RODO controls) ([controllers/admin.py](controllers/admin.py))
- Ustawa Kamilka SMS bypass `sms_opt_in` — legal basis GDPR art. 6.1.d (vital interest) ([models/incident_card.py](models/incident_card.py))
- Field-level access on RODO art. 9 special-category health data (allergies, medications, doctor_notes, chronic_conditions) ([models/participant.py](models/participant.py))

---

## [17.0.1.0.0] - 2026-04-30

Initial hotel-pattern release.

### Added
- Initial absorption of camp models from `campscout_management` monolith
- 50 models across 14 files (camp/participant/operations/emergency/nutrition/dziennik/kuratorium/program/loyalty/training/commercial/sms/campscout_portal) ([models/](models/))
- 6 portal routes: `/my`, `/my/stories`, `/my/loyalty`, `/my/documents`, `/my/participants`, `/my/support` ([controllers/portal.py](controllers/portal.py))
- 6 JSON API endpoints: `/api/v1/camps`, `/api/v1/participants`, `/api/v1/stories`, `/api/v1/loyalty`, `/api/v1/checkin`, `/api/v1/emergency` ([controllers/api.py](controllers/api.py))
- `post_init_hook` for `ir.model.data` ownership migration from absorbed modules ([hooks.py](hooks.py))
- Initial test suite: `test_campscout`, `test_campscout_extended`, `test_scaffold` ([tests/](tests/))
