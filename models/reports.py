# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Camp reports & analytics models (migrated from fayna_camp_reports).

Consolidates three models that capture or render camp performance data:

* ``camp.analytics.snapshot`` — daily KPI snapshot (attendance, finance,
  qualification cards, ops). Immutable historical fact.
* ``camp.stats.snapshot`` — daily occupancy + revenue snapshot used for
  trend graphs.
* ``camp.marketing.report`` — TransientModel wizard for ad-hoc report
  generation (Registrations / Revenue / Occupancy / Age distribution).

These were previously housed in the ``fayna_camp_reports`` module which is
being decomissioned. Per master TZ §16 (Strangler Fig) the camp vertical
collapses into a single ``fayna_camp_portal`` module.

Security:
    * snapshots — admin-only (``group_camp_organizator``).
    * marketing report wizard — admin + sales (``group_camp_sales``).

Performance:
    * Many2one + ``snapshot_date`` indexed for fast pivot/graph queries.
    * Revenue queries cross security via ``sudo()`` (sales orders),
      isolated to the snapshot writer.
"""

from __future__ import annotations

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


# =====================================================================
# camp.analytics.snapshot — KPI snapshot per event per day (immutable)
# =====================================================================
class CampAnalyticsSnapshot(models.Model):
    """Periodic KPI snapshot for a camp event.

    Captures attendance, financial, and operational metrics at a point in
    time. Records become read-only after creation to preserve the
    historical fact. Written by :meth:`_cron_take_daily_snapshot`; can also
    be created manually with ``snapshot_allow_write=True`` in context.
    """

    _name = "camp.analytics.snapshot"
    _description = "Camp Analytics KPI Snapshot"
    _order = "snapshot_date desc, id desc"
    _rec_name = "display_name"

    # ---------------- Core ------------------------------------------------
    event_id = fields.Many2one(
        "event.event",
        string="Camp Event",
        required=True,
        index=True,
        ondelete="cascade",
    )
    snapshot_date = fields.Date(
        string="Snapshot Date",
        default=fields.Date.context_today,
        required=True,
        index=True,
    )

    # ---------------- Attendance -----------------------------------------
    registered_count = fields.Integer(string="Registered", default=0)
    confirmed_count = fields.Integer(string="Confirmed", default=0)
    cancelled_count = fields.Integer(string="Cancelled", default=0)
    occupancy_rate = fields.Float(
        string="Occupancy Rate (%)",
        digits=(5, 2),
        default=0.0,
    )
    qualification_signed_count = fields.Integer(
        string="Qualifications Signed",
        default=0,
        help="Number of qualification cards signed at the time of this snapshot.",
    )

    # ---------------- Financial ------------------------------------------
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    revenue_total = fields.Monetary(
        string="Revenue Total",
        currency_field="currency_id",
        default=0.0,
    )
    revenue_paid = fields.Monetary(
        string="Revenue Paid",
        currency_field="currency_id",
        default=0.0,
    )
    revenue_pending = fields.Monetary(
        string="Revenue Pending",
        currency_field="currency_id",
        default=0.0,
    )
    avg_order_value = fields.Float(
        string="Avg Order Value",
        digits=(10, 2),
        default=0.0,
        help="Average sale order value for registrations at the time of this snapshot.",
    )

    # ---------------- Operations -----------------------------------------
    incidents_count = fields.Integer(string="Incidents", default=0)
    support_requests_count = fields.Integer(string="Support Requests", default=0)

    # ---------------- Display --------------------------------------------
    display_name = fields.Char(
        string="Label",
        compute="_compute_display_name",
        store=True,
    )

    _sql_constraints = [
        (
            "analytics_snapshot_event_date_unique",
            "UNIQUE(event_id, snapshot_date)",
            "An analytics snapshot for this event and date already exists.",
        ),
    ]

    @api.depends("event_id", "snapshot_date")
    def _compute_display_name(self):
        for rec in self:
            event_name = rec.event_id.name if rec.event_id else "?"
            date_str = str(rec.snapshot_date) if rec.snapshot_date else "?"
            rec.display_name = f"{event_name} / {date_str}"

    # ------------------------------------------------------------------
    # Immutability guard — snapshots are historical facts.
    # ------------------------------------------------------------------
    def write(self, vals):
        """Reject writes after creation, except ORM recompute of stored
        computed fields and explicit internal context bypass.
        """
        computed_only = set(vals.keys()) <= {"display_name"}
        if computed_only or self.env.context.get("snapshot_allow_write"):
            return super().write(vals)
        raise UserError(
            _(
                "Analytics snapshots are read-only after creation. "
                "They represent historical facts and cannot be edited.",
            ),
        )

    # ------------------------------------------------------------------
    # Cron — daily snapshot at 03:00.
    # ------------------------------------------------------------------
    @api.model
    def _cron_take_daily_snapshot(self):
        """Iterate active events and create one KPI snapshot per event for
        today. Idempotent — skips events that already have a snapshot.
        """
        today = fields.Date.today()
        events = self.env["event.event"].search(
            [
                ("state", "not in", ("cancel", "done")),
                ("date_end", ">=", fields.Datetime.now()),
            ],
        )
        _logger.info(
            "fayna_camp_portal: analytics daily snapshot — %d active events for %s",
            len(events),
            today,
        )
        for event in events:
            try:
                self._take_analytics_snapshot(event, today)
            except (UserError, ValidationError, ValueError, KeyError):
                _logger.exception(
                    "fayna_camp_portal: analytics snapshot failed for event %s",
                    event.id,
                )

    @api.model
    def _take_analytics_snapshot(self, event, snapshot_date):
        """Create one analytics snapshot for *event* on *snapshot_date*.

        Idempotent: if a record exists for this event+date it is skipped
        (snapshots are immutable historical facts — no update on re-run).
        """
        existing = self.search(
            [("event_id", "=", event.id), ("snapshot_date", "=", snapshot_date)],
            limit=1,
        )
        if existing:
            return existing

        # ---- Attendance ----
        all_regs = self.env["event.registration"].search(
            [("event_id", "=", event.id)],
        )
        registered_count = len(all_regs.filtered(lambda r: r.state != "cancel"))
        confirmed_count = len(all_regs.filtered(lambda r: r.state == "done"))
        cancelled_count = len(all_regs.filtered(lambda r: r.state == "cancel"))

        capacity = event.seats_max or 0
        occupancy_rate = (registered_count / capacity * 100.0) if capacity > 0 else 0.0

        # ---- Qualification cards (graceful degradation) ----
        qualification_signed_count = 0
        if "camp.participant" in self.env:
            qualification_signed_count = self.env["camp.participant"].search_count(
                [
                    ("event_id", "=", event.id),
                    ("qualification_state", "=", "signed"),
                ],
            )

        # ---- Revenue (sudo crosses SO security boundary) ----
        partner_ids = all_regs.filtered(lambda r: r.state != "cancel").mapped("partner_id").ids
        revenue_total = 0.0
        revenue_paid = 0.0
        revenue_pending = 0.0
        avg_order_value = 0.0

        if partner_ids:
            orders = (
                self.env["sale.order"]
                .sudo()
                .search(
                    [
                        ("partner_id", "in", partner_ids),
                        ("state", "in", ["sale", "done"]),
                    ],
                )
            )
            revenue_total = sum(orders.mapped("amount_total"))
            paid_orders = orders.filtered(lambda o: o.invoice_status == "invoiced")
            revenue_paid = sum(paid_orders.mapped("amount_total"))
            revenue_pending = revenue_total - revenue_paid
            order_count = len(orders)
            avg_order_value = (revenue_total / order_count) if order_count > 0 else 0.0

        vals = {
            "event_id": event.id,
            "snapshot_date": snapshot_date,
            "registered_count": registered_count,
            "confirmed_count": confirmed_count,
            "cancelled_count": cancelled_count,
            "occupancy_rate": occupancy_rate,
            "qualification_signed_count": qualification_signed_count,
            "revenue_total": revenue_total,
            "revenue_paid": revenue_paid,
            "revenue_pending": revenue_pending,
            "avg_order_value": avg_order_value,
            "currency_id": self.env.company.currency_id.id,
        }
        return self.with_context(snapshot_allow_write=True).create(vals)


# =====================================================================
# camp.stats.snapshot — daily occupancy + revenue (used by trend graphs)
# =====================================================================
class CampStatsSnapshot(models.Model):
    """Daily snapshot of camp occupancy and revenue metrics.

    Stored records used for dashboard trend graphs. Written once per day by
    :meth:`_cron_take_snapshot`. Unlike ``camp.analytics.snapshot`` this
    model permits updates so the cron can re-run safely on the same day
    (the constraint is one row per (event, date)).
    """

    _name = "camp.stats.snapshot"
    _description = "Camp Daily Stats Snapshot"
    _order = "snapshot_date desc, id desc"
    _rec_name = "display_name"

    event_id = fields.Many2one(
        "event.event",
        string="Camp Event",
        required=True,
        index=True,
        ondelete="cascade",
    )
    snapshot_date = fields.Date(
        string="Snapshot Date",
        required=True,
        index=True,
        default=fields.Date.context_today,
    )

    total_registered = fields.Integer(string="Total Registered", default=0)
    total_capacity = fields.Integer(string="Total Capacity", default=0)
    total_revenue = fields.Monetary(
        string="Total Revenue",
        currency_field="currency_id",
        default=0.0,
    )
    occupancy_pct = fields.Float(
        string="Occupancy (%)",
        digits=(6, 2),
        default=0.0,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    display_name = fields.Char(
        string="Label",
        compute="_compute_display_name",
        store=True,
    )

    _sql_constraints = [
        (
            "stats_event_date_unique",
            "UNIQUE(event_id, snapshot_date)",
            "A snapshot for this event and date already exists.",
        ),
    ]

    @api.depends("event_id", "snapshot_date")
    def _compute_display_name(self):
        for rec in self:
            event_name = rec.event_id.name or "?"
            date_str = str(rec.snapshot_date) if rec.snapshot_date else "?"
            rec.display_name = f"{event_name} / {date_str}"

    # ------------------------------------------------------------------
    # Cron — daily at 02:00.
    # ------------------------------------------------------------------
    @api.model
    def _cron_take_snapshot(self):
        """Iterate all active events and upsert one snapshot per event for
        today's date.
        """
        today = fields.Date.today()
        events = self.env["event.event"].search(
            [("date_end", ">=", fields.Datetime.now())],
        )
        _logger.info(
            "fayna_camp_portal: stats snapshot — %d active events for %s",
            len(events),
            today,
        )
        for event in events:
            try:
                self._take_event_snapshot(event, today)
            except (UserError, ValidationError, ValueError, KeyError):
                _logger.exception(
                    "fayna_camp_portal: stats snapshot failed for event %s",
                    event.id,
                )

    @api.model
    def _take_event_snapshot(self, event, snapshot_date):
        """Create or update the snapshot for one event on one date."""
        registrations = self.env["event.registration"].search(
            [
                ("event_id", "=", event.id),
                ("state", "not in", ["cancel"]),
            ],
        )
        total_registered = len(registrations)
        total_capacity = event.seats_max or 0
        occupancy_pct = (total_registered / total_capacity * 100.0) if total_capacity > 0 else 0.0

        partner_ids = registrations.mapped("partner_id").ids
        total_revenue = 0.0
        if partner_ids:
            orders = (
                self.env["sale.order"]
                .sudo()
                .search(
                    [
                        ("partner_id", "in", partner_ids),
                        ("state", "in", ["sale", "done"]),
                    ],
                )
            )
            total_revenue = sum(orders.mapped("amount_total"))

        vals = {
            "event_id": event.id,
            "snapshot_date": snapshot_date,
            "total_registered": total_registered,
            "total_capacity": total_capacity,
            "total_revenue": total_revenue,
            "occupancy_pct": occupancy_pct,
            "currency_id": self.env.company.currency_id.id,
        }

        existing = self.search(
            [("event_id", "=", event.id), ("snapshot_date", "=", snapshot_date)],
            limit=1,
        )
        if existing:
            existing.write(vals)
            return existing
        return self.create(vals)


# =====================================================================
# camp.marketing.report — wizard, ad-hoc analytics
# =====================================================================
class CampMarketingReport(models.TransientModel):
    """Wizard for generating camp analytics reports.

    Computes live metrics across registrations + sales orders for a chosen
    event and date range. Used by sales + organizator (admin) staff.
    """

    _name = "camp.marketing.report"
    _description = "Camp Analytics Report Wizard"

    # ---------------- Filters --------------------------------------------
    event_id = fields.Many2one(
        "event.event",
        string="Camp Event",
        required=True,
        index=True,
    )
    date_from = fields.Date(
        string="Date From",
        required=True,
        default=fields.Date.context_today,
    )
    date_to = fields.Date(
        string="Date To",
        required=True,
        default=fields.Date.context_today,
    )
    report_type = fields.Selection(
        [
            ("registrations", "Registrations"),
            ("revenue", "Revenue"),
            ("occupancy", "Occupancy"),
            ("age_distribution", "Age Distribution"),
        ],
        string="Report Type",
        required=True,
        default="registrations",
    )

    # ---------------- Computed metrics -----------------------------------
    total_registrations = fields.Integer(
        string="Total Registrations",
        compute="_compute_metrics",
    )
    total_revenue = fields.Monetary(
        string="Total Revenue",
        compute="_compute_metrics",
        compute_sudo=True,
        currency_field="currency_id",
    )
    occupancy_rate = fields.Float(
        string="Occupancy Rate (%)",
        compute="_compute_metrics",
        digits=(6, 2),
    )
    avg_age = fields.Float(
        string="Average Age",
        compute="_compute_metrics",
        digits=(6, 1),
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )

    _sql_constraints = [
        (
            "marketing_report_date_range_check",
            "CHECK(date_from <= date_to)",
            "Date From must be before or equal to Date To.",
        ),
    ]

    @api.depends("event_id", "date_from", "date_to")
    def _compute_metrics(self):
        for rec in self:
            if not rec.event_id:
                rec.total_registrations = 0
                rec.total_revenue = 0.0
                rec.occupancy_rate = 0.0
                rec.avg_age = 0.0
                continue

            event = rec.event_id

            # ---- Registrations ----
            registrations = self.env["event.registration"].search(
                [
                    ("event_id", "=", event.id),
                    ("state", "not in", ["cancel"]),
                    (
                        "create_date",
                        ">=",
                        fields.Datetime.from_string(str(rec.date_from)),
                    ),
                    (
                        "create_date",
                        "<=",
                        fields.Datetime.from_string(
                            str(rec.date_to) + " 23:59:59",
                        ),
                    ),
                ],
            )
            rec.total_registrations = len(registrations)

            # ---- Revenue (compute_sudo crosses SO security boundary) ----
            partner_ids = registrations.mapped("partner_id").ids
            if partner_ids:
                orders = (
                    self.env["sale.order"]
                    .sudo()
                    .search(
                        [
                            ("partner_id", "in", partner_ids),
                            ("state", "in", ["sale", "done"]),
                            ("date_order", ">=", str(rec.date_from)),
                            (
                                "date_order",
                                "<=",
                                str(rec.date_to) + " 23:59:59",
                            ),
                        ],
                    )
                )
                rec.total_revenue = sum(orders.mapped("amount_total"))
            else:
                rec.total_revenue = 0.0

            # ---- Occupancy ----
            capacity = event.seats_max or 0
            rec.occupancy_rate = (
                (rec.total_registrations / capacity) * 100.0 if capacity > 0 else 0.0
            )

            # ---- Average age ----
            ages = []
            for reg in registrations:
                if reg.partner_id and reg.partner_id.birthday:
                    delta = fields.Date.today() - reg.partner_id.birthday
                    ages.append(delta.days / 365.25)
            rec.avg_age = (sum(ages) / len(ages)) if ages else 0.0

    def action_generate_report(self):
        """Render a QWeb PDF of the wizard data, if a matching report
        action is registered. The PDF template lives outside this model
        scope; if it is not present we surface the metrics inline.
        """
        self.ensure_one()
        report = self.env.ref(
            "fayna_camp_portal.action_report_camp_stats",
            raise_if_not_found=False,
        )
        if report:
            return report.report_action(self)
        # Fallback — keep wizard usable even without a PDF template.
        raise UserError(
            _(
                "PDF report template is not installed. Live metrics are visible above.",
            ),
        )
