# Copyright 2026 Fayna Digital — Volodymyr Shevchenko
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Camp transport — one transport trip record per camp shift.

Migrated from the standalone ``fayna_camp_transport`` module into
``fayna_camp_portal`` as part of the consolidation per master TZ.

PL law requires documenting all transport per shift. A trip record covers
a single departure or return journey (bus, train, own transport, excursion).

Inherits ``portal.mixin`` so the parent portal page ``/my/transport/<id>``
gets a stable signed URL plus a ``portal.message_thread`` chatter (matching
the convention in ``portal_mixin_extensions.py``).
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CampTransport(models.Model):
    """One transport trip record — one journey for a group of participants."""

    _name = "camp.transport"
    _description = "Camp transport trip"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "departure_datetime desc"

    # ── Computed display name ──────────────────────────────────────────────
    name = fields.Char(
        string="Name",
        compute="_compute_name",
        store=True,
    )

    @api.depends("trip_type", "event_id", "departure_datetime")
    def _compute_name(self):
        trip_labels = dict(self._fields["trip_type"].selection)
        for rec in self:
            trip_label = trip_labels.get(rec.trip_type or "arrival", "")
            event_name = rec.event_id.name if rec.event_id else ""
            if rec.departure_datetime:
                date_str = fields.Datetime.context_timestamp(rec, rec.departure_datetime).strftime(
                    "%Y-%m-%d"
                )
            else:
                date_str = ""
            parts = [p for p in [trip_label, event_name, date_str] if p]
            rec.name = " — ".join(parts) if parts else _("New trip")

    # ── Core ───────────────────────────────────────────────────────────────
    event_id = fields.Many2one(
        "event.event",
        string="Camp shift",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )

    trip_type = fields.Selection(
        [
            ("arrival", "Przyjazd (Arrival)"),
            ("departure", "Wyjazd (Departure)"),
            ("excursion", "Wycieczka"),
            ("other", "Inne"),
        ],
        string="Trip type",
        required=True,
        default="arrival",
        tracking=True,
    )

    # ── Route ──────────────────────────────────────────────────────────────
    departure_location = fields.Char(
        string="Departure location",
        required=True,
        help="e.g. 'Warszawa Centralna'",
    )
    arrival_location = fields.Char(
        string="Arrival location",
        required=True,
        help="e.g. 'Kielce — baza obozu'",
    )
    departure_datetime = fields.Datetime(
        string="Departure date/time",
        required=True,
        tracking=True,
    )
    arrival_datetime = fields.Datetime(
        string="Arrival date/time",
    )

    # ── Vehicle & driver ───────────────────────────────────────────────────
    vehicle_type = fields.Selection(
        [
            ("bus", "Autobus"),
            ("minibus", "Minibus"),
            ("train", "Pociąg"),
            ("own_transport", "Transport własny rodziców"),
        ],
        string="Vehicle type",
    )
    vehicle_registration = fields.Char(
        string="License plate",
        help="e.g. 'DW 1234AB'",
    )
    driver_name = fields.Char(string="Driver name")
    driver_phone = fields.Char(string="Driver phone")
    transport_company = fields.Char(
        string="Transport company",
        help="Name of the carrier / bus company",
    )

    # ── Participants ───────────────────────────────────────────────────────
    participant_ids = fields.Many2many(
        "camp.participant",
        "camp_transport_participant_rel",
        "transport_id",
        "participant_id",
        string="Participants",
    )
    participant_count = fields.Integer(
        string="Passenger count",
        compute="_compute_participant_count",
        store=True,
    )

    @api.depends("participant_ids")
    def _compute_participant_count(self):
        for rec in self:
            rec.participant_count = len(rec.participant_ids)

    # ── State ──────────────────────────────────────────────────────────────
    state = fields.Selection(
        [
            ("planned", "Zaplanowany"),
            ("confirmed", "Potwierdzony"),
            ("completed", "Zrealizowany"),
            ("cancelled", "Anulowany"),
        ],
        string="Status",
        default="planned",
        required=True,
        tracking=True,
    )

    # ── Extra ──────────────────────────────────────────────────────────────
    notes = fields.Text(string="Notes")
    waybill_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Passenger list (waybill)",
        help="Scanned or uploaded list of passengers",
    )

    # ── Computed flags ─────────────────────────────────────────────────────
    is_overdue = fields.Boolean(
        string="Overdue",
        compute="_compute_is_overdue",
        search="_search_is_overdue",
        help="Arrival datetime passed but trip is still in planned state",
    )

    @api.depends("arrival_datetime", "state")
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_overdue = bool(
                rec.arrival_datetime and rec.arrival_datetime < now and rec.state == "planned"
            )

    def _search_is_overdue(self, operator, value):
        """Make the computed flag searchable (для фільтра «Spóźnione»)."""
        now = fields.Datetime.now()
        overdue = ["&", ("arrival_datetime", "<", now), ("state", "=", "planned")]
        positive = (operator == "=" and value) or (operator == "!=" and not value)
        return overdue if positive else ["!"] + overdue

    # ── Portal mixin: signed access URL for /my/transport/<id> ─────────────
    def _compute_access_url(self):
        super()._compute_access_url()
        for rec in self:
            rec.access_url = f"/my/transport/{rec.id}"

    # ── Constraints ────────────────────────────────────────────────────────
    @api.constrains("departure_datetime", "arrival_datetime")
    def _check_datetimes(self):
        for rec in self:
            if (
                rec.arrival_datetime
                and rec.departure_datetime
                and rec.arrival_datetime < rec.departure_datetime
            ):
                raise UserError(
                    _(
                        "Arrival date/time (%(arrival)s) cannot be earlier "
                        "than departure (%(dep)s).",
                        arrival=rec.arrival_datetime,
                        dep=rec.departure_datetime,
                    )
                )

    # ── Actions ────────────────────────────────────────────────────────────
    def action_confirm(self):
        """Confirm the transport trip."""
        for rec in self:
            if rec.state not in ("planned",):
                raise UserError(
                    _(
                        "Only planned trips can be confirmed. " "Current state: %(state)s",
                        state=rec.state,
                    )
                )
            rec.write({"state": "confirmed"})
        return True

    def action_complete(self):
        """Mark trip as completed."""
        for rec in self:
            if rec.state == "cancelled":
                raise UserError(_("Cannot complete a cancelled trip."))
            rec.write({"state": "completed"})
        return True

    def action_cancel(self):
        """Cancel the trip."""
        for rec in self:
            if rec.state == "completed":
                raise UserError(_("Cannot cancel an already completed trip."))
            rec.write({"state": "cancelled"})
        return True
