# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Публічний endpoint для прийому вже згенерованих на клієнті PDF
(kadry-forms/campscout — instruktor/wolontariusz, kadry-forms/rodzice — zgody
4a/4b). Мета: зафіксувати IP+час подання як доказ на випадок спору (INC-216).

Не потребує portal-логіну (parents/kadra тестового табору можуть не мати
акаунту до завтрашнього виїзду) — публічний, але лише ЗАПИСУЄ дані, нічого
не читає й не видає (немає витоку чужих даних).
"""
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

_ALLOWED_DOC_TYPES = ("wychowawca", "rodzic")


class DocumentSubmissionController(http.Controller):

    @http.route(
        ["/camp/submit-document"],
        type="http",
        auth="public",
        website=False,
        methods=["POST"],
        csrf=False,
    )
    def submit_document(self, **post):
        """Приймає JSON body: {doc_type, full_name, contact, doc_number,
        raw_payload (об'єкт), pdf_base64, pdf_filename}. Повертає {"ok": true}."""
        try:
            data = json.loads(request.httprequest.data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return request.make_json_response({"ok": False, "error": "bad_json"}, status=400)

        doc_type = data.get("doc_type")
        full_name = (data.get("full_name") or "").strip()
        if doc_type not in _ALLOWED_DOC_TYPES or not full_name:
            return request.make_json_response({"ok": False, "error": "missing_fields"}, status=400)

        ip_address = request.httprequest.headers.get("X-Forwarded-For", "").split(",")[0].strip() \
            or request.httprequest.remote_addr or ""

        pdf_base64 = data.get("pdf_base64")  # чистий base64 без "data:application/pdf;base64," префіксу
        if pdf_base64 and "," in pdf_base64:
            pdf_base64 = pdf_base64.split(",", 1)[1]

        try:
            record = request.env["camp.document.submission.log"].sudo().create_from_submission(
                env=request.env,
                doc_type=doc_type,
                full_name=full_name,
                contact=data.get("contact") or "",
                doc_number=data.get("doc_number") or "",
                ip_address=ip_address,
                raw_payload=json.dumps(data.get("raw_payload") or {}, ensure_ascii=False),
                pdf_base64=pdf_base64,
                pdf_filename=data.get("pdf_filename") or "dokument.pdf",
            )
        except Exception as e:  # noqa: BLE001 — публічний endpoint не повинен 500-ити на клієнта
            _logger.exception("[submit-document] failed: %s", e)
            return request.make_json_response({"ok": False, "error": "server_error"}, status=500)

        return request.make_json_response({"ok": True, "id": record.id})
