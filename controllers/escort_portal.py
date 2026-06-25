# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Кабінет батьків: Indywidualna asysta / konwój (camp.escort).

auth=user (на відміну від старого public bs-флоу). Доступ обмежує record-rule
`rule_portal_escort_own_children` + явна перевірка власності у кожному route.
Підпис — canvas signature pad → base64 PNG → action_sign() (патерн порталу).
TZ §5.5. Дизайн ухвалено панеллю + СТО 2026-06-23.
"""

import logging

from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class EscortPortal(CustomerPortal):
    """Розширює батьківський портал кабінетом супроводу."""

    def _get_own_escort(self, escort_id):
        """Повертає escort лише якщо він належить дитині поточного батька.

        Без sudo: покладаємось на record-rule; явна перевірка partner —
        друга лінія (consensus: standard access, no sudo для escort).
        """
        escort = request.env["camp.escort"].browse(int(escort_id))
        if not escort.exists():
            raise MissingError("Escort not found")
        partner = request.env.user.partner_id
        if escort.participant_id.parent_partner_id != partner:
            raise AccessError("Not your child's escort")
        return escort

    # ── Лічильник у /my (стиль documents_count) ──────────────────────────
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "escort_count" in counters:
            partner = request.env.user.partner_id
            values["escort_count"] = request.env["camp.escort"].search_count(
                [("participant_id.parent_partner_id", "=", partner.id)]
            )
        return values

    # ── Список ───────────────────────────────────────────────────────────
    @http.route(["/my/escort"], type="http", auth="user", website=True)
    def portal_my_escort(self, **kw):
        partner = request.env.user.partner_id
        escorts = request.env["camp.escort"].search(
            [("participant_id.parent_partner_id", "=", partner.id)],
            order="departure_datetime, id",
        )
        return request.render(
            "fayna_camp_portal.portal_escort_list",
            {"escorts": escorts, "page_name": "escort"},
        )

    # ── Картка + форма збору ─────────────────────────────────────────────
    @http.route(["/my/escort/<int:escort_id>"], type="http", auth="user", website=True)
    def portal_my_escort_detail(self, escort_id, **kw):
        try:
            escort = self._get_own_escort(escort_id)
        except (AccessError, MissingError):
            return request.redirect("/my/escort")
        return request.render(
            "fayna_camp_portal.portal_escort_form",
            {"escort": escort, "page_name": "escort"},
        )

    # ── Збереження полів супроводу ───────────────────────────────────────
    @http.route(
        ["/my/escort/<int:escort_id>/submit"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
    )
    def portal_my_escort_submit(self, escort_id, **post):
        try:
            escort = self._get_own_escort(escort_id)
        except (AccessError, MissingError):
            return request.redirect("/my/escort")
        vals = {
            k: post.get(k)
            for k in (
                "home_city",
                "pkp_station",
                "direction",
                "transport_mode",
                "escort_person_name",
                "escort_person_phone",
                "escort_person_doc",
            )
            if post.get(k)
        }
        vals["medical_help_consent"] = bool(post.get("medical_help_consent"))
        try:
            # sudo після ownership-check (_get_own_escort): portal ACL read-only
            escort.sudo().write(vals)
            escort.sudo().action_collect()
        except (UserError, ValidationError) as e:
            return request.render(
                "fayna_camp_portal.portal_escort_form",
                {"escort": escort, "page_name": "escort", "error": str(e)},
            )
        return request.redirect(f"/my/escort/{escort.id}")

    # ── Підпис (canvas → base64 PNG) ─────────────────────────────────────
    @http.route(["/my/escort/<int:escort_id>/sign"], type="json", auth="user", website=True)
    def portal_my_escort_sign(self, escort_id, signature=None, **kw):
        try:
            escort = self._get_own_escort(escort_id)
        except (AccessError, MissingError):
            return {"error": "access"}
        if not signature:
            return {"error": "no_signature"}
        # canvas dataURL: "data:image/png;base64,XXXX" → лишаємо raw base64
        if "," in signature:
            signature = signature.split(",", 1)[1]
        try:
            # sudo після ownership-check; signed_by_id=справжній батько (юр-доказ)
            escort.sudo().action_sign(
                ip_address=request.httprequest.remote_addr,
                signature=signature,
                signed_by_id=request.env.user.id,
            )
        except (UserError, ValidationError) as e:
            return {"error": str(e)}
        return {"success": True}
