# fayna_camp_portal — CLAUDE.md

## Що це
**Єдиний** модуль управління таборами CampScout (архітектурний pivot 2026-06-07).
Hotel-pattern: весь camp-specific код в одному модулі замість 21 окремих `fayna_camp_*`.

**Версія:** `17.0.2.0.0` | **GitHub:** `VladSh77/fayna-campscout` (branch: main)
**Staging:** `/opt/campscout/custom-addons/fayna_camp_portal/` — встановлено ✅
**Prod:** НЕ задеплоєний (staging-only на 2026-06-07)

## Що входить у модуль
- **6-role RBAC:** Organizator / Sales / Kierownik / Wychowawca / Instructor / Parent
- **Portal /my/\*:** кабінет батьків — учасники, лояльність, stories, документи
- **Backend views:** реєстрації, учасники, харчування, транспорт, операції, звіти
- **SMS:** 3-рівнева система (CRITICAL/IMPORTANT/INFO) через `fayna_sms_base`
- **Ustawa Kamilka 2024:** 5-хв ескалація cron + immutable Kuratorium notification log
- **Кваліфікаційна картка:** 5 секцій MEN law + підпис батьків + PDF
- **Щоденник занять** (Załącznik 5), **Program Wypoczynku** (Załącznik 9)
- **Admin dashboard** /admin/dashboard з view-as impersonation

## Залежності
```
base, mail, portal, website, sale, event, event_sale, account, loyalty, sms
fayna_rodo_compliance  ← RODO consent, art.9 field-level access
fayna_sms_base         ← SMS dispatcher (TurboSMS adapter)
```
**НЕ залежить** від `fayna_sms_turbosms` (той залежить від `fayna_sms_base`).

## Де що лежить
```
models/camp.py             ← головна модель camp.camp
models/participant.py      ← camp.participant (дитина в таборі)
models/portal_mixin_extensions.py ← portal /my/* helpers
models/incident_kamilka.py ← Ustawa Kamilka escalation
controllers/portal.py      ← /my/* routes
controllers/admin.py       ← /admin/dashboard
templates/portal_templates.xml ← QWeb для /my/*
docs/TZ.md                 ← технічне ТЗ модуля
docs/CABINET_STATUS.md     ← статус кабінету батьків (детально)
```

## Deploy (staging → prod — коли буде готово)
```bash
ssh campscout
cd /opt/campscout/custom-addons/fayna_camp_portal
git pull && sudo chmod -R o+rX .
docker exec campscout_web odoo -c /etc/odoo/odoo.conf -d campscout \
  -u fayna_camp_portal --stop-after-init
docker restart campscout_web
```

## Архітектурний контекст
- **Strangler Fig:** поступово замінює `campscout_management` (старий монолітний модуль)
- **campscout_management** ще активний на prod — паралельно доки не мігруємо
- `fayna_rodo_compliance` — окремо (cross-project reusable)
- `fayna_sms_base` / `fayna_sms_turbosms` — окремо (SMS infrastructure)
- Всі інші `fayna_camp_*` репо — застарілі після pivot; код переноситься сюди

## Важливо
- Не додавай нові `fayna_camp_*` модулі — новий функціонал = сюди
- Перед будь-якою зміною: прочитай `docs/CABINET_STATUS.md` для portal-частини
- Mobile audit обов'язковий для будь-яких змін у `/my/*` templates
- `sudo chmod -R o+rX` (capital X!) після кожного git pull на сервері
