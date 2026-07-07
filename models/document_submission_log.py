# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Append-only лог поданих документів (кадра табору + згоди батьків), підписаних
поза Odoo-порталом (статичні форми kadry-forms/campscout, kadry-forms/rodzice —
client-side pdfmake, без порталу). Мета: докази IP+час подання на випадок спору.

Портал (/my/participants) не використовується для цього, бо staging тримає
тестові дані (SEED/test events), а не реальні сім'ї — див. INC-216 контекст.
"""
import base64
import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class CampDocumentSubmissionLog(models.Model):
    """Незмінний запис: хто, що, коли подав + IP + сам PDF як доказ."""

    _name = "camp.document.submission.log"
    _description = "Camp document submission log (evidence: IP + timestamp)"
    _order = "create_date desc"

    doc_type = fields.Selection(
        [
            ("wychowawca", "Kadra — instruktor/wolontariusz"),
            ("rodzic", "Rodzic — zgody 4a/4b"),
        ],
        required=True,
        string=_("Typ dokumentu"),
    )
    full_name = fields.Char(required=True, string=_("Imię i nazwisko"))
    contact = fields.Char(string=_("Telefon/e-mail"))
    doc_number = fields.Char(string=_("Numer dokumentu (auto)"))
    ip_address = fields.Char(string=_("IP nadawcy"), readonly=True)
    submitted_at = fields.Datetime(
        string=_("Data/godzina złożenia"), default=fields.Datetime.now, readonly=True
    )
    raw_payload = fields.Text(string=_("Pełne dane formularza (JSON)"))
    pdf_attachment_id = fields.Many2one(
        "ir.attachment", string=_("Podpisany PDF"), readonly=True
    )

    def name_get(self):
        return [
            (rec.id, f"{dict(rec._fields['doc_type'].selection).get(rec.doc_type)} — {rec.full_name}")
            for rec in self
        ]

    @staticmethod
    def create_from_submission(env, doc_type, full_name, contact, doc_number, ip_address, raw_payload, pdf_base64, pdf_filename):
        """Створює лог-запис + прикріплює PDF як ir.attachment (sudo — публічний endpoint)."""
        Log = env["camp.document.submission.log"].sudo()
        Attachment = env["ir.attachment"].sudo()

        attachment = False
        if pdf_base64:
            try:
                attachment = Attachment.create(
                    {
                        "name": pdf_filename or "dokument.pdf",
                        "datas": pdf_base64,
                        "mimetype": "application/pdf",
                        "res_model": "camp.document.submission.log",
                    }
                )
            except Exception as e:  # noqa: BLE001 — non-fatal: log record без PDF краще, ніж 500
                _logger.error("[camp.document.submission.log] attachment create failed: %s", e)

        record = Log.create(
            {
                "doc_type": doc_type,
                "full_name": full_name,
                "contact": contact,
                "doc_number": doc_number,
                "ip_address": ip_address,
                "raw_payload": raw_payload,
                "pdf_attachment_id": attachment.id if attachment else False,
            }
        )
        if attachment:
            attachment.write({"res_id": record.id})
        return record
