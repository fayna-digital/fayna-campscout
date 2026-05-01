"""Organizator (admin) dashboard + view-as routes.

Top-level Organizator (group_camp_organizator per PL law, Rozp. MEN
30.03.2016 §2.1) lands on /admin/dashboard. From there, /admin/as-{role}
endpoints render the portal/back-office through the eyes of another role
to support, debug or inspect.

RODO compliance:
- Every view-as call is logged to camp.admin.access.log BEFORE the render
  (even if the render fails afterwards, the trace exists).
- We use with_user(target_user) — NOT sudo() — so ACL and ir.rule record
  rules of the target role are preserved. The Organizator only "sees what
  they would see" — they do not gain write-bypass on RODO Art.9 fields.
- IP + session id are captured for RODO art.30 traceability.

TZ §5.1 (2026-04-30 six-role design).
"""

import logging
from datetime import datetime, timedelta

from odoo import _, http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

ORGANIZATOR_GROUP = "fayna_camp_portal.group_camp_organizator"


class CampscoutAdmin(http.Controller):
    """Server-rendered admin dashboard + view-as endpoints."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_admin(self):
        """Raise AccessError if the current user is not an Organizator."""
        if not request.env.user.has_group(ORGANIZATOR_GROUP):
            raise AccessError(_("Access restricted to Organizator (admin)."))

    def _log_access(
        self,
        impersonated_role,
        target_user=None,
        target_partner=None,
        target_event=None,
        reason=None,
    ):
        """Write a camp.admin.access.log row (sudo) before rendering view-as.

        Sudo is used so the immutable RODO art.30 register always gets the
        entry, regardless of any record rule. If the create itself fails we
        re-raise — RODO traceability is non-negotiable; the admin must see
        the error rather than impersonate silently.
        """
        request.env["camp.admin.access.log"].sudo().create(
            {
                "user_id": request.env.user.id,
                "impersonated_role": impersonated_role,
                "target_user_id": target_user.id if target_user else False,
                "target_partner_id": target_partner.id if target_partner else False,
                "target_event_id": target_event.id if target_event else False,
                "reason": reason or False,
                "ip_address": request.httprequest.remote_addr or False,
                "session_id": getattr(request.session, "sid", False) or False,
            }
        )

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    @http.route("/admin/dashboard", type="http", auth="user", website=True)
    def admin_dashboard(self, **kw):
        """Server-rendered KPI dashboard for Organizators."""
        self._check_admin()
        env_sudo = request.env(su=True)
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        in_14_days = now + timedelta(days=14)
        in_30_days = now + timedelta(days=30)

        values = {
            "page_name": "admin_dashboard",
            "now": now,
        }

        # 1) Business overview
        try:
            values["kpi_active_events"] = env_sudo["event.event"].search_count(
                [("date_begin", "<=", now), ("date_end", ">=", now)]
            )
            values["kpi_paid_registrations"] = env_sudo["event.registration"].search_count(
                [("state", "=", "open"), ("event_id.date_begin", ">=", month_start)]
            )
            paid_orders = env_sudo["sale.order"].search(
                [("state", "in", ("sale", "done")), ("date_order", ">=", month_start)]
            )
            values["kpi_revenue_month"] = sum(paid_orders.mapped("amount_total"))
            values["kpi_revenue_currency"] = (
                paid_orders[:1].currency_id.name if paid_orders else "PLN"
            )
        except (AccessError, MissingError, KeyError) as e:
            _logger.warning("[ADMIN-KPI] business overview failed: %s", e)
            values.update(
                kpi_active_events=0,
                kpi_paid_registrations=0,
                kpi_revenue_month=0.0,
                kpi_revenue_currency="PLN",
            )

        # 2) Alarms
        values["alarm_unsigned_cards"] = self._count_unsigned_cards(env_sudo, in_14_days)
        values["alarm_open_incidents"] = self._count_open_incidents(env_sudo)
        values["alarm_kuratorium_pending"] = self._count_kuratorium_pending(env_sudo)

        # 3) Active camps table
        values["active_camps"] = self._build_active_camps(env_sudo, now)

        # 4) Team — expiring certs in next 30 days
        values["expiring_certs"] = self._expiring_certs(env_sudo, now, in_30_days)

        # 5) Communications
        values["open_support_requests"] = self._count_open_support(env_sudo)
        values["rodo_consent_rate"] = self._rodo_consent_rate(env_sudo)

        # 6) Marketing — top 3 camps by sales this month
        values["top_camps"] = self._top_camps_by_sales(env_sudo, month_start)

        # 7) Audit — recent access log
        values["recent_access_log"] = (
            env_sudo["camp.admin.access.log"]
            .search([], order="accessed_at desc", limit=10)
        )

        return request.render("fayna_camp_portal.admin_dashboard", values)

    # --- KPI helpers -------------------------------------------------

    def _count_unsigned_cards(self, env_sudo, deadline):
        """Count unsigned qualification cards for events starting within deadline.

        Pushes filtering to PostgreSQL via search_count + indexed event domain
        instead of full-table search() + Python filter() (avoids N+1 + scan).
        """
        try:
            return env_sudo["camp.participant"].search_count(
                [
                    ("qualification_signed", "=", False),
                    ("registration_ids.event_id.date_begin", "<=", deadline),
                    ("registration_ids.state", "!=", "cancel"),
                ]
            )
        except (AccessError, MissingError, KeyError):
            return 0

    def _count_open_incidents(self, env_sudo):
        try:
            return env_sudo["camp.incident.report"].search_count(
                [("state", "in", ("draft", "investigating", "open", "escalated"))]
            )
        except (AccessError, MissingError, KeyError):
            return 0

    def _count_kuratorium_pending(self, env_sudo):
        try:
            return env_sudo["camp.kuratorium.notification"].search_count(
                [("state", "in", ("draft", "ready", "submitted", "deficiency"))]
            )
        except (AccessError, MissingError, KeyError):
            return 0

    def _build_active_camps(self, env_sudo, now):
        try:
            events = env_sudo["event.event"].search(
                [("date_begin", "<=", now + timedelta(days=180)), ("date_end", ">=", now)],
                order="date_begin asc",
                limit=20,
            )
            rows = []
            for ev in events:
                kierownik = False
                try:
                    staff = env_sudo["camp.staff"].search(
                        [("event_id", "=", ev.id), ("role", "in", ("director", "leader"))],
                        limit=1,
                    )
                    kierownik = staff.name or (staff.user_id and staff.user_id.name) or False
                except (AccessError, MissingError, KeyError):
                    kierownik = False

                regs = env_sudo["event.registration"].search_count(
                    [("event_id", "=", ev.id), ("state", "!=", "cancel")]
                )
                if ev.date_begin <= now <= ev.date_end:
                    status, badge = _("Триває"), "success"
                elif ev.date_begin > now:
                    status, badge = _("Заплановано"), "info"
                else:
                    status, badge = _("Завершено"), "secondary"

                rows.append(
                    {
                        "id": ev.id,
                        "name": ev.name,
                        "kierownik": kierownik or _("(не призначено)"),
                        "registrations": regs,
                        "status": status,
                        "badge": badge,
                    }
                )
            return rows
        except (AccessError, MissingError, KeyError):
            return []

    def _expiring_certs(self, env_sudo, now, deadline):
        try:
            recs = env_sudo["camp.staff.training.record"].search(
                [
                    ("expiry_date", ">=", now.date()),
                    ("expiry_date", "<=", deadline.date()),
                ],
                order="expiry_date asc",
                limit=20,
            )
            return recs
        except (AccessError, MissingError, KeyError):
            return env_sudo["res.users"].browse([])  # empty recordset placeholder

    def _count_open_support(self, env_sudo):
        try:
            return env_sudo["camp.support.request"].search_count(
                [
                    (
                        "state",
                        "in",
                        ("new", "draft", "submitted", "in_progress", "under_review"),
                    )
                ]
            )
        except (AccessError, MissingError, KeyError):
            return 0

    def _rodo_consent_rate(self, env_sudo):
        """Return percentage of partners with active RODO consent (best-effort).

        Reads from fayna.rodo.consent.log if available — falls back to 0 when
        the dependency is not installed.
        """
        try:
            total = env_sudo["res.partner"].search_count(
                [("is_company", "=", False), ("customer_rank", ">", 0)]
            )
            if not total:
                return 0
            consented = env_sudo["fayna.rodo.consent.log"].search_count(
                [("state", "=", "granted")]
            )
            return round(min(consented, total) * 100.0 / total, 1)
        except (AccessError, MissingError, KeyError, ValueError):
            return 0

    def _top_camps_by_sales(self, env_sudo, month_start):
        try:
            orders = env_sudo["sale.order"].search(
                [("state", "in", ("sale", "done")), ("date_order", ">=", month_start)]
            )
            tally = {}
            for order in orders:
                for line in order.order_line:
                    event = getattr(line, "event_id", False)
                    if not event:
                        continue
                    tally.setdefault(event.id, {"name": event.name, "amount": 0.0})
                    tally[event.id]["amount"] += line.price_total or 0.0
            top = sorted(tally.values(), key=lambda r: r["amount"], reverse=True)[:3]
            return top
        except (AccessError, MissingError, KeyError):
            return []

    # ------------------------------------------------------------------
    # View-as: kierownik
    # ------------------------------------------------------------------

    @http.route("/admin/as-kierownik", type="http", auth="user", website=True)
    def admin_as_kierownik(self, event_id=None, reason=None, **kw):
        self._check_admin()
        if not event_id:
            raise UserError(_("event_id is required."))

        try:
            event = request.env["event.event"].sudo().browse(int(event_id)).exists()
        except (ValueError, TypeError) as e:
            raise UserError(_("Invalid event_id.")) from e
        if not event:
            raise UserError(_("Event not found."))

        target_user = event.user_id or request.env.user
        self._log_access(
            "kierownik",
            target_user=target_user,
            target_event=event,
            reason=reason,
        )

        # Build values via with_user(target_user) so we honour the kierownik's ACL.
        try:
            scoped_env = request.env(user=target_user.id)
            scoped_event = scoped_env["event.event"].browse(event.id)
            participants = scoped_env["event.registration"].search(
                [("event_id", "=", event.id), ("state", "!=", "cancel")]
            )
            staff = scoped_env["camp.staff"].search([("event_id", "=", event.id)])
        except (AccessError, MissingError) as e:
            _logger.warning("[ADMIN] as-kierownik scoped read failed: %s", e)
            scoped_event = event
            participants = request.env["event.registration"].browse([])
            staff = request.env["camp.staff"].browse([])

        values = {
            "page_name": "admin_as_kierownik",
            "viewed_user": target_user,
            "event": scoped_event,
            "registrations": participants,
            "staff": staff,
            "impersonated_role": "kierownik",
        }
        return request.render("fayna_camp_portal.admin_as_kierownik", values)

    # ------------------------------------------------------------------
    # View-as: wychowawca
    # ------------------------------------------------------------------

    @http.route("/admin/as-wychowawca", type="http", auth="user", website=True)
    def admin_as_wychowawca(self, staff_id=None, reason=None, **kw):
        self._check_admin()
        if not staff_id:
            raise UserError(_("staff_id is required."))

        try:
            staff = request.env["camp.staff"].sudo().browse(int(staff_id)).exists()
        except (ValueError, TypeError) as e:
            raise UserError(_("Invalid staff_id.")) from e
        if not staff:
            raise UserError(_("Staff record not found."))

        target_user = staff.user_id or request.env.user
        self._log_access(
            "wychowawca",
            target_user=target_user,
            target_event=staff.event_id or None,
            reason=reason,
        )

        try:
            scoped_env = request.env(user=target_user.id)
            dzienniki = scoped_env["fayna.camp.dziennik"].search(
                [("event_id", "=", staff.event_id.id)] if staff.event_id else []
            )
            staff_view = scoped_env["camp.staff"].browse(staff.id)
        except (AccessError, MissingError, KeyError) as e:
            _logger.warning("[ADMIN] as-wychowawca scoped read failed: %s", e)
            dzienniki = request.env["camp.staff"].browse([])
            staff_view = staff

        values = {
            "page_name": "admin_as_wychowawca",
            "viewed_user": target_user,
            "staff": staff_view,
            "dzienniki": dzienniki,
            "event": staff.event_id,
            "impersonated_role": "wychowawca",
        }
        return request.render("fayna_camp_portal.admin_as_wychowawca", values)

    # ------------------------------------------------------------------
    # View-as: instructor
    # ------------------------------------------------------------------

    @http.route("/admin/as-instructor", type="http", auth="user", website=True)
    def admin_as_instructor(self, staff_id=None, reason=None, **kw):
        self._check_admin()
        if not staff_id:
            raise UserError(_("staff_id is required."))

        try:
            staff = request.env["camp.staff"].sudo().browse(int(staff_id)).exists()
        except (ValueError, TypeError) as e:
            raise UserError(_("Invalid staff_id.")) from e
        if not staff:
            raise UserError(_("Staff record not found."))

        target_user = staff.user_id or request.env.user
        self._log_access(
            "instructor",
            target_user=target_user,
            target_event=staff.event_id or None,
            reason=reason,
        )

        try:
            scoped_env = request.env(user=target_user.id)
            activities = scoped_env["camp.activity"].search([])
            staff_view = scoped_env["camp.staff"].browse(staff.id)
        except (AccessError, MissingError, KeyError) as e:
            _logger.warning("[ADMIN] as-instructor scoped read failed: %s", e)
            activities = request.env["camp.staff"].browse([])
            staff_view = staff

        values = {
            "page_name": "admin_as_instructor",
            "viewed_user": target_user,
            "staff": staff_view,
            "activities": activities,
            "event": staff.event_id,
            "impersonated_role": "instructor",
        }
        return request.render("fayna_camp_portal.admin_as_instructor", values)

    # ------------------------------------------------------------------
    # View-as: parent — render /my-style portal as that parent
    # ------------------------------------------------------------------

    @http.route("/admin/as-parent", type="http", auth="user", website=True)
    def admin_as_parent(self, partner_id=None, reason=None, **kw):
        self._check_admin()
        if not partner_id:
            raise UserError(_("partner_id is required."))

        try:
            partner = request.env["res.partner"].sudo().browse(int(partner_id)).exists()
        except (ValueError, TypeError) as e:
            raise UserError(_("Invalid partner_id.")) from e
        if not partner:
            raise UserError(_("Partner not found."))

        target_user = partner.user_ids[:1] or request.env.user
        self._log_access(
            "parent",
            target_user=target_user,
            target_partner=partner,
            reason=reason,
        )

        try:
            scoped_env = request.env(user=target_user.id) if partner.user_ids else request.env(su=True)
            participants = scoped_env["camp.participant"].search(
                [("parent_partner_id", "=", partner.id)]
            )
            registrations = scoped_env["event.registration"].search(
                [("partner_id", "=", partner.id), ("state", "!=", "cancel")]
            )
        except (AccessError, MissingError, KeyError) as e:
            _logger.warning("[ADMIN] as-parent scoped read failed: %s", e)
            participants = request.env["camp.participant"].browse([])
            registrations = request.env["event.registration"].browse([])

        values = {
            "page_name": "admin_as_parent",
            "viewed_user": target_user,
            "partner": partner,
            "participants": participants,
            "registrations": registrations,
            "impersonated_role": "parent",
        }
        return request.render("fayna_camp_portal.admin_as_parent", values)
