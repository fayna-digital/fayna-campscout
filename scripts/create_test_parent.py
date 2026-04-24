#!/usr/bin/env python3
"""
Create test parent user with test child and test data.

Run via:
  docker exec campscout_web odoo shell -d campscout < scripts/create_test_parent.py

Or interactively in Odoo shell:
  >>> exec(open('scripts/create_test_parent.py').read())
"""

from datetime import datetime, timedelta
from odoo import fields as odoo_fields

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
print(
    "[TEST DATA] Creating test portal user (test.parent@campscout.eu / TestParent2026!)..."
)
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
        "consent_timestamp": odoo_fields.Datetime.now(),
        "exact_user_response": "Test data creation",
        "notes": "Test parent created for staging verification",
    }
)

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
test_story = env["camp.story"].create(
    {
        "event_id": test_event.id,
        "title": "Первый день в табору",
        "content": """<div class="o_portal_section">
    <h4>Привет, мамы и папы!</h4>
    <p>Первый день в табору прошел отлично! Все дети хорошо поселились в своих домиках и уже начали дружить.</p>
    <p><strong>Сегодня мы:</strong></p>
    <ul>
        <li>Прошли регистрацию</li>
        <li>Познакомились друг с другом</li>
        <li>Пели песни в столовой</li>
        <li>Играли в игры на свежем воздухе</li>
    </ul>
    <p>Завтра нас ждет множество интересных занятий!</p>
    <p><em>Вожатые CampScout</em></p>
</div>""",
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
        "badges": "Новичок, Командный игрок",
        "notes": "Test loyalty record for demo",
    }
)

print("\n✅ TEST DATA CREATED SUCCESSFULLY")
print("\nLogin details:")
print("  Email: test.parent@campscout.eu")
print("  Password: TestParent2026!")
print("\nNext steps:")
print("  1. Open https://staging.campscout.eu/my in your browser")
print("  2. Login with the credentials above")
print("  3. Click on 'Мої діти в таборах' to see test child")
print("  4. Click on 'Щоденні історії' to see test story")
print("  5. Click on 'Програма лояльності' to see test loyalty tier (Silver)")
print("  6. Click on 'Юридичні документи' to see legal documents")
