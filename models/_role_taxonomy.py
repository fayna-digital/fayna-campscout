# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Canonical camp staff-role taxonomy — single source of truth (ADR-22).

Before ADR-22 the «role in camp» concept was encoded in TWO incompatible
Selections (camp.staff.role EN-technical keys vs camp.staff.vacancy.role
PL-keys) plus scattered string hardcodes. This module defines ONE canonical
set (PL-domain-correct, Rozp. MEN) imported by BOTH models, so a vacancy and
the hired staff member always speak the same key — no manual bridge.

`CAMP_ROLE_SELECTION` — the canonical Odoo Selection list.
`LEGACY_ROLE_MAP`     — old key → canonical key, for the data migration
                        (migrations/17.0.4.0.0/post-migrate.py) and reverse
                        compatibility. Keys are the historical values once
                        stored in camp.staff.role and camp.staff.vacancy.role.
"""

# Canonical PL-domain role keys — shared by camp.staff and camp.staff.vacancy.
# Labels are PL (product = Polish market, Rozp. MEN).
CAMP_ROLE_SELECTION = [
    ("kierownik", "Kierownik wypoczynku"),
    ("wychowawca", "Wychowawca"),
    ("instruktor", "Instruktor"),
    ("ratownik", "Ratownik medyczny / Pielęgniarka"),
    ("kuchnia", "Personel kuchni"),
    ("logistyka", "Logistyka"),
    ("wolontariusz", "Wolontariusz"),
]

# Set of canonical keys for quick membership checks / validation.
CAMP_ROLE_KEYS = frozenset(key for key, _label in CAMP_ROLE_SELECTION)

# Legacy (pre-ADR-22) key → canonical key.
#   camp.staff.role legacy:  director,leader,counselor,activity_lead,
#                            medic,kitchen_staff,logistics
#   camp.staff.vacancy.role legacy: wychowawca,kierownik,instructor
# Canonical keys are mapped to themselves so the migration is idempotent.
LEGACY_ROLE_MAP = {
    # --- camp.staff legacy (EN-technical) ---
    "director": "kierownik",
    "leader": "kierownik",
    "counselor": "wychowawca",
    "activity_lead": "instruktor",
    "medic": "ratownik",
    "kitchen_staff": "kuchnia",
    "logistics": "logistyka",
    # --- camp.staff.vacancy legacy (PL, but 'instructor' EN spelling) ---
    "instructor": "instruktor",
    # --- already-canonical keys (idempotency) ---
    "kierownik": "kierownik",
    "wychowawca": "wychowawca",
    "instruktor": "instruktor",
    "ratownik": "ratownik",
    "kuchnia": "kuchnia",
    "logistyka": "logistyka",
    "wolontariusz": "wolontariusz",
}
