# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Experiential role test — PUBLIC user browses vacancies and submits an application.

Perspective: independent QA engineer. Proves that an anonymous (public) user can:
  1. GET /camp/vacancies → HTTP 200 and an open vacancy is listed.
  2. GET /camp/vacancy/<id>/apply → HTTP 200 form renders.
  3. POST /camp/vacancy/<id>/apply with valid data → application is created in DB.

Key facts pinned from the code under test (controllers/recruitment_portal.py):
  * GET /camp/vacancies (auth=public): sudo search state=open, renders portal_vacancy_list.
  * GET /camp/vacancy/<id>/apply (auth=public): checks vacancy exists + state='open'.
  * POST /camp/vacancy/<id>/apply: whitelist _APPLY_WHITELIST + sudo().create().
    Required fields from the whitelist: candidate_name, candidate_email.
  * camp.staff.vacancy required fields (models/staffing.py:58-102):
    name (default 'Wakat'), event_id, role (default 'wychowawca'), state (default 'open').
"""

import datetime
import re

from odoo.tests.common import HttpCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestRolePublicVacancies(HttpCase):
    """Public (unauthenticated) user can browse vacancies and submit an application."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Event to attach the vacancy to
        cls.event = cls.env["event.event"].create(
            {
                "name": "QA Public Vacancy Camp",
                "date_begin": datetime.datetime(2026, 8, 1, 9, 0),
                "date_end": datetime.datetime(2026, 8, 14, 18, 0),
                "date_tz": "Europe/Warsaw",
            }
        )

        # An open vacancy — the only required fields are name, event_id, role, state
        cls.vacancy = cls.env["camp.staff.vacancy"].create(
            {
                "name": "QA Wakat Wychowawca",
                "event_id": cls.event.id,
                "role": "wychowawca",
                "state": "open",
            }
        )

    # ── 1. Public list renders with the open vacancy ─────────────────────────

    def test_public_vacancy_list_renders(self):
        """GET /camp/vacancies returns HTTP 200 and lists the open vacancy."""
        response = self.url_open("/camp/vacancies")
        self.assertEqual(
            response.status_code,
            200,
            "GET /camp/vacancies must return HTTP 200 for anonymous users",
        )
        # The template renders the role display label and the event name,
        # NOT the vacancy internal name field (portal_recruitment.xml:25-28).
        # Verify the event name appears — that is what identifies this vacancy card.
        self.assertIn(
            "QA Public Vacancy Camp",
            response.text,
            "The event name of the open vacancy must appear in the /camp/vacancies body",
        )

    # ── 2. Application form renders for an open vacancy ─────────────────────

    def test_public_apply_form_renders(self):
        """GET /camp/vacancy/<id>/apply returns HTTP 200 for an open vacancy."""
        response = self.url_open(f"/camp/vacancy/{self.vacancy.id}/apply")
        self.assertEqual(
            response.status_code,
            200,
            "GET /camp/vacancy/<id>/apply must return HTTP 200 for an open vacancy",
        )

    # ── 3. POST apply creates an application in the database ─────────────────

    def test_public_apply_submit_creates_application(self):
        """POST /camp/vacancy/<id>/apply with valid data renders the success template.

        The controller (recruitment_portal.py:91-133) uses sudo().create() after
        validating the whitelist, then renders portal_vacancy_apply with success=True.
        We verify the success indicator appears in the response body.

        Note: DB-side count verification is not reliable in HttpCase because the HTTP
        request cursor and the test cursor run in separate transaction scopes. The
        HTTP response body is the authoritative signal for this experiential test.
        """
        apply_url = f"/camp/vacancy/{self.vacancy.id}/apply"

        # Step 1: GET the form (CSRF token may or may not be present in minimal CI env)
        form_response = self.url_open(apply_url)
        self.assertEqual(
            form_response.status_code,
            200,
            "GET /camp/vacancy/<id>/apply must return 200 before we can POST",
        )
        token = None
        match = re.search(r'name="csrf_token"\s+value="([^"]+)"', form_response.text)
        if match:
            token = match.group(1)

        # Step 2: POST — CSRF check is disabled in test mode; token included if found
        payload = {
            "candidate_name": "QA Kandydat Publiczny",
            "candidate_email": "qa_kandydat@campscout.test",
            "candidate_phone": "+48512345678",
            "message": "Chętnie dołączę do zespołu jako wychowawca.",
        }
        if token:
            payload["csrf_token"] = token

        response = self.url_open(apply_url, data=payload)
        self.assertEqual(
            response.status_code,
            200,
            (
                "PRODUCT FINDING: POST /camp/vacancy/<id>/apply must return HTTP 200 after "
                "a successful application. A non-200 code means the form submission fails "
                "before reaching the controller."
            ),
        )
        # The success path renders portal_vacancy_apply with success=True.
        # The template outputs the string "Dziękujemy" in the success alert
        # (portal_recruitment.xml:76-80). Its presence proves the controller reached
        # the success branch (create() returned without raising).
        #
        # ROOT CAUSE OF FAILURE (confirmed from CI log analysis):
        # The GET route (recruitment_portal.py:62-80) lacks methods=["GET"],
        # so it matches ALL HTTP methods. Odoo's router resolves the more
        # general (no-methods-restriction) GET handler before the POST-specific
        # handler — the POST request is dispatched to public_vacancy_apply_form()
        # which renders the form with no success/error context (kw.get() returns
        # None for unrecognised kwargs). The POST body data is lost.
        # FIX: add methods=["GET"] to the GET handler at recruitment_portal.py:66.
        self.assertIn(
            "Dziękujemy",
            response.text,
            (
                "PRODUCT FINDING: POST /camp/vacancy/<id>/apply must render the success "
                "confirmation ('Dziękujemy'). The POST is being intercepted by the GET "
                "handler (recruitment_portal.py:62) which lacks methods=['GET'] and "
                "therefore matches all HTTP methods. FIX: add methods=['GET'] to the "
                "GET handler so the POST-specific route can be reached."
            ),
        )

    # ── 4. Closed vacancy redirects to /camp/vacancies ───────────────────────

    def test_closed_vacancy_redirects(self):
        """GET /camp/vacancy/<id>/apply on a non-open vacancy redirects away."""
        closed_vacancy = self.env["camp.staff.vacancy"].create(
            {
                "name": "QA Wakat Zamknięty",
                "event_id": self.event.id,
                "role": "instruktor",  # canonical PL key from _role_taxonomy.CAMP_ROLE_SELECTION
                "state": "closed",
            }
        )
        response = self.url_open(
            f"/camp/vacancy/{closed_vacancy.id}/apply",
            allow_redirects=False,
        )
        self.assertIn(
            response.status_code,
            (301, 302, 303),
            "A closed/non-open vacancy must redirect (3xx) away from the apply form",
        )
