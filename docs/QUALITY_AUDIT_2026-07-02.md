<!-- Згенеровано конвеєром 2026-07-02: цифри = coverage.py (docker odoo:17 + postgres:16,
харнес 1:1 з ci.yml), чернетка тексту = gemini-2.5-flash, числа звірені CTO 1:1 зі
скриптовим звітом. Відтворення: scratchpad/cov_in_container.sh (сесія 409c59fe). -->

# Quality Audit — coverage-звіт (P3.5)

## Підсумок
**Дата прогону:** 2026-07-02
**Середовище:** docker odoo:17
**Тести:** 207 прогонів, 0 failed / 0 error.

## Загальне покриття коду
Загальне покриття коду модуля `fayna_camp_portal` становить **59%** (6958 стейтментів, 2880 не покритих).
Запланований поріг покриття P3.5 (70%) не досягнуто.

## Топ-10 найменш покритих файлів
| Файл                                                         | Стейтментів | Покриття |
| :----------------------------------------------------------- | :---------- | :------- |
| `controllers/admin.py`          | 301         | 13%      |
| `controllers/escort_portal.py`  | 62          | 27%      |
| `wizards/staff_sms_composer.py` | 120         | 28%      |
| `controllers/api.py`            | 53          | 32%      |
| `models/incident_kamilka.py`    | 58          | 34%      |
| `models/sms_notify.py`          | 73          | 34%      |
| `models/res_users_inherit.py`   | 20          | 35%      |
| `controllers/recruitment_portal.py` | 99          | 37%      |
| `controllers/kiosk.py`          | 43          | 40%      |
| `models/reports.py`             | 167         | 41%      |

## Діри в покритті
Найбільші прогалини у покритті спостерігаються у наступних компонентах:

**Контролери HTTP-шляхів:**
*   `controllers/admin.py` (13%) — найбільша діра.
*   `controllers/escort_portal.py` (27%)
*   `controllers/api.py` (32%)
*   `controllers/recruitment_portal.py` (37%)
*   `controllers/kiosk.py` (40%)
*   `controllers/portal.py` (45%)

**Моделі:**
*   `models/incident_kamilka.py` (34%)
*   `models/sms_notify.py` (34%)
*   `models/res_users_inherit.py` (35%)
*   `models/reports.py` (41%)
*   `models/recruitment.py` (43%)
*   `models/commercial.py` (44%)
*   `models/emergency.py` (45%)
*   `models/sms.py` (46%)
*   `models/transport.py` (49%)

**Візарди:**
*   `wizards/staff_sms_composer.py` (28%)

## Рекомендації
1.  **Підвищити покриття тестами:** Сфокусуватися на написанні тестів для файлів з найнижчим показником покриття, особливо для `controllers/admin.py` (13%).
2.  **Переглянути поріг покриття:** Розглянути можливість коригування цільового порогу покриття (P3.5) відповідно до поточного стану та ресурсів.

Рішення щодо подальших дій залишається за CTO.

---
**Виноска:** Файл `controllers/api.py` (32%) видаляється у PR#10. З наступного прогону він зникне зі знаменника загального покриття.

## Рішення CTO (2026-07-02)
Поріг 70% (P3.5) лишається МЕТОЮ, не CI-блокером: merge-гейт тримають 207 unit-тестів
(0 failed) + lint. Наступний крок покриття — контролерні HTTP-тести (admin.py 13% —
найбільша діра: 301 stmts). E2E-скелети (Playwright) уже є і калібруються окремо (P5.1).
