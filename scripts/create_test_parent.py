#!/usr/bin/env python3
# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""
Create test parent user with test child and test data for CampScout.

Run via:
  docker exec campscout_web python3 -c "
  import os, sys, django
  os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'odoo.conf')
  sys.path.insert(0, '/opt/campscout')
  from odoo.api import Environment
  from odoo import SUPERUSER_ID, registry as get_registry
  with get_registry('campscout').cursor() as cr:
    env = Environment(cr, SUPERUSER_ID, {})
    exec(open('/opt/campscout/custom-addons/fayna_camp_portal/scripts/create_test_parent.py').read())
  " 2>&1

Or via shell in container:
  docker exec campscout_web bash -c "cd /opt/campscout && python3 << 'EOF'
... script content here ...
EOF"
"""

from datetime import datetime, timedelta

from odoo import fields

# env should be passed from caller (Odoo context already initialized)
# If running standalone, skip this script
try:
    assert "env" in locals() or "env" in globals()
except AssertionError:
    print("[!] This script must be run within Odoo environment context")
    print("[!] Use: docker exec campscout_web odoo -d campscout shell < script.py")
    exit(1)

# Clean up if exists (for idempotency)
print("[TEST DATA] Cleaning up existing test data...")
env["res.users"].search([("login", "=", "test.parent@campscout.eu")]).unlink()
env["res.partner"].search([("email", "=", "test.parent@campscout.eu")]).unlink()
env["camp.participant"].search(
    [("first_name", "=", "Anna"), ("last_name", "=", "Testova")]
).unlink()

# 1. Create portal partner
print("[TEST DATA] Creating test parent partner...")
portal_partner = env["res.partner"].create(
    {
        "name": "Test Parent CampScout",
        "email": "test.parent@campscout.eu",
        "phone": "+48501111111",
        "country_id": env.ref("base.pl").id,
        "is_company": False,
    }
)

# 2. Create portal user
print("[TEST DATA] Creating test portal user (test.parent@campscout.eu / TestParent2026!)...")
test_user = env["res.users"].create(
    {
        "name": "Test Parent CampScout",
        "login": "test.parent@campscout.eu",
        "email": "test.parent@campscout.eu",
        "partner_id": portal_partner.id,
        "groups_id": [(6, 0, [env.ref("base.group_portal").id])],
        "password": "TestParent2026!",
    }
)

# 3. Create RODO consent log
print("[TEST DATA] Recording RODO consent...")
env["fayna.rodo.consent.log"].create(
    {
        "partner_id": portal_partner.id,
        "email": portal_partner.email,
        "channel": "website",
        "purpose": "transactional",
        "legal_basis": "contract",
        "consent_given": True,
        "source": "admin_manual",
        "consent_timestamp": fields.Datetime.now(),
        "exact_user_response": "Test data creation",
        "notes": "Test parent created for staging verification",
    }
)

# --- PHASE 1 DONE: commit parent+user+consent before risky camp data ---
env.cr.commit()
print("[TEST DATA] ✅ Phase 1 committed — parent user can now log in.")

# Phase 2: Test camp data (child, event, registration, story, loyalty)
# Wrapped in try/except — if any step fails, parent user is already committed and usable.
try:
    # 4. Create test child participant
    print("[TEST DATA] Creating test child (Anna Testova)...")
    test_child = env["camp.participant"].create(
        {
            "first_name": "Anna",
            "last_name": "Testova",
            "birth_date": "2015-06-10",
            "gender": "f",
            "nationality_id": env.ref("base.pl").id,
            "parent_partner_id": portal_partner.id,
            "diet_restrictions": "vegetarian",
            "vaccination_status": "complete",
            "swimming_ability": "deep",
            "stay_alone_permission": True,
            "emergency_contact_1_name": "Test Parent (Emergency)",
            "emergency_contact_1_phone": "+48501111111",
            "emergency_contact_1_relation": "mother",
        }
    )

    # 5. Get or create test event (camp)
    print("[TEST DATA] Finding or creating test event...")
    test_event = env["event.event"].search([], limit=1)
    if not test_event:
        print("  → Creating test event...")
        test_event = env["event.event"].create(
            {
                "name": "Test Camp 2026 - Summer",
                "date_begin": datetime.now() + timedelta(days=30),
                "date_end": datetime.now() + timedelta(days=40),
                "event_type_id": env.ref("event.event_type_conference").id,
                "seats_available": 50,
                "seats_expected": 40,
            }
        )
    else:
        print(f"  → Using existing event: {test_event.name}")

    # 6. Create event registration (so parent has a camp)
    print("[TEST DATA] Creating event registration...")
    env["event.registration"].create(
        {
            "event_id": test_event.id,
            "partner_id": portal_partner.id,
            "participant_id": test_child.id,
            "state": "done",
            "name": f"{test_child.display_name} - {test_event.name}",
        }
    )

    # 7. Create test story
    print("[TEST DATA] Creating test story...")
    env["camp.story"].create(
        {
            "event_id": test_event.id,
            "title": "Перший день у таборі",
            "content": (
                "<p>Перший день у таборі пройшов чудово! "
                "Діти познайомились, обрали команди та заспівали пісні біля багаття.</p>"
            ),
            "date": datetime.now().date(),
            "state": "published",
            "public": True,
            "story_type": "daily_log",
            "author_id": env.ref("base.user_admin").id,
        }
    )

    # 8. Create loyalty record
    print("[TEST DATA] Creating loyalty record (Silver tier - 2 camps)...")
    env["camp.loyalty"].create(
        {
            "participant_id": test_child.id,
            "camp_count": 2,
            "first_visit_date": (datetime.now() - timedelta(days=365)).date(),
            "last_visit_date": datetime.now().date(),
            "loyalty_tier": "silver",
            "loyalty_points": 150,
            "discount_eligible": True,
            "discount_percentage": 5.0,
            "badges": "Починаючий, Командний гравець",
            "notes": "Test loyalty record for demo",
        }
    )

    env.cr.commit()
    print("[TEST DATA] ✅ Phase 2 committed — camp data created.")

except Exception as e:
    env.cr.rollback()
    print(f"[TEST DATA] ⚠️ Phase 2 failed: {type(e).__name__}: {e}")
    print("[TEST DATA] Parent user still logs in, camp data missing.")

print("\n✅ TEST DATA SCRIPT COMPLETED")
print("\nLogin details:")
print("  Email: test.parent@campscout.eu")
print("  Password: TestParent2026!")
print("\nOpen https://staging.campscout.eu/my to test.")
