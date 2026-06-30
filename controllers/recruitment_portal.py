# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Публічний портал рекрутації — /camp/vacancies + /camp/vacancy/<id>/apply.

Кандидат без акаунту заповнює форму → camp.staff.application.sudo().create().
Після accept() organizator-ом → кандидат отримує portal invite (action_reset_password).

Маршрут /my/candidate (auth=user) — кандидат із вже створеним portal-user переглядає
свій стан та завантажує документи (CV / фото).

Патерн: escort_portal.py — ownership check + sudo після validation.
Захист: csrf (вбудований website=True) + whitelist полів + sudo лише після перевірки.
"""

import logging

from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)

_APPLY_WHITELIST = ("candidate_name", "candidate_email", "candidate_phone", "message")
_ONBOARD_WHITELIST = ("cv_attachment", "photo")


class RecruitmentPortal(CustomerPortal):
    """Публічний портал рекрутації + кабінет кандидата."""

    # ── Лічильник у /my ──────────────────────────────────────────────────────
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "candidate_application_count" in counters:
            partner = request.env.user.partner_id
            values["candidate_application_count"] = (
                request.env["camp.staff.application"]
                .sudo()
                .search_count([("partner_id", "=", partner.id)])
            )
        return values

    # ── GET /camp/vacancies — публічний список відкритих вакансій ────────────
    @http.route(
        ["/camp/vacancies"],
        type="http",
        auth="public",
        website=True,
    )
    def public_vacancy_list(self, **kw):
        vacancies = (
            request.env["camp.staff.vacancy"]
            .sudo()
            .search([("state", "=", "open")], order="event_id, role, id")
        )
        return request.render(
            "fayna_camp_portal.portal_vacancy_list",
            {"vacancies": vacancies, "page_name": "vacancies"},
        )

    # ── GET /camp/vacancy/<id>/apply — форма заявки ──────────────────────────
    @http.route(
        ["/camp/vacancy/<int:vacancy_id>/apply"],
        type="http",
        auth="public",
        website=True,
    )
    def public_vacancy_apply_form(self, vacancy_id, **kw):
        vacancy = request.env["camp.staff.vacancy"].sudo().browse(vacancy_id)
        if not vacancy.exists() or vacancy.state != "open":
            return request.redirect("/camp/vacancies")
        return request.render(
            "fayna_camp_portal.portal_vacancy_apply",
            {
                "vacancy": vacancy,
                "page_name": "vacancies",
                "error": kw.get("error"),
                "success": kw.get("success"),
            },
        )

    # ── POST /camp/vacancy/<id>/apply — прийом заявки ────────────────────────
    @http.route(
        ["/camp/vacancy/<int:vacancy_id>/apply"],
        type="http",
        auth="public",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def public_vacancy_apply_submit(self, vacancy_id, **post):
        vacancy = request.env["camp.staff.vacancy"].sudo().browse(vacancy_id)
        if not vacancy.exists() or vacancy.state != "open":
            return request.redirect("/camp/vacancies")

        # Whitelist — ніяких зайвих полів
        vals = {k: (post.get(k) or "").strip() for k in _APPLY_WHITELIST if post.get(k)}

        # Мінімальна валідація
        if not vals.get("candidate_name") or not vals.get("candidate_email"):
            return request.render(
                "fayna_camp_portal.portal_vacancy_apply",
                {
                    "vacancy": vacancy,
                    "page_name": "vacancies",
                    "error": "Ім'я та e-mail обов'язкові.",
                    "form_data": vals,
                },
            )

        vals["vacancy_id"] = vacancy.id

        try:
            request.env["camp.staff.application"].sudo().create(vals)
        except (UserError, ValidationError) as e:
            return request.render(
                "fayna_camp_portal.portal_vacancy_apply",
                {
                    "vacancy": vacancy,
                    "page_name": "vacancies",
                    "error": str(e),
                    "form_data": vals,
                },
            )

        return request.render(
            "fayna_camp_portal.portal_vacancy_apply",
            {
                "vacancy": vacancy,
                "page_name": "vacancies",
                "success": True,
            },
        )

    # ── GET /my/candidate — кабінет кандидата (auth=user) ───────────────────
    @http.route(
        ["/my/candidate"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_candidate(self, **kw):
        partner = request.env.user.partner_id
        # Беремо останню заявку кандидата (може бути кілька вакансій)
        applications = (
            request.env["camp.staff.application"]
            .sudo()
            .search([("partner_id", "=", partner.id)], order="create_date desc")
        )
        staff_record = None
        if applications and applications[0].staff_id:
            staff_record = applications[0].staff_id.sudo()

        # §13 — blurred-children: виховник у стані pending_admission (ще НЕ
        # «Dopuść», KRK/RSPTS не zweryfikowane) бачить лише KILKOŚĆ dzieci
        # swoich grup + N rozmytych placeholderów. ŻADNE pole dziecka
        # (imię/PESEL/foto/art.9) nie trafia do odpowiedzi — czytamy WYŁĄCZNIE
        # camp.group.participant_count, NIGDY rekordów camp.participant.
        blurred_groups = self._candidate_blurred_groups(staff_record)

        return request.render(
            "fayna_camp_portal.portal_candidate_status",
            {
                "applications": applications,
                "staff": staff_record,
                "blurred_groups": blurred_groups,
                "page_name": "candidate",
                "error": kw.get("error"),
                "success": kw.get("success"),
            },
        )

    def _candidate_blurred_groups(self, staff_record):
        """§13 — dane grup viewer-a pending_admission w formie rozmytej.

        Zwraca listę dict {name, count} — TYLKO dla viewer-ów, którzy NIE są
        jeszcze dopuszczeni (staff.state != 'active'). Po «Dopuść» (active)
        zwraca [] — pełne karty pokazuje kiosk/backend przez record-rule
        `rule_participant_wychowawca_own`, tu nic nie dublujemy.

        Gwarancja prawna: odczytujemy wyłącznie `participant_count`
        (liczba żywa — rośnie przy nowych rezerwacjach) z grup, w których
        bieżący user figuruje jako wychowawca. NIE dotykamy modelu
        camp.participant, więc żadne pole osobowe/art.9 dziecka nie może
        trafić do odpowiedzi serwera.
        """
        if not staff_record or staff_record.state == "active":
            return []

        user = request.env.user
        # sudo: pending wychowawca nie ma jeszcze group_camp_wychowawca, więc
        # record-rule nie da mu czytać camp.group; scope domeną do JEGO grup.
        groups = (
            request.env["camp.group"]
            .sudo()
            .search(
                [("wychowawca_ids", "in", [user.id])],
                order="event_id, sequence, name, id",
            )
        )
        return [{"name": group.name, "count": group.participant_count} for group in groups]

    # ── POST /my/candidate/upload — завантаження CV/фото (auth=user) ─────────
    @http.route(
        ["/my/candidate/upload"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def portal_candidate_upload(self, **post):
        partner = request.env.user.partner_id

        # Знаходимо staff прив'язаний до цього кандидата
        applications = (
            request.env["camp.staff.application"]
            .sudo()
            .search(
                [("partner_id", "=", partner.id), ("state", "=", "accepted")],
                limit=1,
                order="create_date desc",
            )
        )
        if not applications or not applications.staff_id:
            return request.redirect("/my/candidate?error=no_staff")

        staff = applications.staff_id.sudo()

        # Ownership check: staff.user_id == current user
        if staff.user_id.id != request.env.user.id:
            raise AccessError("Not your staff record")

        vals = {}
        # CV upload
        cv_file = request.httprequest.files.get("cv_attachment")
        if cv_file and cv_file.filename:
            import base64

            vals["cv_attachment"] = base64.b64encode(cv_file.read())

        # Photo upload
        photo_file = request.httprequest.files.get("photo")
        if photo_file and photo_file.filename:
            import base64

            vals["photo"] = base64.b64encode(photo_file.read())

        # KRK upload — wyciąg z Krajowego Rejestru Karnego (§13)
        krk_file = request.httprequest.files.get("krk_attachment")
        if krk_file and krk_file.filename:
            import base64

            vals["krk_attachment"] = base64.b64encode(krk_file.read())

        if vals:
            try:
                staff.write(vals)
            except (UserError, ValidationError, AccessError) as e:
                return request.redirect(f"/my/candidate?error={str(e)[:80]}")

        return request.redirect("/my/candidate?success=1")

    # ── POST /my/candidate/declaration — підпис declaracji niekaralności ─────
    @http.route(
        ["/my/candidate/declaration"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def portal_candidate_declaration(self, **post):
        """Kandydat składa oświadczenie o niekaralności (§13 / §6m).

        Wymaga zaznaczenia zgody (accept=on). Utrwalamy moment + IP
        (niezaprzeczalność podpisu, §6k/§6o). NIE zastępuje weryfikacji
        KRK/RSPTS — admission gate sprawdza oba warunki niezależnie."""
        partner = request.env.user.partner_id
        applications = (
            request.env["camp.staff.application"]
            .sudo()
            .search(
                [("partner_id", "=", partner.id), ("state", "=", "accepted")],
                limit=1,
                order="create_date desc",
            )
        )
        if not applications or not applications.staff_id:
            return request.redirect("/my/candidate?error=no_staff")

        staff = applications.staff_id.sudo()
        if staff.user_id.id != request.env.user.id:
            raise AccessError("Not your staff record")

        if not post.get("accept"):
            return request.redirect("/my/candidate?error=Zaznacz zgodę, aby podpisać oświadczenie.")

        ip_address = request.httprequest.remote_addr or ""
        try:
            staff._sign_declaration(ip_address=ip_address)
        except (UserError, ValidationError, AccessError) as e:
            return request.redirect(f"/my/candidate?error={str(e)[:80]}")

        return request.redirect("/my/candidate?success=1")
