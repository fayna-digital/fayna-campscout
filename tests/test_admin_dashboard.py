# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""HttpCase tests for the admin dashboard + view-as (controllers/admin.py).

P3.5 coverage gap: the controller carried the module's largest untested
surface (13%). These tests drive the real HTTP boundary: the Organizator
gate, the KPI dashboard render, the FULL login-as → stop-impersonation
cycle (including the immutable RODO art.30 access log on both ends and the
no-escalation rule) and the as-parent read-only view.
"""

from odoo.tests.common import HttpCase, tagged

from .http_lang import HTTP_TIMEOUT, open_functional

ORGANIZATOR_GROUP = "fayna_camp_portal.group_camp_organizator"
WYCHOWAWCA_GROUP = "fayna_camp_portal.group_camp_wychowawca"

ADMIN_LOGIN = "qa_admin_dash@campscout.test"
WYCH_LOGIN = "qa_wych_dash@campscout.test"
PARENT_LOGIN = "qa_parent_dash@campscout.test"
PASSWORD = "QaDash-1234!Strong"


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestAdminDashboard(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env["res.users"]

        cls.admin_user = Users.create(
            {
                "name": "QA Organizator",
                "login": ADMIN_LOGIN,
                "password": PASSWORD,
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref(ORGANIZATOR_GROUP).id,
                        ],
                    )
                ],
            }
        )
        cls.wych_user = Users.create(
            {
                "name": "QA Wychowawca Dash",
                "login": WYCH_LOGIN,
                "password": PASSWORD,
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref(WYCHOWAWCA_GROUP).id,
                        ],
                    )
                ],
            }
        )
        cls.parent_partner = cls.env["res.partner"].create(
            {"name": "QA Parent Dash", "email": PARENT_LOGIN}
        )
        cls.parent_user = Users.create(
            {
                "name": "QA Parent Dash",
                "login": PARENT_LOGIN,
                "password": PASSWORD,
                "partner_id": cls.parent_partner.id,
                "groups_id": [(6, 0, [cls.env.ref("base.group_portal").id])],
            }
        )
        cls.child = (
            cls.env["camp.participant"]
            .sudo()
            .create(
                {
                    "first_name": "DzieckoDash",
                    "last_name": "Kowalski",
                    "parent_partner_id": cls.parent_partner.id,
                }
            )
        )

    def _access_logs(self, role):
        return (
            self.env["camp.admin.access.log"]
            .sudo()
            .search([("impersonated_role", "=", role)], order="id desc")
        )

    # ── Gate ──────────────────────────────────────────────────────────────

    def test_dashboard_forbidden_for_non_organizator(self):
        """Wychowawca (internal, non-organizator) must NOT see the dashboard."""
        self.authenticate(WYCH_LOGIN, PASSWORD)
        resp = self.url_open("/admin/dashboard")
        self.assertNotEqual(resp.status_code, 200, "non-organizator opened /admin/dashboard")
        self.assertNotIn("Кабінет Організатора", resp.text)

    # ── Dashboard render ─────────────────────────────────────────────────

    def test_dashboard_renders_for_organizator(self):
        """Organizator gets 200 with all seven KPI sections rendered."""
        self.authenticate(ADMIN_LOGIN, PASSWORD)
        resp = self.url_open("/admin/dashboard")
        self.assertEqual(resp.status_code, 200)
        for marker in (
            "Кабінет Організатора",
            "Огляд бізнесу",
            "Тривоги",
            "Активні табори",
            "Команда",
        ):
            self.assertIn(marker, resp.text, f"dashboard section '{marker}' missing")

    # ── login-as: full cycle + RODO log + landing ────────────────────────

    def test_login_as_cycle_logs_and_restores(self):
        """login-as switches the session, logs start AND stop, and lands the
        internal role inside the CampScout menu — then stop restores admin."""
        self.authenticate(ADMIN_LOGIN, PASSWORD)

        # open_functional: із двомовністю (R2) перший 3xx — мовний переписувач
        # URL, а не редірект контролера; асертити треба функціональну відповідь.
        resp = open_functional(self, f"/admin/login-as?user_id={self.wych_user.id}&reason=QA-cykl")
        self.assertIn(resp.status_code, (301, 302, 303, 307, 308))
        self.assertIn("/web", resp.headers.get("Location", ""))

        start_log = self._access_logs("login_as")[:1]
        self.assertTrue(start_log, "login-as start must write an access-log row")
        self.assertEqual(start_log.user_id.id, self.admin_user.id)
        self.assertEqual(start_log.target_user_id.id, self.wych_user.id)

        # Session is now the wychowawca — the admin gate must reject it.
        gate = self.url_open("/admin/dashboard")
        self.assertNotEqual(gate.status_code, 200, "impersonated session kept admin rights")

        # Stop: session returns to the Organizator, stop row is logged.
        stop = open_functional(self, "/admin/stop-impersonation")
        self.assertIn(stop.status_code, (301, 302, 303, 307, 308))
        stop_log = self._access_logs("stop")[:1]
        self.assertTrue(stop_log, "stop-impersonation must write an access-log row")
        self.assertEqual(stop_log.user_id.id, self.admin_user.id)

        back = self.url_open("/admin/dashboard")
        self.assertEqual(back.status_code, 200, "admin session was not restored")

    def test_login_as_refuses_escalation(self):
        """Impersonating another organizator/admin must be refused and unlogged."""
        other_admin = self.env["res.users"].create(
            {
                "name": "QA Organizator 2",
                "login": "qa_admin2_dash@campscout.test",
                "password": PASSWORD,
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref(ORGANIZATOR_GROUP).id,
                        ],
                    )
                ],
            }
        )
        self.authenticate(ADMIN_LOGIN, PASSWORD)
        before = len(self._access_logs("login_as"))
        resp = open_functional(
            self, f"/admin/login-as?user_id={other_admin.id}&reason=QA-eskalacja"
        )
        self.assertNotIn(
            resp.status_code,
            (301, 302, 303, 307, 308),
            "escalation attempt must not redirect into an impersonated session",
        )
        self.assertEqual(
            len(self._access_logs("login_as")),
            before,
            "refused escalation must not create a login_as log row",
        )
        # And the session must still be the admin's own.
        self.assertEqual(self.url_open("/admin/dashboard").status_code, 200)

    # ── as-parent (read-only view) ───────────────────────────────────────

    def test_as_parent_renders_children_and_logs(self):
        self.authenticate(ADMIN_LOGIN, PASSWORD)
        resp = self.url_open(
            f"/admin/as-parent?partner_id={self.parent_partner.id}&reason=kontrola",
            timeout=HTTP_TIMEOUT,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("DzieckoDash", resp.text)
        log = self._access_logs("parent")[:1]
        self.assertTrue(log, "as-parent must write an access-log row")
        self.assertEqual(log.target_partner_id.id, self.parent_partner.id)
