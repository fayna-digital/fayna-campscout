# fayna_campscout — Per-module TZ

Scope: master TZ §16 Phase 7. Owner: Fayna Digital (Volodymyr Shevchenko).

## Mission

Thin client-specific data layer for CampScout (product records, legal pages, brand).

Client-specific records ONLY (21 product.template + events + FAQ + legal copy + brand theme).

## Non-goals

- Anything outside Phase 7 scope per master TZ.
- Production deployment before all 26 modules are on Hetzner staging with
  human QA green (see `feedback_prod_deploy_gate.md` — ЗАКОН).

## Incremental milestones

### M.0 Scaffold ✅ (2026-04-24)

Empty module, installable, feature flag seeded `False`, CI green.

### M.1 — TBD

First concrete behaviour. Details land when Phase 7 starts active development.

## Quality (per master TZ §4.6 ЗАКОН)

- pre-commit gates green on every commit (ruff + ruff-format + OCA + bandit + gitleaks + base hooks)
- tests ≥ 70% coverage on critical paths
- QUALITY_AUDIT_*.md entry before each phase gate promotion

## Rollback

- Flip `fayna_campscout.active` → `False`.
- If still misbehaving, uninstall the module; core Odoo tables remain untouched.

## Reference

- Master TZ `CAMPSCOUT_MASTER_TZ.md` §16 Phase 7
- Sister modules per deps
- **[LEGAL_REQUIREMENTS.md](LEGAL_REQUIREMENTS.md)** — PL legal norms extracted from ITW Niezbędnik Kierownika Wypoczynku 2024 (nutrition %, group sizes, transport, accident procedure, water safety)
