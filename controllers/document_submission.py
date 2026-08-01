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

import base64
import json
import logging
from html import escape

import requests
from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)

_ALLOWED_DOC_TYPES = ("wychowawca", "rodzic", "zwrot")

_ZWROT_EMAIL_TO = "admin@campscout.eu"

_TELEGRAM_SECRETS_FILE = "/etc/odoo/telegram_secrets.env"
_TELEGRAM_CHAT_ID = 1216572335  # @FaynaBrain_bot, той самий чат, що й inbox-agent


def _read_telegram_token():
    try:
        with open(_TELEGRAM_SECRETS_FILE, encoding="utf-8") as f:
            for line in f:
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    return line.strip().split("=", 1)[1]
    except OSError:
        pass
    return None


_SENSITIVE_HINTS = ("iban", "rachun", "pesel", "konto", "karta", "card")


def _mask_sensitive(key, value):
    """Чернетка — це слід спроби, а не сховище платіжних даних: номери рахунків
    і PESEL лишаються лише хвостом у 4 знаки, решта — зірочки."""
    if not isinstance(value, str):
        value = str(value or "")
    value = value.strip()[:300]
    if value and any(h in (key or "").lower() for h in _SENSITIVE_HINTS):
        digits = "".join(ch for ch in value if ch.isalnum())
        if len(digits) > 6:
            return "*" * (len(digits) - 4) + digits[-4:]
    return value


def _gc_drafts(env, days=60):
    """Чернетки не мають накопичуватись роками — прибираємо старші за `days`.
    Викликається зрідка з самого ендпоінта (окремий cron на staging не ставиться:
    upgrade модуля тут зламаний, INC-216)."""
    try:
        limit = fields.Datetime.subtract(fields.Datetime.now(), days=days)
        old = env["ir.attachment"].sudo().search(
            [("name", "=like", "[DRAFT-LOG] %"), ("create_date", "<", limit)], limit=500
        )
        if old:
            old.unlink()
    except Exception as e:  # noqa: BLE001
        _logger.warning("[submit-draft] gc failed: %s", e)


def _notify_telegram(text, pdf_base64=None, pdf_filename="dokument.pdf"):
    """Best-effort — збій сповіщення НЕ повинен зривати збереження доказу.
    Якщо є PDF — шле sendDocument (файл одразу в чаті, caption=text);
    інакше — звичайний sendMessage."""
    token = _read_telegram_token()
    if not token:
        _logger.warning("[submit-document] telegram token не знайдено — сповіщення пропущено")
        return
    try:
        if pdf_base64:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data={"chat_id": _TELEGRAM_CHAT_ID, "caption": text[:1024]},
                files={"document": (pdf_filename, base64.b64decode(pdf_base64), "application/pdf")},
                timeout=15,
            )
        else:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": _TELEGRAM_CHAT_ID, "text": text},
                timeout=5,
            )
    except Exception as e:  # noqa: BLE001
        _logger.warning("[submit-document] telegram notify failed: %s", e)


def _notify_email_zwrot(full_name, doc_number, body_text, attachment):
    """Best-effort доставка заповненого wniosek o zwrot на admin@campscout.eu.
    Збій пошти (нема вихідного mail-сервера тощо) НЕ повинен зривати збереження
    доказу й НЕ 500-ити клієнта — обгорнуто в try/except, як telegram."""
    try:
        body_html = (
            '<pre style="font-family:inherit;white-space:pre-wrap">' + escape(body_text) + "</pre>"
        )
        request.env["mail.mail"].sudo().create(
            {
                "subject": f"Wniosek o zwrot — {full_name} — {doc_number or '—'}",
                "email_to": _ZWROT_EMAIL_TO,
                "body_html": body_html,
                "attachment_ids": [(6, 0, [attachment.id])],
            }
        ).send()
    except Exception as e:  # noqa: BLE001
        _logger.warning("[submit-document] email notify (zwrot) failed: %s", e)


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

        ip_address = (
            request.httprequest.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.httprequest.remote_addr
            or ""
        )

        pdf_base64 = data.get(
            "pdf_base64"
        )  # чистий base64 без "data:application/pdf;base64," префіксу
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
            attachment = (
                request.env["ir.attachment"]
                .sudo()
                .create(
                    {
                        "name": f"[SUBMIT-LOG] {doc_type} — {full_name} — {evidence['doc_number']} — {pdf_filename}",
                        "datas": pdf_base64,
                        "mimetype": "application/pdf",
                        "description": json.dumps(evidence, ensure_ascii=False, indent=2),
                    }
                )
            )
        except Exception as e:  # noqa: BLE001 — публічний endpoint не повинен 500-ити на клієнта
            _logger.exception("[submit-document] failed: %s", e)
            return request.make_json_response({"ok": False, "error": "server_error"}, status=500)

        # Чернетку цієї ж сесії закриваємо на СЕРВЕРІ, а не покладаючись на
        # клієнта: інакше вдале подання лишиться в звіті «почав і не закінчив».
        sid = (data.get("sid") or "").strip()[:64]
        if sid:
            try:
                draft = (
                    request.env["ir.attachment"]
                    .sudo()
                    .search([("name", "=like", f"[DRAFT-LOG] {sid}%")], limit=1)
                )
                if draft:
                    prev = json.loads(draft.description or "{}")
                    prev.update({"stage": "submitted", "submitted_attachment_id": attachment.id,
                                 "last_seen": str(fields.Datetime.now())})
                    draft.write({"description": json.dumps(prev, ensure_ascii=False, indent=2)})
            except Exception as e:  # noqa: BLE001
                _logger.warning("[submit-document] draft close failed: %s", e)

        structured_text = self._telegram_text(doc_type, full_name, evidence)
        _notify_telegram(structured_text, pdf_base64, pdf_filename)
        if doc_type == "zwrot":
            _notify_email_zwrot(full_name, evidence["doc_number"], structured_text, attachment)
        return request.make_json_response({"ok": True, "id": attachment.id})

    @http.route(
        ["/camp/submit-draft"],
        type="http",
        auth="public",
        website=False,
        methods=["POST", "OPTIONS"],
        csrf=False,
        cors="*",
    )
    def submit_draft(self, **post):
        """Чернетка: фіксує СПРОБУ заповнення ще до генерації PDF.

        Потрібна тому, що PDF твориться цілком у браузері: між кліком і POST-ом
        готового документа минає 1–5 с, і якщо в цей момент сторінку закрито
        (iOS вивантажує вкладку при перемиканні застосунку / блокуванні екрана),
        на сервер не потрапляє НІЧОГО — організатор не знає навіть, що людина
        починала. Сюди ж шле `navigator.sendBeacon` на `pagehide`, який браузер
        доставляє вже після вивантаження сторінки.

        Один `sid` (сесія заповнення) = один запис, що оновлюється (upsert),
        інакше кожне натискання клавіші плодило б рядок.

        Мінімізація ПД: IBAN/PESEL маскуються, PDF не зберігається, чернетки
        старші за 60 днів прибирає `_gc_drafts`.
        """
        try:
            data = json.loads(request.httprequest.data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return request.make_json_response({"ok": False, "error": "bad_json"}, status=400)

        sid = (data.get("sid") or "").strip()[:64]
        doc_type = data.get("doc_type") or "unknown"
        if not sid or doc_type not in _ALLOWED_DOC_TYPES + ("unknown",):
            return request.make_json_response({"ok": False, "error": "missing_sid"}, status=400)

        fields_in = data.get("fields") or {}
        if not isinstance(fields_in, dict):
            fields_in = {}
        safe_fields = {k[:60]: _mask_sensitive(k, v) for k, v in list(fields_in.items())[:60]}

        ip_address = (
            request.httprequest.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.httprequest.remote_addr
            or ""
        )
        evidence = {
            "doc_type": doc_type,
            "sid": sid,
            "stage": (data.get("stage") or "typing")[:20],
            "form_url": (data.get("url") or "")[:200],
            "user_agent": request.httprequest.headers.get("User-Agent", "")[:250],
            "ip_address": ip_address,
            "first_seen": str(fields.Datetime.now()),
            "last_seen": str(fields.Datetime.now()),
            "filled_count": len([v for v in safe_fields.values() if v]),
            "fields": safe_fields,
        }

        Att = request.env["ir.attachment"].sudo()
        try:
            existing = Att.search([("name", "=like", f"[DRAFT-LOG] {sid}%")], limit=1)
            if existing:
                try:
                    prev = json.loads(existing.description or "{}")
                except ValueError:
                    prev = {}
                evidence["first_seen"] = prev.get("first_seen") or evidence["first_seen"]
                merged = dict(prev.get("fields") or {})
                merged.update({k: v for k, v in safe_fields.items() if v})
                evidence["fields"] = merged
                evidence["filled_count"] = len([v for v in merged.values() if v])
                existing.write({"description": json.dumps(evidence, ensure_ascii=False, indent=2)})
                att_id = existing.id
            else:
                att_id = Att.create(
                    {
                        "name": f"[DRAFT-LOG] {sid} — {doc_type}",
                        "mimetype": "text/plain",
                        "description": json.dumps(evidence, ensure_ascii=False, indent=2),
                    }
                ).id
        except Exception as e:  # noqa: BLE001 — чернетка ніколи не повинна ламати форму
            _logger.warning("[submit-draft] failed: %s", e)
            return request.make_json_response({"ok": False, "error": "server_error"}, status=200)

        return request.make_json_response({"ok": True, "id": att_id})

    @staticmethod
    def _telegram_text(doc_type, full_name, evidence):
        payload = evidence["raw_payload"] or {}
        if doc_type == "zwrot":
            lines = [
                "💸 Новий wniosek o zwrot",
                f"Заявник: {full_name}",
                f"№ zamówienia: {evidence['doc_number'] or '—'}",
                f"Турнус: {payload.get('turnus') or '—'}",
                f"Сума: {payload.get('kwota') or '—'} zł",
                f"Właściciel rachunku: {payload.get('wlasciciel_rachunku') or '—'}",
                f"IBAN: {payload.get('iban') or '—'}",
                f"Причина: {payload.get('przyczyna') or '—'}",
                f"Контакт: {evidence['contact'] or '—'}",
                f"IP: {evidence['ip_address'] or '—'} · Час: {evidence['submitted_at']}",
            ]
            return "\n".join(lines)
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
