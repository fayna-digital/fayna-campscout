# MIGRATION_MAP — campscout_management → fayna_camp_portal

> Реалізація фази **P1** з [PLAN.md](PLAN.md). Складено 2026-06-09 з аналізу КОДУ обох модулів (локально, без доступу до staging-БД).
> ⚠️ Все, що потребує перевірки на живій БД, позначено **[треба SQL на staging]** — не вгадано.

---

## Головний висновок (перевірено по коду)

**Це НЕ ETL між двома базами.** Обидва модулі — addon-и на **одній Odoo-БД**. Дані клієнтів уже лежать у **нативних Odoo-таблицях**, спільних для обох модулів. «Міграція» = не перенос рядків, а:

1. `post_init_hook` portal переносить **ownership** записів (`ir.model.data`) з absorbed-модулів — **вже реалізовано** (`hooks.py`).
2. Portal **створює свої структуровані моделі** (`camp.participant`, `camp.qualification.card`) поверх наявних нативних `sale.order` / `event.registration`.
3. Невпорядковані дані з форми (картка дитини) треба **витягти й структурувати** — але спершу знайти, де вони фізично осіли.

---

## Джерело: що таке `campscout_management` (перевірено)

Тонкий модуль, `17.0.1.16.13`, depends: `website_sale, event, mail`. **5 файлів моделей, жодної власної таблиці даних** — лише розширення нативних:

| Файл | `_inherit` | Кастомні поля | Дані клієнтів? |
|------|-----------|----------------|----------------|
| `sale_order.py` | `sale.order` | **немає** (лише методи: Umowa в PDF, confirm) | через нативні поля |
| `product_template.py` | `product.template` | немає (метод пошуку tickets) | ні (каталог) |
| `crm_lead.py` | `crm.lead` | `meta_fbc`, `meta_fbp`, `meta_external_id`, `days_in_work` | маркетинг (хешоване) |
| `meta_capi.py` | `crm.lead`, `sale.order` | Meta CAPI (методи) | ні (сигнали) |
| `ir_actions_report.py` | патч PDF-генератора | — | ні (техдолг) |

**Дані дітей (`bs_child_name`, `bs_parents_phone`, `bs_child_health_info`):**
- Це **HTML-форма** у `views/website_qualification_card.xml` (`<input name="bs_*">`), **НЕ Odoo-поля**.
- Контролера, який їх приймає й зберігає, у репо **немає** (єдиний controller — `turbosms_webhook.py`, не пов'язаний).
- 🔴 **[треба SQL на staging]** Де вони осідають? Гіпотези (не підтверджені): order note на `sale.order`, `mail.message` чатера, або взагалі лише в email/PDF без запису в БД. **Це найбільший ризик RODO** — якщо медичні дані ніде структуровано не зберігаються, мігрувати нема чого, треба збирати наново.

---

## Mapping: джерело → ціль (P1.2)

| Нативна таблиця (джерело, спільна БД) | Ціль у portal | Дія міграції |
|---|---|---|
| `res.partner` (батьки, ~97) | `res.partner` (та сама) + portal-розширення (`res_partner_inherit.py`: sms_opt_in) | На місці — лише доповнити поля |
| `sale.order` + `.line` (~157 замовлень) | `sale.order` (та сама) + `commercial.py` розширення | На місці — portal читає наявні |
| `event.registration` (~71) | `event.registration` + portal-логіка | На місці |
| `event.event` (заїзди) | `event.event` + `camp.camp` (`camp.py`) поверх | Portal створює `camp.camp` ↔ event |
| дані дітей з форми `bs_*` | `camp.participant` + `camp.qualification.card` (5 секцій MEN) | 🔴 **[треба SQL]** — джерело невідоме |
| `crm.lead` + meta-поля | лишити в crm.lead / `fayna_meta_capi` | Не чіпати (маркетинг окремо) |
| `mail.template`, legal `website.page`, каталог HTML | seed, не дані | НЕ мігрувати (перестворюються) |

---

## Чеклист P1 (оновлює PLAN.md)

- [x] **P1.1 інвентар** — джерело = тонкий модуль, дані в нативних таблицях (цей документ).
- [~] **P1.2 mapping** — складено по коду; рядок «дані дітей» заблоковано SQL-перевіркою.
- [ ] **P1.3 скрипт** — БЛОКОВАНО до P1.r: спершу знайти, де osідають `bs_*`.
- [ ] **P1.4 звірка** — контрольні суми до/після.

### 🔴 Новий блокер P1.r — [треба staging-БД]
Без доступу до staging (заблокований SSH-ключем з 13.05 — §🔴 kanban) неможливо:
1. `\d sale_order` / `\d res_partner` — знайти, чи є custom-колонки з даними дітей.
2. Перевірити, чи `bs_child_health_info` взагалі десь у БД (`SELECT ... WHERE ... ILIKE`).
3. Порахувати реальні обсяги (підтвердити ~97/~157/~71).

**Поки staging заблокований — P1 далі рухатись не може.** Це робить «Розблокувати staging Hetzner» (§🔴) прямим блокером міграції.

---

## Зв'язки
- [PLAN.md](PLAN.md) P1 · [TZ.md](TZ.md) Boundaries · [LEGAL_REQUIREMENTS.md](LEGAL_REQUIREMENTS.md)
- Kanban: [[projects/kanban]] §🔴 «Міграція даних» + «Розблокувати staging Hetzner»
