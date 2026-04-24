{
    "name": "Fayna CampScout (client data)",
    "version": "17.0.0.1.0",
    "category": "Tools/Camp Management",
    "summary": "Thin client-specific data layer for CampScout (product records, legal pages, brand)",
    "description": """
Fayna CampScout (client data)
=============================

Phase 7 of the Fayna Camp vertical stack (Strangler Fig decomposition
per CAMPSCOUT_MASTER_TZ.md §16).

Client-specific records ONLY (21 product.template + events + FAQ + legal copy + brand theme).

Current status: scaffold — installable but inert. Feature flag
`fayna_campscout.active` defaults to `False`; implementation lands in incremental
milestones defined in docs/TZ.md.

Author: Fayna Digital — Volodymyr Shevchenko
License: LGPL-3
TZ: fayna-digital-docs/contributing/CAMPSCOUT_MASTER_TZ.md §16 Phase 7
    """,
    "author": "Fayna Digital — Volodymyr Shevchenko",
    "website": "https://fayna.agency",
    "license": "LGPL-3",
    "depends": [
        "fayna_camp_template",
        "fayna_camp_qualification",
        "fayna_camp_sales",
        "fayna_legal_versioning",
        "fayna_reviews",
        "fayna_instructor_school",
    ],
    "data": [
        "data/ir_config_parameter.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
