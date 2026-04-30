{
    "name": "Fayna CampScout",
    "version": "17.0.1.0.0",
    "category": "Tools/Camp Management",
    "summary": "Повна система управління дитячим табором: учасники, операції, харчування, НС, комерція, навчання",
    "description": """
Fayna CampScout
===============

Єдиний модуль для управління дитячим табором CampScout.
Побудований на базі нативних модулів Odoo 17.

Функції:
- Табори як event.event (заїзди) + product.template (магазин)
- Кваліфікаційна картка дитини (5 секцій, PL закон)
- RODO consent log (через fayna_rodo_compliance)
- Операції: журнал, розклад, програма (Załącznik 9)
- Харчування + EU-14 алергени
- Протокол НС (Ustawa Kamilka + Rozp. MEN §6)
- Кураторіум: сповіщення та перевірки
- Продажі, підтримка батьків, розстрочки
- Програма лояльності (через sale_loyalty)
- Відгуки (через website_rating)
- Навчання вихователів (через slide.channel + MEN 36h)
- SMS через TurboSMS (через sms)
- Meta CAPI events
- Батьківський портал /my
- REST API для мобільного додатку

Автор: Fayna Digital — Volodymyr Shevchenko
Ліцензія: LGPL-3
    """,
    "author": "Fayna Digital — Volodymyr Shevchenko",
    "website": "https://fayna.agency",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "portal",
        "website",
        "sale",
        "event",
        "event_sale",
        "account",
        "loyalty",
        "slide",
        "sms",
        "website_rating",
        "fayna_rodo_compliance",
    ],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        "data/ir_config_parameter.xml",
        "data/cron.xml",
        "views/camp_views.xml",
        "views/participant_views.xml",
        "views/operations_views.xml",
        "views/nutrition_views.xml",
        "views/emergency_views.xml",
        "views/commercial_views.xml",
        "views/training_views.xml",
        "views/sms_views.xml",
        "views/menus.xml",
        "templates/portal_templates.xml",
        "templates/website_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "fayna_campscout/static/src/scss/portal_hero.scss",
            "fayna_campscout/static/src/css/portal.css",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
    "auto_install": False,
}
