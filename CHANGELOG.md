# Changelog

All notable changes to `fayna_campscout` are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: Odoo `17.0.MAJOR.MINOR.PATCH`.

---

## [17.0.0.4.0] — 2026-04-27

### Added
- Portal sidebar nav (inherit `portal.portal_layout`) with links: Діти та картки, Щоденні новини, Документи, Програма лояльності, Звернення. Active state per `page_name`.
- `portal_my_home_support` tile card on `/my` home (priority 68, `support_count` badge via `/my/counters`).
- `support_count` in `_prepare_home_portal_values`: reads `camp.support.request` for current partner, specific `(AccessError, MissingError)` guard.
- "Звернення" breadcrumb in `portal_breadcrumbs_campscout` for `page_name == 'support'`.
- `portal_participant_reviews_cta` template — inherits `fayna_camp_qualification.portal_participant_detail`, injects reviews section with per-registration CTA (Залишити відгук / Відгук на модерації / Відгук опубліковано) based on `reg.review_state`.
- 2 `HttpCase` smoke tests: `test_portal_home_loads` (GET /my → 200), `test_portal_stories_loads` (GET /my/stories → 200).

---

## [17.0.0.1.0] — 2026-04-24

### Added
- Initial scaffold (empty-but-installable).
- Feature flag `fayna_campscout.active` (default `False`) per master TZ §2 Strangler Fig.
- Canonical tooling (pre-commit, pyproject, GitHub Actions CI).
- Placeholder tests (install + flag + deps sanity).
- `docs/TZ.md` per-module TZ aligned with CAMPSCOUT_MASTER_TZ.md §16 Phase 7.

### Notes
- Module is **inert** until Phase 7 implementation lands.
