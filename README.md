# Odoo 17 Camp Portal — Complete Children's Summer Camp Management

![Odoo Version](https://img.shields.io/badge/Odoo-17.0%20Community-purple)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![PL Law](https://img.shields.io/badge/PL%20Law-Rozp.%20MEN%202016-red)
![License](https://img.shields.io/badge/License-LGPL--3-green.svg)
![Status](https://img.shields.io/badge/Status-Active%20Development-orange)

**Developed by [Fayna Digital](https://www.fayna.agency) for the Polish camp organization market**
**Author: Volodymyr Shevchenko**

---

Single hotel-pattern Odoo 17 module that delivers the complete operational stack for a Polish children's summer camp organizer — from public catalog and parent portal to qualification cards, kuratorium notifications, dziennik zajęć, emergency protocol (Ustawa Kamilka 2024), staff training and SMS broadcasts.

Reference deployment: [CampScout](https://campscout.eu) — child summer camps in Poland.

---

## Features

- **Hotel-pattern architecture** — one installable module covers the entire camp domain (catalog, registrations, qualification cards, operations, emergency, kuratorium, training, loyalty, SMS); horizontal concerns (RODO, SMS base) live in sibling modules
- **Six-role RBAC** — Organizator / Sales / Kierownik / Wychowawca / Instructor / Parent with field-level ACL on RODO Art.9 health data and record rules scoped per shift
- **Native Odoo chat + auto-subscribers** — every camp shift auto-creates a `discuss.channel` (kierownik + staff); qualification cards, journals and incidents auto-subscribe the right partners on create/write so notifications dispatch without manual subscribe
- **SMS three-tier priority** — `CRITICAL` (incidents, unsigned card <3d) / `IMPORTANT` (journal comments, daily reports) / `INFO` (stories, marketing) routed through `fayna_sms_base` → TurboSMS / Twilio with per-partner `sms_opt_in` consent enforcement
- **Ustawa Kamilka 2024 escalation** — `severity='kamilka'` triggers `CRITICAL_OVERRIDE` SMS that bypasses opt-in (GDPR art.6.1.d vital interest); 5-minute cron escalates to deputy kierownik / organizator if primary did not acknowledge; immutable Kuratorium audit trail
- **Admin dashboard with view-as** — Organizator lands on `/admin/dashboard`, can `/admin/as-{role}` impersonate any role using `with_user()` (preserves ACL, never sudo); every impersonation logged to `camp.admin.access.log` (RODO art.30, 7-year retention)
- **Polish camp law compliance** — Karta kwalifikacyjna (5 sections per Rozp. MEN 30.03.2016), Dziennik zajęć (Załącznik 5), Program Wypoczynku (Załącznik 9), Kuratorium notification (Załącznik 1), staff KRK + RPS verification
- **Multi-language** — native Odoo `.po` translation pipeline with `i18n/uk_UA.po` and `i18n/pl_PL.po` (Ukrainian + Polish), all user-facing strings wrapped in `_()`
- **Parent portal + REST API** — `/my` hero with active and upcoming registrations, qualification card flow, stories, documents, loyalty; `/api/v1/*` JSON endpoints for the mobile app

---

## Architecture

```
fayna_camp_portal/
├── __manifest__.py                       # v17.0.2.0.0 · LGPL-3 · application=True
├── hooks.py                              # post_init_hook — seed data, default config
├── models/
│   ├── camp.py                           # camp.category, camp.activity, camp.room.type + event.event extensions
│   ├── participant.py                    # camp.participant (5-section qualification card, immutability after sign-off)
│   ├── operations.py                     # camp.report, camp.journal, camp.staff (+ certs), camp.daily.report, camp.program (Załącznik 9), camp.dziennik, camp.kuratorium.*
│   ├── nutrition.py                      # camp.nutrition.plan + EU-14 allergens (Regulation 1169/2011)
│   ├── emergency.py                      # camp.incident.report (7-state machine, 18 action types)
│   ├── commercial.py                     # camp.support.ticket, camp.installment, loyalty integration, reviews
│   ├── training.py                       # extends slide.channel — wychowawca 36h MEN-compliant course
│   ├── training_vozhatyi.py              # standalone PL-MEN 36h/10h tracker (parallel to slide-based path)
│   ├── transport.py                      # camp.transport — bus / coach booking per shift
│   ├── stories.py                        # camp.story — newsfeed for parents (migrated from fayna_camp_stories)
│   ├── reports.py                        # camp.analytics.snapshot, camp.stats.snapshot, marketing report wizard
│   ├── sms.py                            # SMS adapter (TurboSMS via fayna_sms_base)
│   ├── sms_notify.py                     # three-tier priority override of mail.thread._notify_thread_by_sms
│   ├── incident_kamilka.py               # severity='kamilka' overlay + CRITICAL_OVERRIDE + 5-min escalation
│   ├── incident_notification_log.py      # immutable Kuratorium audit log
│   ├── event_backup_contact.py           # event.event deputy backup contact (Kamilka escalation target)
│   ├── event_channel_create.py           # auto-create discuss.channel per shift; sync members on staff change
│   ├── auto_subscribe_extensions.py      # _message_auto_subscribe_followers on participant / journal / incident
│   ├── portal_mixin_extensions.py        # portal.mixin on participant / support / loyalty for /my chatter
│   ├── res_partner_inherit.py            # sms_opt_in (universal — works for portal users)
│   ├── res_users_inherit.py              # Organizator login redirect to /admin/dashboard
│   ├── admin_access_log.py               # camp.admin.access.log — RODO art.30 register
│   ├── participant_sms_extension.py      # SMS consent + reachable mobile resolution
│   ├── staff_sms_extension.py            # wychowawca-side SMS broadcast hooks
│   ├── staff_sms_log.py                  # camp.staff.sms.log — append-only audit
│   └── campscout_portal.py               # portal route helpers
├── controllers/
│   ├── portal.py                         # /my home override (Odoo 17 _prepare_home_portal_values is AJAX-only)
│   ├── admin.py                          # /admin/dashboard + /admin/as-{role} view-as endpoints
│   └── api.py                            # /api/v1/* JSON endpoints for mobile app
├── views/
│   ├── camp_views.xml                    # camp.category, activity, room.type, event.event extensions
│   ├── participant_views.xml             # qualification card form (5 sections)
│   ├── operations_views.xml              # journal, program, staff, kuratorium, daily reports
│   ├── nutrition_views.xml
│   ├── emergency_views.xml
│   ├── commercial_views.xml              # support, installments, loyalty, reviews
│   ├── training_views.xml                # slide-based course
│   ├── training_vozhatyi_views.xml       # standalone 36h tracker
│   ├── transport_views.xml
│   ├── stories_views.xml
│   ├── reports_views.xml
│   ├── sms_views.xml
│   ├── staff_sms_views.xml
│   ├── admin_views.xml                   # camp.admin.access.log tree/form
│   └── menus.xml
├── templates/
│   ├── portal_templates.xml              # /my hero + participants + stories + loyalty
│   ├── portal_chatter.xml                # portal.message_thread on /my/<model>/<id>
│   ├── website_templates.xml             # public catalog + booking widget
│   └── admin_dashboard.xml               # /admin/dashboard QWeb (KPI cards + drill-down)
├── security/
│   ├── groups.xml                        # 6 roles (Organizator/Sales/Kierownik/Wychowawca/Instructor/Parent) + 3 specialist roles (medical/HR/nutrition/emergency responder/manager)
│   ├── ir.model.access.csv               # CRUD per group per model
│   └── record_rules.xml                  # ir.rule — per-shift scope, parent sees own children only
├── data/
│   ├── ir_config_parameter.xml           # SMS limits, Kuratorium settings
│   ├── cron.xml                          # daily reminders (qualification card 14d/7d/3d)
│   ├── cron_kamilka_escalation.xml       # 5-min Ustawa Kamilka escalation cron
│   ├── sms_templates.xml                 # parent-facing templates
│   ├── sms_child_templates.xml           # child/wychowawca-facing templates
│   └── fayna_sms_provider_data.xml       # default TurboSMS provider seed
├── wizards/
│   └── staff_sms_composer.py             # wychowawca → group SMS broadcast (RODO + cost guard)
├── i18n/
│   ├── fayna_camp_portal.pot             # source pot
│   ├── uk_UA.po                          # Ukrainian
│   └── pl_PL.po                          # Polish
├── tests/
│   ├── test_scaffold.py
│   ├── test_campscout.py
│   └── test_campscout_extended.py
├── static/src/
│   ├── scss/portal_hero.scss
│   └── css/portal.css
└── docs/                                 # per-module TZ + ARCHITECTURE notes
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | Odoo 17 Community |
| Database | PostgreSQL 14+ |
| Frontend | OWL + QWeb + Bootstrap 5 |
| SMS Provider | TurboSMS via `fayna_sms_base` / `turbosms` adapter |
| Background tasks | Odoo cron + `bus.bus` longpolling |
| i18n | Native Odoo `.po` (`uk_UA`, `pl_PL`) |
| Testing | Odoo test framework + `pytest` |
| RODO/GDPR | `fayna_rodo_compliance` (consent log + 7y retention) |
| Module version | 17.0.2.0.0 |
| License | LGPL-3 |

---

## Installation

### 1. Clone into custom-addons

```bash
cd /opt/<client>/custom-addons
git clone https://github.com/VladSh77/fayna_camp_portal.git
git clone https://github.com/VladSh77/fayna-rodo-compliance.git
git clone https://github.com/VladSh77/fayna_sms_base.git
```

### 2. Install dependencies first

`fayna_camp_portal` declares `fayna_rodo_compliance` and `fayna_sms_base` as hard dependencies; install them before this module so the consent dual-write and SMS dispatcher exist before the post_init hook fires.

```bash
docker stop <client>_web

docker run --rm \
    -v /opt/<client>/custom-addons:/mnt/custom-addons:ro \
    -v /opt/<client>/odoo-data:/var/lib/odoo:rw \
    -v /opt/<client>/config:/etc/odoo:rw \
    --network <client>_net \
    odoo:17.0 \
    odoo -c /etc/odoo/odoo.conf -d <db> \
    -i fayna_rodo_compliance,fayna_sms_base --stop-after-init --no-http
```

### 3. Install this module

```bash
docker run --rm \
    -v /opt/<client>/custom-addons:/mnt/custom-addons:ro \
    -v /opt/<client>/odoo-data:/var/lib/odoo:rw \
    -v /opt/<client>/config:/etc/odoo:rw \
    --network <client>_net \
    odoo:17.0 \
    odoo -c /etc/odoo/odoo.conf -d <db> \
    -i fayna_camp_portal --stop-after-init --no-http

docker start <client>_web
```

Or via UI: **Apps → Update Apps List → search `Camp Portal` → Install**.

---

## Configuration

### Step 1 — SMS provider token

Configure TurboSMS (or alternative provider) credentials via **Settings → Technical → System Parameters** (developer mode):

| Key | Value |
|-----|-------|
| `fayna_sms_base.turbosms_token` | TurboSMS API token from https://my.turbosms.ua |
| `fayna_sms_base.default_sender` | Sender alias registered with the provider |
| `fayna_camp_portal.sms_kierownik_monthly_limit` | Monthly broadcast cap for kierownik (default `300`) |
| `fayna_camp_portal.sms_wychowawca_monthly_limit` | Monthly broadcast cap for wychowawca (default `100`) |

The Organizator group bypasses the per-role monthly cap (legitimate operational override; still logged).

### Step 2 — Kuratorium settings

Per Rozp. MEN 30.03.2016 §3, every camp shift must be reported to the regional Kuratorium Oświaty in advance.

| Key | Value |
|-----|-------|
| `fayna_camp_portal.kuratorium_voivodeship` | Voivodeship code (e.g. `mazowieckie`) |
| `fayna_camp_portal.kuratorium_office_email` | Email address of the regional Kuratorium |
| `fayna_camp_portal.kuratorium_organizator_nip` | Organizator NIP (legal entity ID) |
| `fayna_camp_portal.kuratorium_advance_days` | Days before camp start to send notification (default `21`) |

### Step 3 — Branding

Logo, brand colour and email footer are read from the active company. The portal hero (`/my`) uses `static/src/scss/portal_hero.scss` design tokens — override via a child theme module rather than editing the SCSS in place.

---

## Usage

### Parent flow (`/my/*`)

1. Parent logs in (portal user) — login redirects to `/my`
2. Hero block lists active and upcoming registrations, each child as a card
3. **Qualification card** — parent fills Sections I-II (own data + child data + medical disclosure); sign-off triggers immutability on those fields (further changes go through the `amend()` flow)
4. **Stories** — `/my/stories` shows shift-scoped news posted by wychowawca
5. **Documents** — `/my/documents` exposes signed PDFs (qualification card snapshot, regulamin, RODO consent receipts)
6. **Loyalty** — `/my/loyalty` shows points + tier + active coupons
7. **Mobile app** — JSON endpoints under `/api/v1/*` (auth=user)

### Kierownik flow (own camp dashboard)

1. Kierownik (camp shift director) logs in — sees only their own shift via record rule `camp.staff.event_id == self.event_id`
2. **Daily report** — submit `camp.daily.report` (head count, weather, incidents) — auto-notifies organizator
3. **Journal** — `camp.journal` per day; sign-off locks Section III of every participant card under their charge
4. **Sections IV-V** — sign at end of shift (locks group dynamics + health summary)
5. **Załącznik 9 approval** — `camp.program` → submit → manager approves
6. **Kuratorium checklist** — tick off Załącznik 1 items; system blocks shift start if unchecked

### Wychowawca flow (own group + dziennik + SMS broadcast)

1. Wychowawca logs in — sees only own group via record rule
2. **Dziennik zajęć** — `camp.dziennik` activity log per group per day (Załącznik 5)
3. **Section VI of qualification card** — observations + recommendations per child; sign-off locks
4. **SMS broadcast** — wizard from `camp.staff` form; recipients auto-derived from group, RODO-filtered (`sms_consent=True` + reachable mobile), monthly cap enforced, audit row written
5. **Discuss channel** — auto-joined to the shift's private group chat with kierownik + co-staff

### Organizator flow (`/admin/dashboard` + view-as)

1. Organizator logs in (top-level role per Rozp. MEN §2.1) — login redirect to `/admin/dashboard`
2. Server-rendered dashboard with KPI cards: registrations, revenue, occupancy, unsigned cards, open incidents, upcoming kuratorium deadlines
3. **Drill-down** — click a camp → see attendance, staff, journal entries, incidents, daily reports
4. **View-as** — `/admin/as-kierownik?event_id=...` renders the kierownik portal with `with_user(target_user)` — ACL of the target role is preserved, the Organizator does NOT gain write-bypass on RODO Art.9 fields
5. Every view-as call writes a row to `camp.admin.access.log` (RODO art.30 register) before the render — even if the render fails the trace exists

---

## Polish Camp Law Compliance (Rozp. MEN 30.03.2016)

### Karta kwalifikacyjna (5 sections)

`camp.participant` model holds the qualification card per Załącznik 6 of the regulation:

| Section | Owner | Locked after |
|---------|-------|--------------|
| I. Camp metadata (name, dates, place, organizator) | Organizator (auto from `event.event`) | Always read-only for parent |
| II. Child + parent data + medical disclosure | Parent | `qualification_signed=True` |
| III. Adaptation notes, health events, medication given | Kierownik | `iii_completed_date` set |
| IV. Objectives achieved + group dynamics | Kierownik | `iv_kierownik_signature` |
| V. Health summary + recommendations | Kierownik | `iv_kierownik_signature` (joint with IV) |
| VI. Wychowawca observations | Wychowawca | `vi_wychowawca_signature` |

Post-signoff edits require a fresh signed record + archive of the previous one (`amend()` flow). Frozen field set: `_PROTECTED_AFTER_SIGNOFF` in `models/participant.py`.

### Dziennik zajęć (Załącznik 5)

`camp.dziennik` per group per day — activities, attendance, notes. Wychowawca signs each entry; once signed, `write()` is blocked except for `notes` field.

### Program Wypoczynku (Załącznik 9)

`camp.program` — multi-day structured program (theme + objectives + daily activities). State machine `draft → submitted → approved`. Approval requires `group_fayna_camp_manager`. Approved programs are read-only except by manager override.

### Kuratorium notification (Załącznik 1)

`camp.kuratorium.notification` — bundle of organizator info, shift dates, location sketch, staff list with KRK + RPS verification, NNW insurance proof, regulamin. Auto-deadline: 21 days before shift start; cron blocks shift start state if not submitted.

### Ustawa Kamilka 2024 (vital interest reporting)

Polish Ustawa o przeciwdziałaniu zagrożeniom przestępczością na tle seksualnym i ochronie małoletnich (August 2024) requires immediate notification on incidents threatening child life or sexual safety.

`camp.incident.report` extends `severity` with `'kamilka'` value:
- Forces SMS dispatch with priority `CRITICAL_OVERRIDE` regardless of recipient `sms_opt_in` (legal basis: GDPR art.6.1.d vital interest)
- 5-minute escalation cron — if primary kierownik did not acknowledge the SMS, the deputy kierownik (or organizator if no deputy) is notified
- Description must be ≥ 50 chars + `incident_datetime` mandatory (Kuratorium audit demands detail)
- Every notification logged to `camp.incident.notification.log` — append-only, no `unlink()` even by superuser

---

## Technical Deep Dive

### SMS notification flow

```
Model post (e.g. camp.incident.report.message_post)
      │
      ▼
mail.thread._notify_thread (stock Odoo)
      │
      ▼
mail.thread._notify_thread_by_sms          ← override in sms_notify.py
      │
      ├── Read class attribute `_notify_priority`
      │   (CRITICAL / IMPORTANT / INFO / CRITICAL_OVERRIDE)
      │
      ├── If priority NOT in SMS_DISPATCH_PRIORITIES → return (bell+email only)
      │
      ├── Filter recipients:
      │     CRITICAL_OVERRIDE → bypass sms_opt_in (GDPR art.6.1.d)
      │     CRITICAL          → only partners with sms_opt_in=True
      │
      ▼
fayna.sms.dispatcher (sibling module)
      │
      ├── Resolve provider by recipient country (PL → TurboSMS, UA → TurboSMS UA)
      ├── Cost guard (monthly cap per role)
      ├── Audit row in fayna.sms.log
      │
      ▼
TurboSMS HTTP API → recipient phone
```

### Auto-subscribe flow on `event.event` create

```
event.event.create({...})
      │
      ▼
event_channel_create.EventEventChannel.create:
      │
      ├── 1. Collect partner_ids = [kierownik.partner_id] + [staff.partner_id ...]
      │
      ├── 2. Create discuss.channel(
      │         name=event.name,
      │         channel_type='group',
      │         camp_event_id=event.id,
      │     ).with_context(mail_create_nosubscribe=True)
      │
      ├── 3. channel.add_members(partner_ids=partner_ids)
      │      (Odoo 17 → discuss.channel.member records, NOT channel_partner_ids)
      │
      └── 4. Auto-subscribe followers chain:
              event → kierownik
              participant → parent_partner_id + event.kierownik
              camp.journal → kierownik + wychowawca
              camp.incident → kierownik + organizator + (kamilka → deputy)
```

### Ustawa Kamilka escalation flow

```
T+0:00  Incident reported with severity='kamilka'
            │
            ▼
        sms_notify dispatches CRITICAL_OVERRIDE SMS to kierownik
        (bypasses sms_opt_in — vital interest)
            │
            │ kierownik does NOT mark mail.notification as read within 5 min
            ▼
T+5:00  cron_kamilka_escalation fires (every 1 min, checks 5+ min old)
            │
            ├── Resolve backup_contact:
            │     event.event.deputy_kierownik_id (if set)
            │     ELSE → organizator (group_camp_organizator)
            │
            ├── Dispatch CRITICAL_OVERRIDE SMS to backup
            │
            ├── Set incident.backup_notified_at = now()
            │
            └── Append camp.incident.notification.log row
                 (immutable — no write/unlink even by superuser)

T+30:00 If incident still 'open' → cron sends Kuratorium notification
        (incident.kuratorium_notified_at)
```

### Admin view-as flow

```
GET /admin/as-kierownik?event_id=42&reason=Support+ticket+#123
      │
      ▼
CampscoutAdmin._check_admin()
      │ (raise AccessError if not group_camp_organizator)
      ▼
CampscoutAdmin._log_access(
    impersonated_role='kierownik',
    target_user=event.user_id,
    target_event=event,
    reason=...,
    ip_address=request.httprequest.remote_addr,
    session_id=request.session.sid,
)
      │ (sudo create — RODO art.30 register, never silently skipped)
      ▼
request.env(user=target_user).render('portal.portal_my_home', values)
      │ (with_user — NOT sudo — preserves target ACL + ir.rule)
      ▼
Browser sees the kierownik view; Organizator did NOT gain write-bypass
on RODO Art.9 medical fields (medical_officer group still required).
```

---

## Local Development

```bash
# Clone module + dependencies
git clone https://github.com/VladSh77/fayna_camp_portal.git
git clone https://github.com/VladSh77/fayna-rodo-compliance.git
git clone https://github.com/VladSh77/fayna_sms_base.git

# Spin up ephemeral Odoo with all three mounted
docker run -d --name camp_dev \
    -v $(pwd)/fayna_camp_portal:/mnt/custom-addons/fayna_camp_portal \
    -v $(pwd)/fayna-rodo-compliance:/mnt/custom-addons/fayna_rodo_compliance \
    -v $(pwd)/fayna_sms_base:/mnt/custom-addons/fayna_sms_base \
    -p 8069:8069 \
    odoo:17.0

# Open http://localhost:8069 → create db → install fayna_camp_portal
# (dependencies install transitively)

# Run tests
docker exec camp_dev odoo \
    -c /etc/odoo/odoo.conf -d <db> \
    --test-enable --stop-after-init -u fayna_camp_portal

# Update Polish translations
docker exec camp_dev odoo \
    -c /etc/odoo/odoo.conf -d <db> \
    --i18n-export=/mnt/custom-addons/fayna_camp_portal/i18n/pl_PL.po \
    --modules=fayna_camp_portal --language=pl_PL --stop-after-init
```

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `Module fayna_rodo_compliance not found` | Hard dependency missing in addons_path | Clone `fayna-rodo-compliance` repo into custom-addons; restart Odoo and update Apps List |
| `_prepare_home_portal_values not called for /my hero` | Odoo 17 only invokes it on `/my/counters` AJAX | Already handled — `controllers/portal.py::home()` overrides initial render with `_prepare_campscout_hero_values()` |
| Qualification card edits silently reverted | Field is in `_PROTECTED_AFTER_SIGNOFF` after sign-off | Use the `amend()` flow — creates a new signed record + archives the previous one |
| Kamilka SMS not bypassing `sms_opt_in` | Model missing `_notify_priority = "CRITICAL_OVERRIDE"` class attribute | Set the attribute on the model (or extend `incident_kamilka.py` overlay) — `sms_notify.py` reads it via `getattr(type(self), "_notify_priority", None)` |
| `discuss.channel` not auto-created on shift create | Odoo 17 renamed `mail.channel` → `discuss.channel`; old `channel_partner_ids` writes silently no-op | Use `channel.add_members(partner_ids=[...])` — already handled in `event_channel_create.py` |
| `/admin/dashboard` returns 403 for Organizator | User missing `group_camp_organizator` (assigned via Settings → Users → Groups) | Assign `Organizator Wypoczynku (top-level)` in user form — implies all sub-roles |
| Translations not picked up after `.po` edit | Odoo caches compiled `.mo` until module load | Restart Odoo with `-u fayna_camp_portal --i18n-overwrite` |
| Wychowawca SMS broadcast hits cap unexpectedly | Monthly counter is per-role per-staff per calendar month | Bump `fayna_camp_portal.sms_wychowawca_monthly_limit` config parameter, or use Organizator override |

---

## Role-Based Access Reference

| Role | Read-Write | Read-Only | Hidden |
|------|------------|-----------|--------|
| **Organizator Wypoczynku** | All models (via `base.group_system` + implied roles); admin dashboard; view-as any role | — | — |
| **Camp Sales Manager** | Catalog (camp.category, camp.activity, product.template), `sale.order`, `camp.support.ticket`, marketing reports, public stories | Camp shifts (read), participants (count only) | Medical fields, kuratorium, dziennik, daily reports, incidents |
| **Camp Manager** | `camp.program` (Załącznik 9 approval), full incident lifecycle, all kuratorium docs | — | — |
| **Camp Kierownik** | Own shift's `camp.journal`, `camp.daily.report`, `camp.staff`, qualification card Sections III-V | Other shifts (read), participants of own shift only (via record rule) | Other shifts' medical/journal data |
| **Camp Wychowawca** | Own group's `camp.dziennik`, qualification card Section VI, SMS broadcast (capped) | Allergies + emergency contact of own group's children | Medications, doctor_notes, other groups, incidents (unless responder) |
| **Camp Instructor** | Own activity assignments (`camp.activity` where `responsible_id == self`) | Activity-relevant medical (e.g. asthma for running) of attendees | Full medical, journal, incidents |
| **Camp Medical Officer** | RODO Art.9 health fields (`allergies`, `medications`, `chronic_conditions`, `doctor_notes`) | Qualification card metadata | Sales, marketing, support |
| **Camp Nutrition Officer** | `camp.participant.diet` (RODO Art.9 dietary), `camp.nutrition.plan`, EU-14 allergens | Participant card metadata | Medical (non-dietary), incidents |
| **Camp HR Manager** | Staff certifications (KRK, RPS, course certs) per Rozp. MEN §4 | Staff list | Participants, incidents, sales |
| **Emergency Responder** | Create/update `camp.incident.report` + `camp.incident.action` | Closed incidents (read-only) | Close/reopen incidents |
| **Emergency Manager** | Full incident lifecycle (close, reopen, override) | — | — |
| **Parent** (portal) | Own qualification card Sections I-II (until signed), own contact data | Own children's status, stories of own shifts, documents, loyalty | Other parents' data, internal journal, kuratorium docs |

Record rules (`security/record_rules.xml`) enforce per-shift scoping for staff roles and per-parent scoping for portal users; `with_user()` impersonation in admin view-as preserves these rules — Organizator only "sees what the role would see".

---

## License

LGPL-3 — see [LICENSE](LICENSE)

---

*Developed by [Fayna Digital](https://www.fayna.agency) · Volodymyr Shevchenko*
