# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Публічний endpoint для прийому вже згенерованих на клієнті PDF
(kadry-forms/campscout — instruktor/wolontariusz, kadry-forms/rodzice — zgody
4a/4b). Мета: зафіксувати IP+час подання як доказ на випадок спору (INC-216).

Не потребує portal-логіну (parents/kadra тестового табору можуть не мати
акаунту до завтрашнього виїзду) — публічний, але лише ЗАПИСУЄ дані, нічого
не читає й не видає (немає витоку чужих даних).

Зберігає через ir.attachment (не через camp.document.submission.log) — той
модуль ще чекає -u на staging (INC-216 продовження: CLI/UI upgrade зламані
в цьому середовищі), а ir.attachment вже встановлений і доступний без
міграції. Коли -u стане можливим, це можна перенести на власну модель.
"""
import json
import logging

import requests

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

_ALLOWED_DOC_TYPES = ("wychowawca", "rodzic")

_TELEGRAM_SECRETS_FILE = "/etc/odoo/telegram_secrets.env"
_TELEGRAM_CHAT_ID = 1216572335  # @FaynaBrain_bot, той самий чат, що й inbox-agent


def _read_telegram_token():
    try:
        with open(_TELEGRAM_SECRETS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    return line.strip().split("=", 1)[1]
    except OSError:
        pass
    return None


def _notify_telegram(text):
    """Best-effort — збій сповіщення НЕ повинен зривати збереження доказу."""
    token = _read_telegram_token()
    if not token:
        _logger.warning("[submit-document] telegram token не знайдено — сповіщення пропущено")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": _TELEGRAM_CHAT_ID, "text": text},
            timeout=5,
        )
    except Exception as e:  # noqa: BLE001
        _logger.warning("[submit-document] telegram notify failed: %s", e)


class DocumentSubmissionController(http.Controller):

    @http.route(
        ["/camp/submit-document"],
        type="http",
        auth="public",
        website=False,
        methods=["POST", "OPTIONS"],
        csrf=False,
        cors="*",
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

        evidence = {
            "doc_type": doc_type,
            "full_name": full_name,
            "contact": data.get("contact") or "",
            "doc_number": data.get("doc_number") or "",
            "ip_address": ip_address,
            "submitted_at": str(fields.Datetime.now()),
            "raw_payload": data.get("raw_payload") or {},
        }
        pdf_filename = data.get("pdf_filename") or "dokument.pdf"

        try:
            attachment = request.env["ir.attachment"].sudo().create({
                "name": f"[SUBMIT-LOG] {doc_type} — {full_name} — {evidence['doc_number']} — {pdf_filename}",
                "datas": pdf_base64,
                "mimetype": "application/pdf",
                "description": json.dumps(evidence, ensure_ascii=False, indent=2),
            })
        except Exception as e:  # noqa: BLE001 — публічний endpoint не повинен 500-ити на клієнта
            _logger.exception("[submit-document] failed: %s", e)
            return request.make_json_response({"ok": False, "error": "server_error"}, status=500)

        _notify_telegram(self._telegram_text(doc_type, full_name, evidence))
        return request.make_json_response({"ok": True, "id": attachment.id})

    @staticmethod
    def _telegram_text(doc_type, full_name, evidence):
        payload = evidence["raw_payload"] or {}
        lines = [f"📄 Нова заявка ({'кадра' if doc_type == 'wychowawca' else 'згода батьків'})"]
        if doc_type == "rodzic":
            lines.append(f"Дитина: {payload.get('dziecko') or '—'}")
            lines.append(f"Батько/опікун: {full_name}")
            lines.append(f"Wizerunek: {payload.get('wizerunek') or '—'}")
            lines.append(f"Marketing: {'TAK' if payload.get('marketing') else 'NIE'}")
        else:
            lines.append(f"ПІБ: {full_name}")
        lines.append(f"Контакт: {evidence['contact'] or '—'}")
        lines.append(f"Номер: {evidence['doc_number'] or '—'}")
        lines.append(f"IP: {evidence['ip_address'] or '—'}")
        lines.append(f"Час: {evidence['submitted_at']}")
        return "\n".join(lines)
