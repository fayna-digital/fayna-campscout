#!/usr/bin/env python3
# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — Populate children + events (F4, LOOP-E iteration 1)
# Дотяжка 11 дітей без group_id та 6 таборів без budget/teczka/program.

"""
Populate children without group_id + events without budget/teczka/program.

Usage:
    cd /path/to/campscout && python3 scripts/populate_children_and_events.py

Outputs:
    - CSV report to scripts/populate_report_{timestamp}.csv
    - Log to stdout + stderr
"""

import csv
import logging
import sys
from datetime import datetime
from pathlib import Path

# Odoo-standalone: must run inside the container or with PYTHONPATH set
try:
    import odoo
    from odoo import api
    from odoo.tools import config as odoo_config
except ImportError:
    print("ERROR: Odoo not found. Run inside container or set PYTHONPATH.")
    sys.exit(1)

_logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
REPORT_PATH = SCRIPT_DIR / f"populate_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

BATCH_SIZE = 50  # Commit every N operations to avoid memory buildup.


# ──────────────────────────────────────────────────────────────────────────────
# Main logic
# ──────────────────────────────────────────────────────────────────────────────


def populate_children_and_events():
    """Main entry point."""
    db = odoo_config["db_name"]
    registry = odoo.registry(db)

    report = {
        "children_processed": 0,
        "children_assigned": 0,
        "children_failed": 0,
        "events_processed": 0,
        "events_budget_created": 0,
        "events_teczka_created": 0,
        "events_program_created": 0,
        "events_failed": 0,
        "details": [],
    }

    with registry.cursor() as cr:
        env = api.Environment(cr, odoo.SUPERUSER_ID, {})

        # --- Phase 1: Populate children without group_id ---

        _logger.info("=== Phase 1: Populating children (group_id assignment) ===")
        report["details"].append(("children_start", "Finding children without group_id...", ""))

        participants = env["camp.participant"].search(
            [("group_id", "=", False), ("birth_date", "!=", False)]
        )
        _logger.info(f"Found {len(participants)} children without group_id")
        report["details"].append(("children_search", f"Found {len(participants)} children", ""))

        for participant in participants:
            report["children_processed"] += 1
            try:
                # Find a registration for this participant.
                reg = env["event.registration"].search(
                    [
                        ("participant_id", "=", participant.id),
                        ("state", "!=", "cancel"),
                    ],
                    limit=1,
                )
                if not reg:
                    report["details"].append(
                        (
                            "child_no_registration",
                            participant.display_name,
                            "No active registration found",
                        )
                    )
                    continue

                event = reg.event_id
                if not event:
                    report["details"].append(
                        (
                            "child_no_event",
                            participant.display_name,
                            "Registration has no event",
                        )
                    )
                    continue

                # Auto-split: distribute unassigned children into age-based groups.
                # action_auto_split returns only newly created groups, so child may
                # be assigned to an existing group if there's room.
                env["camp.group"].action_auto_split(event)

                # Reload the participant to pick up the group assignment.
                participant.refresh()
                if participant.group_id:
                    report["children_assigned"] += 1
                    report["details"].append(
                        (
                            "child_assigned",
                            participant.display_name,
                            f"→ {participant.group_id.name}",
                        )
                    )
                else:
                    report["children_failed"] += 1
                    report["details"].append(
                        (
                            "child_assignment_failed",
                            participant.display_name,
                            "Auto-split did not assign to a group",
                        )
                    )

            except Exception as exc:
                report["children_failed"] += 1
                _logger.exception(f"Error processing child {participant.display_name}: {exc}")
                report["details"].append(("child_error", participant.display_name, str(exc)))

            # Commit in batches.
            if report["children_processed"] % BATCH_SIZE == 0:
                cr.commit()
                _logger.info(f"Committed batch at child #{report['children_processed']}")

        cr.commit()

        # --- Phase 2: Populate events without budget/teczka/program ---

        _logger.info("=== Phase 2: Populating events (budget/teczka/program) ===")
        report["details"].append(
            ("events_start", "Finding events without budget/teczka/program...", "")
        )

        events = env["event.event"].search([("camp_program_id", "!=", False)])
        _logger.info(f"Found {len(events)} camp events")

        for event in events:
            report["events_processed"] += 1
            try:
                # --- Budget ---
                budget = event.camp_budget_id
                if not budget:
                    try:
                        budget = env["camp.budget"].create(
                            {
                                "event_id": event.id,
                                "planned_children": event.seats_max or 0,
                            }
                        )
                        budget._ensure_analytic()
                        report["events_budget_created"] += 1
                        _logger.info(f"Created budget for {event.name}")
                        report["details"].append(
                            ("event_budget_created", event.name, f"budget_id={budget.id}")
                        )
                    except Exception as exc:
                        _logger.exception(f"Failed to create budget for {event.name}: {exc}")
                        report["details"].append(("event_budget_failed", event.name, str(exc)))
                else:
                    report["details"].append(
                        ("event_budget_exists", event.name, f"budget_id={budget.id}")
                    )

                # --- Teczka KO ---
                teczka = env["camp.teczka.ko"].search([("event_id", "=", event.id)], limit=1)
                if not teczka:
                    try:
                        teczka = env["camp.teczka.ko"].create({"event_id": event.id})
                        report["events_teczka_created"] += 1
                        _logger.info(f"Created teczka.ko for {event.name}")
                        report["details"].append(
                            ("event_teczka_created", event.name, f"teczka_id={teczka.id}")
                        )
                    except Exception as exc:
                        _logger.exception(f"Failed to create teczka.ko for {event.name}: {exc}")
                        report["details"].append(("event_teczka_failed", event.name, str(exc)))
                else:
                    report["details"].append(
                        ("event_teczka_exists", event.name, f"teczka_id={teczka.id}")
                    )

                # --- Program Wypoczynku ---
                program = env["camp.program.wypoczynku"].search(
                    [("event_id", "=", event.id), ("state", "!=", False)], limit=1
                )
                if not program:
                    try:
                        program = env["camp.program.wypoczynku"].create(
                            {
                                "event_id": event.id,
                                "name": f"Program Wypoczynku — {event.name}",
                                "version": 1,
                                "state": "draft",
                            }
                        )
                        report["events_program_created"] += 1
                        _logger.info(f"Created program for {event.name}")
                        report["details"].append(
                            (
                                "event_program_created",
                                event.name,
                                f"program_id={program.id}",
                            )
                        )
                    except Exception as exc:
                        _logger.exception(f"Failed to create program for {event.name}: {exc}")
                        report["details"].append(("event_program_failed", event.name, str(exc)))
                else:
                    report["details"].append(
                        (
                            "event_program_exists",
                            event.name,
                            f"program_id={program.id}",
                        )
                    )

            except Exception as exc:
                report["events_failed"] += 1
                _logger.exception(f"Error processing event {event.name}: {exc}")
                report["details"].append(("event_error", event.name, str(exc)))

            # Commit in batches.
            if report["events_processed"] % BATCH_SIZE == 0:
                cr.commit()
                _logger.info(f"Committed batch at event #{report['events_processed']}")

        cr.commit()

    # --- Write CSV report ---

    _logger.info(f"=== Writing report to {REPORT_PATH} ===")
    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Operation", "Entity", "Result"])
        for op_type, entity, result in report["details"]:
            writer.writerow([op_type, entity, result])

    # --- Summary ---

    _logger.info(
        "=== Summary ===\n"
        f"Children processed: {report['children_processed']}\n"
        f"  - Assigned: {report['children_assigned']}\n"
        f"  - Failed: {report['children_failed']}\n"
        f"Events processed: {report['events_processed']}\n"
        f"  - Budget created: {report['events_budget_created']}\n"
        f"  - Teczka KO created: {report['events_teczka_created']}\n"
        f"  - Program created: {report['events_program_created']}\n"
        f"  - Failed: {report['events_failed']}\n"
        f"Report saved: {REPORT_PATH}"
    )

    return report


if __name__ == "__main__":
    try:
        result = populate_children_and_events()
        sys.exit(0 if result["children_failed"] + result["events_failed"] == 0 else 1)
    except Exception as exc:
        _logger.exception(f"Fatal error: {exc}")
        sys.exit(2)
