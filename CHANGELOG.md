# Changelog

All notable changes to `fayna_camp_portal` are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html) — Odoo `17.0.MAJOR.MINOR.PATCH`.

---

## [17.0.2.0.0] - 2026-04-30

Major release: hotel-pattern consolidation + 6-role RBAC + native chat + SMS three-tier + admin dashboard + Ustawa Kamilka.

### Added
- Module renamed from `fayna_campscout` to `fayna_camp_portal` ([TZ §9](../fayna-digital-docs/contributing/FAYNA_CAMPSCOUT_TZ.md))
- 6 role groups: Organizator (top-level PL Rozp. MEN 30.03.2016), Sales, Kierownik, Wychowawca, Instructor, Parent — plus orthogonal Medical Officer opt-in ([security/security.xml](security/security.xml))
- Record rules per model (~15 rules) for fine-grained access scope ([security/record_rules.xml](security/record_rules.xml))
- Field-level `groups=` on medical fields (allergies, medications, doctor_notes) ([models/camp_participant.py](models/camp_participant.py))
- Auto-subscribers on 6 models via `_message_auto_subscribe_followers` ([models/](models/))
- `discuss.channel` auto-create per `event.event` (camp shift staff team chat) ([models/event_event.py](models/event_event.py))
- SMS three-tier (CRITICAL/IMPORTANT/INFO) via `fayna_sms_base.dispatcher` -> `fayna_sms_turbosms` ([models/sms_dispatcher.py](models/sms_dispatcher.py))
- 12 SMS templates (6 staff + 6 child broadcast) ([data/sms_templates.xml](data/sms_templates.xml))
- Wychowawca SMS broadcast wizard with cost guard (100/300 monthly limits) ([wizards/sms_broadcast_wizard.py](wizards/sms_broadcast_wizard.py))
- `camp.staff.sms.log` immutable broadcast audit (7y retention) ([models/camp_staff_sms_log.py](models/camp_staff_sms_log.py))
- Ustawa Kamilka 2024 special handling: `severity='kamilka'` bypasses opt-in, 5-min escalation cron, immutable `camp.incident.notification.log` ([models/camp_incident.py](models/camp_incident.py), [data/cron_data.xml](data/cron_data.xml))
- `event.event.deputy_kierownik_id` backup contact for escalation ([models/event_event.py](models/event_event.py))
- `camp.participant.child_mobile` + `sms_consent` (RODO art.7 explicit consent) ([models/camp_participant.py](models/camp_participant.py))
- `/admin/dashboard` with 7 KPI sections ([controllers/admin_dashboard.py](controllers/admin_dashboard.py))
- 4 view-as routes (`/admin/as-{kierownik,wychowawca,instructor,parent}`) ([controllers/admin_view_as.py](controllers/admin_view_as.py))
- `camp.admin.access.log` immutable RODO art.30 audit (7y retention) ([models/camp_admin_access_log.py](models/camp_admin_access_log.py))
- `res.users._get_login_action()` override -> organizator lands on dashboard ([models/res_users.py](models/res_users.py))
- Portal chatter on `/my/participants/<id>`, `/my/stories/<id>`, `/my/loyalty`, `/my/support/<id>` ([controllers/portal.py](controllers/portal.py))
- Migrated 4 absorbed models: `camp.story` (from `fayna_camp_stories`), `camp.transport` (from `fayna_camp_transport`), `camp.analytics.snapshot` + `camp.marketing.report` + `camp.stats.snapshot` (from `fayna_camp_reports`), 4 vozhatyi models (from `fayna_camp_vozhatyi_school`) ([models/](models/))
- Polish translation `pl_PL.po` (374 msgids, ~100% coverage) ([i18n/pl_PL.po](i18n/pl_PL.po))
- Ukrainian translation `uk_UA.po` (374 msgids, ~100% coverage) ([i18n/uk_UA.po](i18n/uk_UA.po))
- App icon (CampScout brand orange logo, 150x150 PNG) ([static/description/icon.png](static/description/icon.png))

### Changed
- Manifest `name` -> "Портал CampScout" (was "Fayna CampScout") ([__manifest__.py](__manifest__.py))
- Manifest `version` -> `17.0.2.0.0` (was `17.0.1.0.0`) ([__manifest__.py](__manifest__.py))
- Wizard SMS broadcast routes via `fayna.sms.dispatcher` (our wrapper) instead of native Odoo `sms.api` — replaces dependency on third-party `kw_sms_turbosms` ([wizards/sms_broadcast_wizard.py](wizards/sms_broadcast_wizard.py))
- New manifest depend: `fayna_sms_base` (our multi-provider SMS layer) ([__manifest__.py](__manifest__.py))

### Fixed
- INC-014: model load order — `operations` before `emergency` in `models/__init__.py` (`camp.staff` must exist before emergency `_inherit`) ([models/__init__.py](models/__init__.py))
- INC-015: `post_init_hook` idempotent — DELETE source rows before UPDATE to prevent `UniqueViolation` on `ir_model_data` ([hooks.py](hooks.py))
- INC-016: `selection_add` `ondelete='cascade'` for kamilka severity (was invalid `'set default'` / `'severe'`) ([models/camp_incident.py](models/camp_incident.py))
- INC-017: `camp.journal` field is `author_id` (was incorrectly `staff_id` in record rule) ([security/record_rules.xml](security/record_rules.xml))
- INC-018: `is_published` -> `website_published` in `event.event` domain (Odoo 17 stored field name) ([controllers/portal.py](controllers/portal.py))
- Removed orphan reference to deleted `fayna_camp_qualification.portal_participant_detail` template ([templates/](templates/))

### Removed
- Dependency on `kw_sms_turbosms` / `kw_sms_api` (Kitworks Systems third-party paid module) — replaced by Fayna stack `fayna_sms_base` + `fayna_sms_turbosms` ([__manifest__.py](__manifest__.py))
- 16 absorbed `fayna_camp_*` modules (consolidated into single hotel-pattern module per [TZ §9](../fayna-digital-docs/contributing/FAYNA_CAMPSCOUT_TZ.md))

### Security
- Audit logs `camp.admin.access.log` and `camp.staff.sms.log` are IMMUTABLE (override `write` and `unlink` to raise `UserError`) ([models/camp_admin_access_log.py](models/camp_admin_access_log.py), [models/camp_staff_sms_log.py](models/camp_staff_sms_log.py))
- View-as uses `with_user()` (preserves ACL/record rules) — NOT `sudo()` (would bypass RODO controls) ([controllers/admin_view_as.py](controllers/admin_view_as.py))
- Ustawa Kamilka SMS bypass `sms_opt_in` — legal basis GDPR art. 6.1.d (vital interest) ([models/camp_incident.py](models/camp_incident.py))
- Field-level access on RODO art. 9 special-category health data (allergies, medications, doctor_notes, chronic_conditions) ([models/camp_participant.py](models/camp_participant.py))

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
