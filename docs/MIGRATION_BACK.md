# MIGRATION_BACK — план міграції fayna_camp_portal на PROD (ціль: 2026-06-12)

> Виконується ЛИШЕ за явною командою user-а після QA 11.06 на staging.
> Кожен крок цього плану ВЖЕ репетирується щодобовим `scripts/staging_sync.sh`
> (рефреш staging = відновлення prod-копії + install модуля) — статус репетиції
> дивись у WORKLOG. Все нижче — idempotent, із dry-run і бекапом.

## 0. Передумови (gate)
- [ ] QA user-а на staging green по 7 кабінетах (11.06).
- [ ] Odoo-тести модуля зелені на staging (`--test-tags /fayna_camp_portal`).
- [ ] Остання щодобова репетиція install — без помилок.
- [ ] Вікно міграції: поза годинами пік (рекоменд.: ранок 12.06 до 9:00).

## 1. Бекап (rollback point #1)
```bash
ssh campscout "docker exec campscout_db pg_dump -U odoo -Fc campscout > /opt/backups/pre_portal_$(date +%Y%m%d).dump"
# filestore НЕ чіпаємо (install його не модифікує деструктивно), але розмір/чексуму зафіксувати
```
Rollback будь-якої миті: `pg_restore` цього дампа + `docker restart`.

## 2. Install модуля на prod
```bash
ssh campscout
cd /opt/campscout/custom-addons/fayna_camp_portal && git fetch && git checkout main && git pull && sudo chmod -R o+rX .
docker exec campscout_web odoo -c /etc/odoo/odoo.conf -d campscout -i fayna_camp_portal --stop-after-init --no-http
docker restart campscout_web
```
⚠️ Перед цим гілка `loop/season-sprint` мерджиться у main (PR, за командою).
⚠️ `--no-http` обов'язковий (8069+8072 зайняті) — INC репетиції 10.06.
⚠️ НА PROD НЕ ВИКОНУЄТЬСЯ нейтралізація (mail/SMS/crons лишаються живі) — вона лише для staging-рефрешу. Не плутати скрипти!

## 3. «Звільнення даних» від campscout_management (adoption) — §8a ТЗ
ПІДТВЕРДЖЕНО 10.06 [staging SQL]: модуль володіє 24 product.template (всі табори),
3 event.event + 3 tickets (noupdate), 21 attribute.values, homepage_v2 + 8 views, website.page.
**До будь-якого uninstall** (сам uninstall — НЕ в цьому вікні, окреме рішення пізніше):
```sql
-- dry-run: SELECT model, count(*) FROM ir_model_data WHERE module='campscout_management' GROUP BY model;
DELETE FROM ir_model_data
 WHERE module='campscout_management'
   AND model IN ('product.template','product.product','product.attribute',
                 'product.attribute.value','event.event','event.event.ticket','website.page');
```
→ записи стають звичайними даними (живуть незалежно). Кастомні views (homepage_v2,
legal, mail layout) НЕ adoptуються — переносяться як шаблони portal (окремий крок, до uninstall).

## 4. Дані → правильні місця
### 4.1 Люди → кабінети (групи)
- Організатор (Volodymyr) → group_camp_organizator + admin.
- Кадра з camp.staff (роль) → відповідні групи kierownik/wychowawca ПІСЛЯ RSPTS-акцепту (свідомо: акцепт вручну admin — R2; до акцепту лишаються без бекенд-прав).
- Батьки: partners з реєстраціями вже мають portal-доступ (нативно) — нових дій не треба; кабінет /my/* підхоплює.
- Księgowa → group_camp_finance (коли user вирішить дати логін; зараз — він сам).
### 4.2 Діти → групи (§2)
- `camp.group.action_auto_split(event)` для кожного активного event → молодші/старші, ліміти 15/20; нерозподілених kierownik перетасовує в UI.
- ⚠️ Лише ПІСЛЯ цього wychowawcy бачать дітей (нове record rule «лише своя група»). Порядок критичний — INC-нотатка агента §2.
### 4.3 Старі картки (bs_* на sale_order) → camp.participant
ПІДТВЕРДЖЕНО 10.06: 21 колонка bs_*; 81 замовлення з `bs_qualification_form_pdf`, 83 згоди.
- Скрипт (написати до 12.06, прогнати на staging): для кожного SO з bs_-даними →
  знайти/створити camp.participant (по імені дитини+SO partner), прикріпити PDF
  як ir.attachment до картки, wzor_version='2021' (передані до 06.06 — чинні, §2 розпорядження),
  qualification_signed=True (підпис уже існує на PDF), consent з bs_client_consent.
- Контрольна сума: 81 PDF до = 81 attachment після; список розбіжностей → CSV для ручного розбору.
### 4.4 Фінанси → analytic backfill
- Для кожного активного event: `action_open_budget` (створює budget + analytic 'CAMP/...').
- Фактури marzec–maj: прив'язка analytic по продукту-табору (product↔event мапінг із campscout_management даних) — скрипт із dry-run; неоднозначні → CSV до ручного розбору. Закриває історичну частину листа księgowej.
### 4.5 Версіонування карток (R7)
- Існуючі підписані → wzor_version='2021' (immutable, старий PDF-layout).
- Нові від 06.06 → '2026' (дефолт моделі вже такий).

## 5. Верифікація після міграції (чекліст)
- [ ] `ir_module_module`: fayna_camp_portal=installed; campscout_management=installed (співіснують, Strangler Fig).
- [ ] Контрольні суми: partners/sale_order/event_registration ДО = ПІСЛЯ (install нічого не видаляє).
- [ ] 81 bs_-PDF → 81 attachment на картках.
- [ ] mail-сервери активні (prod ЖИВИЙ — нейтralізація не виконувалась!), crons як були.
- [ ] Smoke по 7 кабінетах на prod (швидкий, по 2 хв на роль).
- [ ] curl головних сторінок (200): /, /my, /shop.

## 6. Rollback
1. `docker stop campscout_web` → `pg_restore` бекапа кроку 1 → restart. (≤15 хв.)
2. Код: модуль uninstall НЕ потрібен — досить відновлення БД (install — це записи в БД; файли модуля без install інертні).

## Відкрите (рішення user-а пізніше)
- Коли вимикати campscout_management (після повного feature-parity + adoption views).
- Логін для księgowej (group_camp_finance).
- Переніс homepage_v2/legal views у шаблони portal.
