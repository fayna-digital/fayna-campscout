# Кабінет Клієнта — стан розробки

**Модуль:** `fayna_campscout` (Thin Client)
**Роль:** aggregator / UI-shell — hero home page, shared SCSS design tokens, legal docs gateway, nav між секціями кабінету.

Канонічна назва кабінету (юр. документи): **"Кабінет клієнта"** (UA) / **"Panel Klienta"** (PL) — джерело `regulamin-panelu-klienta.html`, `rodo.html`.

Повна картинка — у `docs/CABINET_STATUS.md` кожного з залежних модулів:
- [`fayna-camp-qualification`](https://github.com/VladSh77/fayna-camp-qualification/blob/main/docs/CABINET_STATUS.md) — діти, картка, підпис
- [`fayna-camp-sales`](https://github.com/VladSh77/fayna-camp-sales/blob/main/docs/CABINET_STATUS.md) — замовлення, архів, checkout
- [`fayna-rodo-compliance`](https://github.com/VladSh77/fayna-rodo-compliance/blob/main/docs/CABINET_STATUS.md) — RODO consent у кабінеті

## Цільова структура (ТЗ §2.6.2c + §2.7)

| Route | Власник | Стан |
|---|---|---|
| `/my` | `fayna_campscout` | ✅ hero + 3 nav-blocks |
| `/my/stories` | `fayna_campscout` | ✅ премiумна list-сторінка |
| `/my/loyalty` | `fayna_campscout` | ✅ tier hero + progress + stats + ladder |
| `/my/documents` | `fayna_campscout` | ✅ 4 static cards (RODO/child-protection/panel-terms/general) + dynamic versions |
| `/my/participants` | `fayna_camp_qualification` | ⚠️ list існує, styled not premium |
| `/my/participants/<id>` | `fayna_camp_qualification` | ⚠️ 4/5 секцій працюють (картка/поточний/архів/майбутні), відсутня inbox |
| `/my/participants/<id>/sign` | `fayna_camp_qualification` | ✅ canvas signature + PDF |
| `/my/bookings` | `fayna_camp_sales` | ❌ scaffold |
| `/my/bookings/new` | `fayna_camp_sales` | ❌ scaffold |
| `/my/bookings/archived` | `fayna_camp_sales` | ❌ scaffold |
| `/my/profile` | core Odoo | ✅ stock |

## Що реалізовано в цьому модулі (2026-04-24)

### ✅ `/my` home — hero shell

- Override `_prepare_portal_layout_values` у `controllers/portal.py` — інжектить `cs_participants`, `cs_active_regs`, `cs_upcoming_regs`, `cs_has_hero`, `cs_today`, `cs_parent_only` через `.sudo()` з явним `partner.id` scope.
- Inherit template `portal.portal_my_home` з XPath `//div[hasclass('o_portal_docs')] position="before"` — hero банер "Ваші діти у CampScout".
- Data-attribute `data-cs-parent-only='1'` на `.o_portal_my_home` — CSS ховає стандартні Odoo cards (Замовлення/Рахунки/Безпека) для portal-only батьків.
- Секції hero: active-camp alert (якщо дитина зараз в таборі), children strip (картки з ім'ям + віком → link до `/my/participants/<id>`), upcoming camps list, 3 nav-blocks (Стoрії/Лояльність/Документи).
- Override `portal.portal_layout` — `<h3>My account</h3>` → `<h3>Кабінет клієнта</h3>` per legal docs.

### ✅ `/my/stories`

- Route у `controllers/portal.py` — filter stories за parent's events (privacy: тільки stories з зареєстрованих подій).
- Template `portal_stories` — cs-page shell, cs-story-card з pill type-badge (daily_log/adventure/team_moment/lesson_learned і т.д.).
- `.sudo()` з explicit partner scope.

### ✅ `/my/loyalty` — **ядро знижок**

- Route + template з per-child cards.
- **Gradient tier hero** per tier (bronze/silver/gold/platinum — справжні металеві градієнти).
- Великий discount % front-and-center.
- Progress bar до наступного tier ("ще 2 табори до Золотого").
- 3 stats: taborиv / балів / з нами з року.
- Tier ladder card пояснює програму.

### ✅ `/my/documents`

- 4 static cards → зовнішні legal docs на `/docs/rodo`, `/docs/child-protection`, `/docs/regulamin-panelu`, `/docs/terms`.
- Dynamic secondary cards з `legal.document.version` (через `fayna_legal_versioning`).
- Premium cards з emoji icons, hover lift, CampScout orange CTA.

### ✅ Shared SCSS — `static/src/scss/portal_hero.scss`

Доступний globally через `web.assets_frontend` → інші модулі (`fayna_camp_qualification`) можуть reuse.

Design tokens:
- `$cs-orange: #ff7a00` (primary)
- `$cs-green: #20ac41` (success)
- Tier gradients
- `$cs-card-radius: 12px`, `$cs-shadow-soft/hover`

Reusable classes:
- `.cs-page`, `.cs-page-back`, `.cs-back-link`, `.cs-page-header`, `.cs-page-title`, `.cs-page-subtitle`
- `.cs-empty-state`, `.cs-empty-icon`
- `.cs-doc-card`, `.cs-doc-icon`, `.cs-doc-body`, `.cs-doc-title`, `.cs-doc-desc`, `.cs-doc-cta`
- `.cs-story-card`, `.cs-story-head`, `.cs-story-meta`, `.cs-story-type[data-type=...]`
- `.cs-loyalty-card[data-tier]`, `.cs-loyalty-hero`, `.cs-loyalty-progress`, `.cs-loyalty-stats`, `.cs-tier-ladder`

Mobile media queries `<576px` — адаптація hero, tier-row grid стеком, зменшені шрифти.

## Поточний вигляд (2026-04-24)

### `/my` home

```
Кабінет клієнта
──────────────
Ваші діти у CampScout
[Anna Testova, 10 років]   ← clickable card
──────────────
📖 Щоденні історії    🏆 Лояльність     📄 Документи
   Звіти вожатих       Рівні та знижки    Умови, політики...
   Переглянути →       Переглянути →      Переглянути →
```

### `/my/loyalty` (Silver для test.parent)

Gradient срібляста карта Anna з:
- 5% знижка великим шрифтом
- Progress bar "До Золотого залишилось 2 табори" (2/4)
- 2 таборів / 150 балів / 2025 з нами
- Нижче — tier ladder з 4 rows (bronze/silver/gold/platinum gradient pills)

### `/my/stories` + `/my/documents`

Premium cards, back-link, page header/subtitle, consistent typography.

## Known issues

- ⚠️ **JS console warning** `documentsCounterEl null` — counter з `fayna_camp_qualification.orphan_registration_count` повертався у AJAX /my/counters response коли не requested; виправлено у `fayna-camp-qualification` commit `f443288`.
- ⚠️ **i18n** — всі user-facing strings жорстко українською. Для польської версії сайту потрібен English source + uk_UA.po + pl_PL.po. Не зроблено.
- ⚠️ **Test data російською** — `scripts/create_test_parent.py` мав російський seed; виправлено, оновлено в БД.

## Next steps (що ще дописувати)

1. **CTA «Забронювати новий табір»** у hero + children strip + future camps → `/shop?child_id=<id>` (pre-filled)
2. **i18n** — English source + uk_UA.po + pl_PL.po
3. **Avatar placeholder** у children strip — SVG з initialами замість лише тексту
4. Синхронізація дизайну з `/my/participants/<id>` у `fayna_camp_qualification` (pass SCSS tokens)
5. **Inbox** на home — anons непрочитаних повідомлень від organizatora (потребує mail.thread integration у qualification)

## Технічні рішення (lessons learned)

- `home()` route у Odoo 17 викликає `_prepare_portal_layout_values()`, НЕ `_prepare_home_portal_values()`. Останній — тільки AJAX `/my/counters`. Override неправильного hook дає values тільки для counter badges, не для HTML render. **Див. commit `e21792f`.**
- Template inherit з `customize_show="True"` + priority 25 = канонічний pattern (як `sale.portal_my_home_sale`).
- Portal user має record rules на `camp.participant` + `event.registration`, але не має access на `event.event` (core model). Рішення — `.sudo()` з явним filter по `partner.id` (стандартний Odoo portal pattern).
- `.o_portal_docs` НЕ можна ховати через `t-if` — JS видаляє `.o_portal_doc_spinner` всередині, crash при null. Замість того — `data-cs-parent-only='1'` на `.o_portal_my_home` + CSS `.o_portal_category { display: none }`.
- Counter overrides у `_prepare_home_portal_values` ОБОВ'ЯЗКОВО wrap в `if "X" in counters` — інакше response contains keys з відсутнім DOM element → TypeError у portal.js.
- `<tree colors="...">` removed in Odoo 17 → use `decoration-info/success/warning/danger`. Plus decoration referenced field must be rendered in tree (or `invisible="1"`).
- `__init__.py` у корені модуля мусить import ВСІ subdirs (models, controllers, wizards) — пропустиш і views впадуть ParseError бо моделі не зареєстровані.

## Reference

- Master TZ §2.6.2c (site map), §2.7 (Parent Cabinet vision), §2.7.2 (5 секцій /my/participants/<id>)
- Legal docs canonical name: `camp/knowledge-base/legal/regulamin-panelu-klienta.html`
- Design tokens memory: `feedback_odoo_staging_first.md`, `project_campscout_brand_colors.md`
