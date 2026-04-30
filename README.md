# Fayna CampScout

![Odoo Version](https://img.shields.io/badge/Odoo-17.0%20Community-purple)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-LGPL--3-green.svg)
![Status](https://img.shields.io/badge/Status-Live-brightgreen)

**Розроблено [Fayna Digital](https://www.fayna.agency)**
**Автор: Volodymyr Shevchenko**

---

## Що це

Єдиний Odoo-модуль для управління дитячим табором CampScout.
Один install — отримуєш все необхідне для роботи табору.

Побудований на базі нативних модулів Odoo 17: `event`, `sale`, `loyalty`, `slide`, `sms`, `website_rating`.

---

## Можливості

### Табори та реєстрація
- Табори як `event.event` (заїзди) + `product.template` (магазин)
- Онлайн запис через website shop
- Управління місцями та ціноутворенням

### Учасники (діти)
- Кваліфікаційна картка дитини — 5 секцій за польським законом
- RODO consent log (через `fayna_rodo_compliance`)
- Медичні дані з ACL-обмеженням (тільки медперсонал)
- Immutability після підпису керівником

### Операції табору
- Журнал дня (dziennik zajęć)
- Програма wypoczynku — Załącznik 9 (обов'язковий документ PL)
- Склад персоналу по змінах
- Розклад активностей
- Звіт керівника (sprawozdanie kierownika)
- Сповіщення кураторіуму

### Харчування
- Плани харчування по днях
- EU-14 алергени (Regulation 1169/2011)
- Дієтичні профілі учасників

### Надзвичайні ситуації
- Протокол НС — 7-станова машина станів
- 18 типів дій (Ustawa Kamilka 2024 + Rozp. MEN §6)
- Immutable ledger — не можна змінити після закриття

### Комерція
- Підтримка батьків (запити, скасування, переноси)
- Розстрочки (через `account.payment.term`)
- Програма лояльності (через `loyalty.program` + camp tier)
- Відгуки батьків (через `website_rating`)

### Навчання персоналу
- Курс виховника 36h (через `slide.channel`)
- MEN compliance tracking (Rozp. MEN 2016)
- Сертифікати завершення

### Комунікації
- SMS через TurboSMS (через `sms`)
- Мульти-провайдер routing (UA/PL номери)
- Meta CAPI events (Facebook Pixel)

### Батьківський портал
- `/my` — головна панель батька
- `/my/participants` — діти та картки
- `/my/stories` — новини з табору
- `/my/documents` — юридичні документи
- `/my/loyalty` — програма лояльності
- REST API для мобільного додатку

---

## Встановлення

```bash
# На staging:
docker stop campscout_web
docker run --rm ... odoo -i fayna_campscout --stop-after-init
docker start campscout_web
```

**Одна команда — весь функціонал.**

---

## Залежності

| Odoo native | Призначення |
|---|---|
| `event`, `event_sale` | Заїзди табору |
| `sale`, `account` | Продажі та оплати |
| `loyalty` | Програма лояльності |
| `slide` | Навчання персоналу |
| `sms` | SMS-розсилки |
| `website_rating` | Відгуки |
| `portal`, `website` | Батьківський кабінет |

| Fayna shared | Призначення |
|---|---|
| `fayna_rodo_compliance` | RODO consent log (shared з sendpulse) |

---

## Структура

```
fayna_campscout/
  models/
    camp.py          # event.event + product.template розширення
    participant.py   # camp.participant, кваліфікаційна картка
    operations.py    # журнал, програма, персонал, кураторіум
    nutrition.py     # харчування, алергени
    emergency.py     # протокол НС
    commercial.py    # підтримка, лояльність, відгуки
    training.py      # навчання (extends slide.channel)
    sms.py           # SMS adapter TurboSMS
  views/             # XML views для кожного розділу
  templates/         # Portal + website QWeb шаблони
  i18n/
    uk_UA.po         # Українська
    pl_PL.po         # Польська
```

---

## Ліцензія

LGPL-3 · [Fayna Digital](https://www.fayna.agency) · Volodymyr Shevchenko
