{
    "name": "CampScout Portal (Thin Client)",
    "version": "17.0.0.3.0",
    "category": "Tools/Camp Management",
    "summary": "Parent portal with REST API — family dashboard, messaging, documents, loyalty",
    "description": """
CampScout Portal (Thin Client)
===============================

Parent-facing portal integration:
- Portal dashboard: /my/participants, /my/stories, /my/documents, /my/loyalty
- REST JSON API for mobile apps (login, participants, stories, loyalty, documents, messages)
- Daily story publishing to families
- Legal document signing workflow
- Loyalty program tracking
    """,
    "author": "Fayna Digital",
    "website": "https://fayna.agency",
    "license": "LGPL-3",
    "depends": [
        "base",
        "website",
        "sale",
        "portal",
        "mail",
        "fayna_camp_template",
        "fayna_camp_qualification",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/campscout_views.xml",
        "templates/portal_templates.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "fayna_campscout/static/src/scss/portal_hero.scss",
            "fayna_campscout/static/src/css/portal.css",
        ],
    },
    "installable": True,
    "application": True,
}
