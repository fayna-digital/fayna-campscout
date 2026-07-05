# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
{
    "name": "Портал CampScout",
    "version": "17.0.4.1.7",
    "category": "Tools/Camp Management",
    "summary": "Complete children's summer camp management portal (Polish law compliance)",
    "description": """
Fayna Camp Portal
=================

Hotel-pattern Odoo 17 module — single module containing all camp business logic.
Built on top of native Odoo features (mail.thread, portal, event, sale,
loyalty, account.payment.term, website_rating, sms).

Features:

* 6-role RBAC: Organizator (PL Rozp. MEN 30.03.2016 §2.1) / Sales / Kierownik /
  Wychowawca / Instructor / Parent — record rules + field-level groups
* Native Odoo chat with auto-subscribers + discuss.channel auto-create per
  camp shift staff team
* SMS three-tier (CRITICAL/IMPORTANT/INFO) via fayna_sms_base multi-provider
  dispatcher (TurboSMS adapter)
* Wychowawca SMS broadcast wizard with cost guard + immutable audit log
* Ustawa Kamilka 2024 — vital interest reporting with 5-min escalation cron
  + immutable Kuratorium notification log
* Karta kwalifikacyjna (5 sections per PL law) with parent signoff workflow
* Dziennik zajęć (Załącznik 5 MEN) with kierownik commenting via mail.thread
* Program Wypoczynku (Załącznik 9) with approval workflow
* Kuratorium notification (Załącznik 1) — auto-prepared submission package
* Parent portal /my/ — children cards, stories, loyalty, transport, support
* Organizator dashboard /admin/dashboard with view-as impersonation
  (with_user pattern, RODO art.30 audit log)
* PL/UA native i18n via Odoo .po (374+ translated strings)
* RODO compliance — append-only consent log, art.9 field-level access,
  immutable audit trails (7-year retention)

Architecture: Strangler Fig migration from campscout_management monolith.
All camp-specific logic lives in this single module. Horizontal infrastructure
(fayna_rodo_compliance, fayna_sms_base) stays as separate reusable modules.

Author: Fayna Digital — Volodymyr Shevchenko
License: OPL-1 (Odoo Proprietary License v1.0)
    """,
    "author": "Fayna Digital — Volodymyr Shevchenko",
    "website": "https://fayna.agency",
    "license": "OPL-1",
    "depends": [
        "base",
        "mail",
        "contacts",
        "portal",
        "website",
        "website_slides",
        "sale",
        "event",
        "event_sale",
        "website_event",
        "website_sale",
        "account",
        "loyalty",
        "sms",
        "fayna_rodo_compliance",
        "fayna_sms_base",
    ],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        "data/ir_config_parameter.xml",
        "data/budget_categories.xml",
        "data/fiscal_positions.xml",
        "data/cron.xml",
        "data/cron_kamilka_escalation.xml",
        "data/sms_templates.xml",
        "data/sms_child_templates.xml",
        "data/fayna_sms_provider_data.xml",
        "views/camp_views.xml",
        "views/participant_views.xml",
        "views/operations_views.xml",
        "views/group_views.xml",
        "views/nutrition_views.xml",
        "views/emergency_views.xml",
        "views/incident_card_views.xml",
        "views/incident_notification_log_views.xml",
        "views/commercial_views.xml",
        "views/sale_order_installment_views.xml",
        "views/budget_views.xml",
        "views/staffing_views.xml",
        "views/program_views.xml",
        "views/regulamin_views.xml",
        "views/teczka_views.xml",
        "views/training_views.xml",
        "views/sms_views.xml",
        "views/stories_views.xml",
        "views/admin_views.xml",
        "views/kiosk_views.xml",
        "views/menus.xml",
        "views/menu_scoping.xml",
        "views/recruitment_views.xml",
        "views/transport_views.xml",
        "views/camp_escort_views.xml",
        "views/staff_sms_views.xml",
        "views/reports_views.xml",
        "views/res_company_views.xml",
        "reports/teczka_report_templates.xml",
        "reports/teczka_reports.xml",
        "reports/budget_report_templates.xml",
        "reports/budget_evidence_templates.xml",
        "reports/budget_reports.xml",
        "reports/incident_report_templates.xml",
        "reports/incident_reports.xml",
        "reports/karta_report_templates.xml",
        "reports/karta_reports.xml",
        "reports/dziennik_report_templates.xml",
        "reports/dziennik_reports.xml",
        "reports/escort_report_templates.xml",
        "reports/escort_reports.xml",
        "reports/escort_rodo_report_templates.xml",
        "reports/escort_rodo_reports.xml",
        "templates/portal_templates.xml",
        "templates/portal_camp_day.xml",
        "templates/portal_chatter.xml",
        "templates/portal_escort.xml",
        "templates/portal_recruitment.xml",
        "templates/website_templates.xml",
        "templates/admin_dashboard.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "fayna_camp_portal/static/src/scss/portal_hero.scss",
            "fayna_camp_portal/static/src/css/portal.css",
        ],
        "web.assets_backend": [
            "fayna_camp_portal/static/src/js/chat_window_close_fix.js",
            "fayna_camp_portal/static/src/js/impersonation_systray.js",
            "fayna_camp_portal/static/src/xml/impersonation_systray.xml",
            # Kiosk shell (TZ §4)
            "fayna_camp_portal/static/src/scss/kiosk.scss",
            "fayna_camp_portal/static/src/js/kiosk_app.js",
            "fayna_camp_portal/static/src/xml/kiosk_template.xml",
            "fayna_camp_portal/static/src/js/kiosk_odoo_toggle_systray.js",
            "fayna_camp_portal/static/src/xml/kiosk_toggle_systray.xml",
            "fayna_camp_portal/static/src/js/kiosk_back_systray.js",
            "fayna_camp_portal/static/src/xml/kiosk_back_systray.xml",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
    "auto_install": False,
}
