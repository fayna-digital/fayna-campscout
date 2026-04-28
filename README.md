# CampScout Portal (Thin Client)

![Odoo Version](https://img.shields.io/badge/Odoo-17.0%20Community-purple)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-LGPL--3-green.svg)
![Status](https://img.shields.io/badge/Status-Live-brightgreen)

**Розроблено [Fayna Digital](https://www.fayna.agency) для платформи CampScout.**
**Автор: Volodymyr Shevchenko**

---

## Призначення

Портальний thin client для батьків: особистий кабінет `/my` з дашбордом учасників, щоденними stories від вихователів, документами для підписання та програмою лояльності. Окремий REST JSON API для мобільного застосунку (авторизація, учасники, stories, документи, повідомлення). Модуль виступає точкою інтеграції між платформою CampScout і батьківським досвідом.

## Поточний стан

| Параметр | Значення |
|---|---|
| Версія | 17.0.0.4.0 |
| Фаза проекту | Phase 7 з 9 |
| Статус | Live |
| Staging | ✅ |

## Моделі

| Модель | Опис |
|---|---|
| `campscout.portal.session` | Трекінг сесії батька в порталі: кількість дітей, активні табори, непрочитані повідомлення, очікувані дії. |
| `campscout.portal.menu` | Кастомізація меню порталу залежно від регіону (PL/UA). |

## Контролери

| Контролер | Маршрути |
|---|---|
| `controllers/portal.py` | `home()` override для `/my` — рендерить hero-блок кабінету батька; `/my/participants`, `/my/stories`, `/my/documents`, `/my/loyalty` |
| `controllers/api.py` | REST JSON API для мобільного: авторизація, учасники, stories, документи, повідомлення |

## Залежності

- `base`, `website`, `sale`, `portal`, `mail`
- `fayna_camp_template`
- `fayna_camp_qualification`
- `fayna_camp_loyalty`
- `fayna_camp_stories`
- `fayna_legal_versioning`
- `fayna_rodo_compliance`

## Безпека

### ACL (`ir.model.access.csv`)

Портальні користувачі мають обмежений доступ лише до власних сесій.

### Правила доступу до рядків (`ir.rule`)

| Правило | Умова |
|---|---|
| Portal: власна сесія | `partner_id = user.partner_id` — батько бачить тільки свій запис |

## Тести

2 тести: `test_campscout.py` (TransactionCase — portal menu, portal session values), `test_scaffold.py`. Мінімальне тестування, потребує розширення.

```bash
docker exec campscout_web odoo -c /etc/odoo/odoo.conf -d campscout \
    --test-enable --stop-after-init --no-http -u fayna_campscout
```

## Локалізація

`i18n/uk_UA.po` + `i18n/pl_PL.po`

## Ліцензія

LGPL-3 — © 2026 Fayna Digital
