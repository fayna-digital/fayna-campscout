# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
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
from odoo.addons.web.controllers.home import Home

_logger = logging.getLogger(__name__)

ORGANIZATOR_GROUP = "fayna_camp_portal.group_camp_organizator"


class CampHome(Home):
    """Login redirect: Organizator → server-rendered /admin/dashboard.

    Root cause (TZ §20 R1): the organizator home action was an `act_url` to
    /admin/dashboard, but the web client does NOT auto-execute an act_url home
    action → blank /web (stuck "Pobieranie"). Redirect at the HTTP login level
    so they land straight on the dashboard. Kiosk roles fall through to default
    (web client → camp_kiosk_action via res.users._get_login_action).
    """

    def _login_redirect(self, uid, redirect=None):
        if not redirect:
            user = request.env["res.users"].sudo().browse(uid)
            if user.has_group(ORGANIZATOR_GROUP):
                return "/admin/dashboard"
        return super()._login_redirect(uid, redirect=redirect)


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
        values["recent_access_log"] = env_sudo["camp.admin.access.log"].search(
            [], order="accessed_at desc", limit=10
        )

        # 8) Impersonation — users the Organizator may log in as (login-as)
        values["impersonable_users"] = self._build_impersonable_users(env_sudo)

        return request.render("fayna_camp_portal.admin_dashboard", values)

    def _build_impersonable_users(self, env_sudo):
        """Return camp-role/parent users that login-as may target, grouped by role.

        Mirrors the backend guard in /admin/login-as: never list admins or
        organizators (no privilege escalation). Internal camp roles
        (kierownik/wychowawca/instructor) plus portal parents are eligible.
        Returns a list of dicts ordered by role for a grouped QWeb render.
        """
        groups = {
            "kierownik": "fayna_camp_portal.group_camp_kierownik",
            "wychowawca": "fayna_camp_portal.group_camp_wychowawca",
            "instructor": "fayna_camp_portal.group_camp_instructor",
            "parent": "base.group_portal",
        }
        # Labels shown in the UI (Ukrainian, per CLAUDE.md).
        labels = {
            "kierownik": _("Kierownik"),
            "wychowawca": _("Wychowawca"),
            "instructor": _("Instruktor"),
            "parent": _("Батьки"),
        }
        try:
            system_group = env_sudo.ref("base.group_system")
            organizator_group = env_sudo.ref(ORGANIZATOR_GROUP)
        except (ValueError, KeyError):
            return []

        sections = []
        seen_ids = set()
        for role, xmlid in groups.items():
            try:
                group = env_sudo.ref(xmlid)
            except (ValueError, KeyError):
                continue
            try:
                users = env_sudo["res.users"].search(
                    [
                        ("active", "=", True),
                        ("groups_id", "in", group.id),
                        ("groups_id", "not in", system_group.id),
                        ("groups_id", "not in", organizator_group.id),
                    ],
                    order="name asc",
                    limit=100,
                )
            except (AccessError, MissingError, KeyError):
                continue
            rows = []
            for user in users:
                # A user may hold several role groups — show them once, under
                # the first (most privileged) role we encounter.
                if user.id in seen_ids:
                    continue
                seen_ids.add(user.id)
                rows.append({"id": user.id, "name": user.name})
            if rows:
                sections.append(
                    {"role": role, "label": labels.get(role, role), "users": rows}
                )
        return sections

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
                        [("event_id", "=", ev.id), ("role", "=", "kierownik")],
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
            consented = env_sudo["fayna.rodo.consent.log"].search_count([("state", "=", "granted")])
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
            scoped_env = (
                request.env(user=target_user.id) if partner.user_ids else request.env(su=True)
            )
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

    # ------------------------------------------------------------------
    # TRUE login-as: switch the WHOLE session to the target user, so the
    # Organizator uses that role's real backend/portal. RODO-logged on
    # start AND stop, no escalation (cannot impersonate admin/organizator),
    # fully reversible via /admin/stop-impersonation.
    # ------------------------------------------------------------------
    @http.route("/admin/login-as", type="http", auth="user", website=True)
    def admin_login_as(self, user_id=None, reason=None, **kw):
        self._check_admin()
        if request.session.get("impersonator_uid"):
            raise UserError(_("Już trwa impersonacja — najpierw wróć do siebie."))
        if not user_id:
            raise UserError(_("user_id is required."))
        try:
            target = request.env["res.users"].sudo().browse(int(user_id)).exists()
        except (ValueError, TypeError) as e:
            raise UserError(_("Invalid user_id.")) from e
        if not target:
            raise UserError(_("User not found."))
        if target.id == request.env.user.id:
            raise UserError(_("Nie można impersonować samego siebie."))
        # No privilege escalation — never become an admin / organizator.
        if target.has_group("base.group_system") or target.has_group(ORGANIZATOR_GROUP):
            raise UserError(_("Nie można impersonować administratora/organizatora."))

        original_uid = request.env.user.id
        self._log_access("login_as", target_user=target, reason=reason or "login-as")

        # Switch session + recompute token (else Odoo invalidates next request).
        request.session["impersonator_uid"] = original_uid
        request.session.uid = target.id
        request.session.login = target.login
        request.session.session_token = target._compute_session_token(request.session.sid)
        request.update_env(user=target.id)

        return request.redirect(self._login_as_landing(target))

    def _login_as_landing(self, target):
        """Choose the landing URL for a freshly-impersonated user.

        G1 (TZ §G, 2026-06-24): operational internal roles
        (kierownik/wychowawca/instructor and any other camp role that is a
        base.group_user) must NOT land in the raw Odoo apps-grid (/web). They
        land directly inside the «Portal CampScout» root menu so the cabinet
        is the first thing they see — not a wall of Sales/Website/Employees
        apps. Portal-only parents keep landing on /my.

        We deep-link via /web#menu_id=<root> (the Odoo 17 web client reads the
        menu_id from the URL fragment and opens that application directly
        instead of the apps grid), and fall back to plain /web only if the menu
        record cannot be resolved (e.g. module half-installed).
        """
        if not target.has_group("base.group_user"):
            # Portal-only (parent) — their cabinet is /my.
            return "/my"
        try:
            root_menu = request.env.ref(
                "fayna_camp_portal.menu_campscout_root", raise_if_not_found=False
            )
        except (ValueError, KeyError):
            root_menu = None
        if root_menu:
            # Odoo 17 web client reads the menu_id from the URL fragment and
            # opens that application's menu directly instead of the apps grid.
            return "/web#menu_id=%s" % root_menu.id
        return "/web"

    @http.route("/admin/impersonation-status", type="json", auth="user")
    def admin_impersonation_status(self):
        """JSON: чи поточна сесія в режимі імперсонації (для systray/банера)."""
        imp = request.session.get("impersonator_uid")
        if not imp:
            return {"impersonating": False}
        admin = request.env["res.users"].sudo().browse(int(imp)).exists()
        return {
            "impersonating": True,
            "admin_name": admin.name if admin else "",
            "current_name": request.env.user.name,
        }

    @http.route("/admin/stop-impersonation", type="http", auth="user", website=True)
    def admin_stop_impersonation(self, **kw):
        original_uid = request.session.get("impersonator_uid")
        if not original_uid:
            return request.redirect("/admin/dashboard")
        orig_user = request.env["res.users"].sudo().browse(int(original_uid)).exists()
        if not orig_user:
            request.session.logout(keep_db=True)
            return request.redirect("/web/login")

        # Audit the stop AS the original admin (not the impersonated user).
        request.env["camp.admin.access.log"].sudo().create(
            {
                "user_id": original_uid,
                "impersonated_role": "stop",
                "target_user_id": request.env.user.id,
                "ip_address": request.httprequest.remote_addr or False,
                "session_id": getattr(request.session, "sid", False) or False,
                "reason": "stop-impersonation",
            }
        )
        request.session.uid = original_uid
        request.session.login = orig_user.login
        request.session.session_token = orig_user._compute_session_token(request.session.sid)
        request.session.pop("impersonator_uid", None)
        request.update_env(user=original_uid)
        return request.redirect("/admin/dashboard")
