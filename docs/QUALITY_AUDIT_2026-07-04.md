# QUALITY AUDIT — coverage P3.5 (2026-07-04)

> Харнес: docker odoo:17 + postgres:16, 1:1 ci.yml (`--addons-path=/addons,/addons/deps`),
> `python3 -m coverage run --source=<модуль> odoo -i fayna_camp_portal --test-enable --test-tags /fayna_camp_portal`.
> COVERAGE_FILE на writable-mount (образ USER=odoo, CWD=/ не писабельний). Повторюваність: 2 виміри (base/final) в один день.

## Підсумок

| Вимір | Stmts | Miss | Cover |
|---|---|---|---|
| Базовий (main, до серії 3) | 8932 | 2961 | **67%** |
| Фінальний (ця гілка) | 8962 | 2746 | **69%** |

**Ціль ≥70% (P3.5) ще НЕ досягнута** — бракує ~90 покритих інструкцій. Чесний залишок нижче.

## Що зроблено цією гілкою

- `controllers/admin.py` **13% → 58%** (−139 missed): `test_admin_dashboard.py` — гейт організатора,
  рендер 7 KPI-секцій дашборда, ПОВНИЙ цикл login-as → stop-impersonation (RODO art.30 лог на старті
  І стопі, редірект-landing, відновлення сесії), заборона ескалації (organizator/admin — відмова БЕЗ
  лог-запису), as-parent прев'ю з логом.
- `controllers/escort_portal.py` **27% → 45%**: `test_escort_portal.py` — список/деталь власника,
  ownership-гейт чужого escort + leak-перевірка тіла.
- 🐛 **Знайдено і полагоджено продуктовий баг (тестом):** кабінет `/my/escort` показував батькам
  «Brak rekordów» попри наявні escort-записи — non-sudo search з traversal-доменом
  `participant_id.parent_partner_id` фільтрував ВЛАСНІ записи (емпірично: rule-only search знаходить,
  route-домен — ні). Фікс: sudo + явний ownership-домен (канонічний патерн модуля, як
  `/my/participants`). Те саме в лічильнику `_prepare_home_portal_values` (показував 0).
- 🐛 **Знайдено і полагоджено (тестом):** `/my/escort/<id>` — деталь (і підпис) мертві для батьків, див. «Розпарковано» нижче.
- 🐛 **Знайдено і полагоджено (тестом):** `/admin/as-parent` показував порожній кабінет для батьків
  З user-акаунтом (scoped_env під portal-юзером → AccessError → catch → порожньо). Фікс: sudo +
  ownership-домен, як портал.

## Залишок до ≥70% (пріоритет наступної серії)

| Файл | Cover | Miss | Кандидат-тест |
|---|---|---|---|
| wizards/staff_sms_composer.py | 28% | 87 | композер SMS: create+send flow |
| models/incident_kamilka.py | 34% | 38 | ескалація 5-хв cron + notification log |
| models/sms_notify.py | 34% | 48 | 3-tier dispatch (mock adapter) |
| models/res_users_inherit.py | 35% | 13 | login action роутінг ролей |
| controllers/recruitment_portal.py | 37% | 62 | публічні вакансії + аплікація |
| controllers/kiosk.py | 40% | 26 | плитки за ролями (set_lang прийде з PR#17) |
| models/reports.py | 41% | 98 | snapshot-моделі + marketing report compute |

## Розпарковано (серія 5, той самий день) — ТРЕТІЙ баг зловлено

- Розбір паркованого submit-тесту (werkzeug-логи) показав: **/my/escort/<id> НІКОЛИ не рендерився
  для власника** — `_get_own_escort` без sudo падав уже на читанні escort'а (record-rule check
  трасує participant_id) → 303 на список для ВСІХ батьків; «зелений» detail-тест був хибно-зеленим
  (follow-redirect на список, який теж містить ім'я дитини). Фікс: sudo-browse + жорсткий гейт
  parent_partner_id (патерн `_get_own_participant`). Тепер: власник GET деталі → 200 (werkzeug),
  чужий → 303; submit-тест повернуто, draft→collected під тестом. **Урок: асерти редірект-флоу —
  лише raw (allow_redirects=False); follow-redirect маскує мертві сторінки.**

## Історія

- 2026-07-02: coverage 59% (сесія конвеєра; діра admin.py 13%).
- 2026-07-04: 67% (main виріс тестами серій 1-2) → **69%** (ця гілка).
