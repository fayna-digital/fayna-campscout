# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — N+1 query guard (OCA review: assertQueryCount).
#
# The portal cabinet renders a list of children for a parent. For each child it
# reads the "current booking" projection (current_registration_id,
# current_sale_order_id, current_camp_name, current_amount_total, ...). If any
# of those computed fields issued one query per record, a parent with K children
# would trigger O(K) extra queries — the classic N+1 that OCA flags.
#
# These tests pin the query budget for the bulk read so a future refactor that
# introduces a per-record query fails the suite instead of silently slowing the
# portal.
from odoo.tests.common import TransactionCase, tagged

_PARAM_SALES_ACTIVE = "fayna_camp_portal.sales_active"


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestQueryCount(TransactionCase):
    """assertQueryCount guard for the portal cabinet bulk read."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(cls.env.context, tracking_disable=True, no_reset_password=True)
        )
        cls.env["ir.config_parameter"].sudo().set_param(_PARAM_SALES_ACTIVE, "True")

        # Camp-program product linked to the event via camp_program_id so that
        # product.template.event_ids is populated — _init_camp_registrations
        # requires it (see commercial.py:1140).
        cls.product = cls.env["product.product"].create(
            {
                "name": "Obóz 2026 — Turnus 1",
                "type": "service",
                "list_price": 2000.0,
                "is_camp_program": True,
            }
        )
        cls.event = cls.env["event.event"].create(
            {
                "name": "Query Count Camp 2026",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-14 18:00:00",
                "camp_program_id": cls.product.product_tmpl_id.id,
            }
        )
        cls.ticket = cls.env["event.event.ticket"].create(
            {
                "name": "Standard",
                "event_id": cls.event.id,
                "product_id": cls.product.id,
            }
        )

    def _make_participant_with_booking(self, idx):
        """Create a child + a confirmed sale order with one registration."""
        partner = self.env["res.partner"].create(
            {"name": f"Parent {idx}", "email": f"parent{idx}@campscout.test"}
        )
        participant = self.env["camp.participant"].create(
            {
                "partner_id": self.env["res.partner"].create({"name": f"Child {idx}"}).id,
                "first_name": f"Child{idx}",
                "last_name": "Test",
            }
        )
        order = self.env["sale.order"].create({"partner_id": partner.id})
        self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "event_id": self.event.id,
                "event_ticket_id": self.ticket.id,
            }
        )
        order.action_confirm()
        reg = self.env["event.registration"].search(
            [("event_id", "=", self.event.id), ("sale_order_id", "=", order.id)],
            limit=1,
        )
        reg.participant_id = participant.id
        return participant

    def test_current_booking_bulk_read_is_constant_query(self):
        """Reading the current-booking projection across many children must not
        scale with the number of children (no N+1)."""
        participants = self.env["camp.participant"]
        for i in range(6):
            participants |= self._make_participant_with_booking(i)

        fields_to_read = [
            "current_registration_id",
            "current_sale_order_id",
            "current_camp_name",
            "current_amount_total",
            "current_currency_id",
            "current_insurance_name",
            "current_merch_name",
        ]

        # Warm the cache / flush so the measured block is the pure compute pass.
        participants.read(fields_to_read)

        with self.assertQueryCount(1):
            # A single SELECT of the stored/computed projection for all rows.
            participants.read(fields_to_read)

        # Sanity: the projection actually resolved for every child.
        for p in participants:
            self.assertTrue(
                p.current_registration_id,
                f"participant {p.id} should have a current booking",
            )
            self.assertTrue(
                p.current_sale_order_id,
                f"participant {p.id} should have a current sale order",
            )

    def test_display_name_bulk_read_is_constant_query(self):
        """display_name is stored, so a bulk read must be a single query."""
        participants = self.env["camp.participant"]
        for i in range(5):
            participants |= self._make_participant_with_booking(i)

        participants.read(["display_name"])

        with self.assertQueryCount(1):
            participants.read(["display_name"])

        for p in participants:
            self.assertTrue(p.display_name)
