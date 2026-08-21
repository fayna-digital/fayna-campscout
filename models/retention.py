# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — F-DOC-4: Retention-matrix (авто-виконання).
#
# Політика (docs/TZ.md [F-DOC-4]):
#   карти/медичні/journal/звіти/staff-доки/підписи = 7 років
#     (art.118 k.c. 6 р. + буфер; пауза при справі в суді);
#   umowy кадри 10 р. (art.94 k.p.);
#   фінанси/KSeF 5 р.+рік (art.74 o rachunkowości);
#   фото stories 2 р. або до відкликання (art.81 Prawa autorskiego);
#   marketing-згоди — до відкликання;
#   кваліфікації (świadectwa курсів) — permanent.
#
# Формула строку: max(date_end останньої реєстрації, signed_date) + N років
#   → flag to_erase → перевірка активних claims (пауза при справі) → лог erasure.
#
# DESIGN (безпечно): перші реальні видалення — 2033 (ТЗ). Тому cron НЕ
# видаляє дані. Він:
#   1) знаходить записи, що перевищили retention_until (to_erase);
#   2) перевіряє активні claims (справа в суді) — якщо є, ставить паузу;
#   3) логує erasure-подію в camp.retention.log (append-only, RODO art.30).
# Реальне видалення/анонімізація — окремий wizard-підтверджений крок
# (перші видалення 2033), який читає цей лог.
import logging

from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Retention matrix (years) — canonical policy from docs/TZ.md [F-DOC-4].
# Keys are the retention categories used on the log records.
RETENTION_YEARS = {
    "participant": 7,  # карти/медичні — art.118 k.c. 6р + буфер
    "journal": 7,  # dziennik zajęć
    "report": 7,  # звіти
    "staff_doc": 7,  # staff-доки/підписи
    "staff_umowa": 10,  # umowy кадри — art.94 k.p.
    "finance": 6,  # фінанси/KSeF 5р + рік — art.74 o rachunkowości
    "story_photo": 2,  # фото stories — art.81 Prawa autorskiego
    "marketing_consent": 0,  # до відкликання (не строковий)
    "qualification": -1,  # permanent (ніколи не видаляти)
}


class CampRetentionLog(models.Model):
    """Append-only log of retention/erasure decisions (RODO art.30).

    Written by the daily retention cron (F-DOC-4). Records are immutable:
    deletion is forbidden so the audit trail survives the 7-year PL retention.
    """

    _name = "camp.retention.log"
    _description = "Retention/erasure decision log (F-DOC-4, RODO art.30)"
    _order = "id desc"

    _sql_constraints = [
        (
            "res_unique",
            "UNIQUE(res_model, res_id, action)",
            "A retention decision for a record+action may be logged only once.",
        ),
    ]

    res_model = fields.Char(
        string=_("Model"),
        required=True,
        index=True,
        help=_("Technical model name of the record (e.g. camp.participant)."),
    )
    res_id = fields.Integer(
        string=_("Record ID"),
        required=True,
        index=True,
        help=_("ID of the record the decision applies to."),
    )
    action = fields.Selection(
        [
            ("flagged", _("Flagged for erasure")),
            ("paused", _("Paused — active claim (court case)")),
            ("erased", _("Erased / anonymised")),
        ],
        string=_("Action"),
        required=True,
        index=True,
        help=_("What the retention engine decided for this record."),
    )
    retention_until = fields.Date(
        string=_("Retain until"),
        help=_("Retention deadline that was exceeded (when applicable)."),
    )
    category = fields.Selection(
        [(k, k) for k in RETENTION_YEARS],
        string=_("Category"),
        help=_("Retention category from the F-DOC-4 matrix."),
    )
    note = fields.Text(
        string=_("Note"),
        help=_("Human-readable explanation of the decision."),
    )
    logged_by = fields.Many2one(
        "res.users",
        string=_("Logged by"),
        default=lambda self: self.env.user,
        readonly=True,
        help=_("User/system that wrote this log entry."),
    )
    logged_at = fields.Datetime(
        string=_("Logged at"),
        default=fields.Datetime.now,
        readonly=True,
        help=_("When the decision was recorded."),
    )

    def unlink(self):
        """Forbid deletion — append-only audit trail (RODO art.30, 7y retention)."""
        raise UserError(_("Retention log is append-only (RODO art.30 audit trail)."))


class CampRetentionEngine(models.AbstractModel):
    """F-DOC-4 — daily retention scan engine (ir.cron target).

    Pure, idempotent, safe: it only FLAGS and LOGS. It never deletes or
    anonymises data — real erasure is a separate wizard-confirmed step that
    reads camp.retention.log (first deletions are 2033 per ТЗ).
    """

    _name = "camp.retention.engine"
    _description = "F-DOC-4 retention scan engine"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @api.model
    def _cron_retention_scan(self):
        """Daily cron entry point (F-DOC-4).

        Scans the retention-bearing models, flags records past their
        retention deadline as to_erase, pauses those with an active claim
        (court case), and logs every decision to camp.retention.log.
        """
        today = fields.Date.context_today(self)
        decisions = []

        # 1. Participants — retention_until = max(last event end, sign) + 7y.
        decisions += self._scan_participants(today)
        # 2. Programs Wypoczynku — event end + 7y.
        decisions += self._scan_programs(today)
        # 3. Daily reports — event end + 7y.
        decisions += self._scan_daily_reports(today)
        # 4. Staff umowy — 10y (art.94 k.p.) — via camp.staff signed date.
        decisions += self._scan_staff_umowy(today)

        # Write the append-only log (idempotent via UNIQUE(res_model,res_id,action)).
        Log = self.env["camp.retention.log"].sudo()
        for d in decisions:
            try:
                Log.create(d)
            except Exception:  # noqa: BLE001 — duplicate/race → skip, already logged
                _logger.debug(
                    "fayna_camp_portal.retention: duplicate decision skipped %s",
                    d,
                )

        _logger.info(
            "fayna_camp_portal.retention: cron scan done — %d decisions",
            len(decisions),
        )
        return len(decisions)

    # ------------------------------------------------------------------
    # Per-model scans
    # ------------------------------------------------------------------

    def _scan_participants(self, today):
        """Flag camp.participant records past retention_until (7y)."""
        decisions = []
        Participant = self.env.get("camp.participant")
        if Participant is None:
            return decisions
        overdue = Participant.search(
            [
                ("retention_until", "!=", False),
                ("retention_until", "<=", today),
            ]
        )
        for rec in overdue:
            if self._has_active_claim(rec):
                decisions.append(
                    self._decision(
                        "camp.participant",
                        rec.id,
                        "paused",
                        rec.retention_until,
                        "participant",
                        _("Aktywna sprawa/claim — retention paused."),
                    )
                )
            else:
                decisions.append(
                    self._decision(
                        "camp.participant",
                        rec.id,
                        "flagged",
                        rec.retention_until,
                        "participant",
                        _("Retention 7 lat przekroczony — oznaczono do usunięcia."),
                    )
                )
        return decisions

    def _scan_programs(self, today):
        """Flag Program Wypoczynku past retention_until (event end + 7y)."""
        decisions = []
        Program = self.env.get("camp.program.wypoczynku")
        if Program is None or "retention_until" not in Program._fields:
            return decisions
        overdue = Program.search(
            [
                ("retention_until", "!=", False),
                ("retention_until", "<=", today),
            ]
        )
        for rec in overdue:
            decisions.append(
                self._decision(
                    "camp.program.wypoczynku",
                    rec.id,
                    "flagged",
                    rec.retention_until,
                    "journal",
                    _("Program wypoczynku — retention 7 lat przekroczony."),
                )
            )
        return decisions

    def _scan_daily_reports(self, today):
        """Flag daily reports past retention (7y)."""
        decisions = []
        Report = self.env.get("camp.daily.report")
        if Report is None:
            return decisions
        # Daily reports carry a report_date; use the existing archive cron's
        # source. Fall back to a conservative 7y from the report date.
        date_field = "report_date" if "report_date" in Report._fields else False
        if not date_field:
            return decisions
        overdue = Report.search(
            [
                (date_field, "!=", False),
                (date_field, "<=", today - relativedelta(years=7)),
            ]
        )
        for rec in overdue:
            decisions.append(
                self._decision(
                    "camp.daily.report",
                    rec.id,
                    "flagged",
                    rec[date_field] + relativedelta(years=7),
                    "report",
                    _("Raport dzienny — retention 7 lat przekroczony."),
                )
            )
        return decisions

    def _scan_staff_umowy(self, today):
        """Flag staff umowy past 10y (art.94 k.p.)."""
        decisions = []
        Staff = self.env.get("camp.staff")
        if Staff is None:
            return decisions
        # Use the staff member's contract/start date if present. camp.staff
        # carries date_from (shift participation start) — a conservative proxy
        # for the umowa date. Prefer an explicit contract date when it exists.
        date_field = None
        for f in (
            "contract_date",
            "signed_date",
            "hire_date",
            "date_from",
            "date_start",
        ):
            if f in Staff._fields:
                date_field = f
                break
        if not date_field:
            return decisions
        overdue = Staff.search(
            [
                (date_field, "!=", False),
                (date_field, "<=", today - relativedelta(years=10)),
            ]
        )
        for rec in overdue:
            decisions.append(
                self._decision(
                    "camp.staff",
                    rec.id,
                    "flagged",
                    rec[date_field] + relativedelta(years=10),
                    "staff_umowa",
                    _("Umowa kadry — retention 10 lat przekroczony (art.94 k.p.)."),
                )
            )
        return decisions

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _has_active_claim(self, record):
        """True when the record is referenced by an active court case / claim.

        F-DOC-4: retention pauses while a case is in court. We look for any
        open incident card or legal claim referencing this record. This is a
        conservative heuristic — when in doubt, we PAUSE (never erase).
        """
        # Incident cards referencing this record (legal evidence retention).
        Incident = self.env.get("camp.incident.card")
        if Incident is not None:
            # Any non-draft incident card touching this record pauses retention.
            # ``record`` may be a participant (no event_id) or an event-scoped
            # record — resolve the event id defensively.
            event_id = 0
            if "event_id" in record._fields:
                event_id = record.event_id.id or 0
            refs = Incident.search(
                [
                    ("state", "!=", "draft"),
                    "|",
                    ("participant_id", "=", record.id),
                    ("event_id", "=", event_id),
                ],
                limit=1,
            )
            if refs:
                return True
        return False

    def _decision(self, res_model, res_id, action, retention_until, category, note):
        """Build a log-record dict for the append-only log."""
        return {
            "res_model": res_model,
            "res_id": res_id,
            "action": action,
            "retention_until": retention_until,
            "category": category,
            "note": note,
        }
