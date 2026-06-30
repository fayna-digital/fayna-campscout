# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Staff training — Odoo eLearning (slide.channel) extension for MEN compliance.

Extends slide.channel with:
- Course type: wychowawca 36h / kierownik improvement / first_aid / specialty
- Required-hours tracking (MEN Rozp. 2016 §3)
- Per-partner training record with certificate issuance
- Staff event-assignment compliance check

ADR-001 decision: do not build a custom LMS; extend native slide.channel instead.
"""

import uuid

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SlideChannel(models.Model):
    """MEN-compliance extension for native eLearning channels."""

    _inherit = "slide.channel"

    camp_course_type = fields.Selection(
        [
            ("wychowawca", "Kurs wychowawcy (36h) — MEN"),
            ("kierownik_improvement", "Doskonalenie kierownika — MEN"),
            ("first_aid", "Pierwsza pomoc / BLS — AHA 2025"),
            ("specialty", "Kurs specjalistyczny"),
        ],
        string=_("Camp course type"),
        help=_(
            "Determines required hours and certificate type.\n"
            "Legal base: Rozp. MEN 2016 §3 (wychowawca 36h), §4 (kierownik improvement).\n"
            "CampScout can run wychowawca and improvement courses only — "
            "the official kierownik 10h course requires a separate institution license."
        ),
    )
    required_hours = fields.Float(
        string=_("Required hours"),
        default=0.0,
        help=_(
            "Minimum contact hours to pass the course and receive a certificate.\n"
            "MEN standard: wychowawca = 36h, doskonalenie = 10h."
        ),
    )
    is_men_course = fields.Boolean(
        string=_("MEN compliance course"),
        default=False,
        help=_(
            "Marks this channel as an official MEN-regulated training.\n"
            "Affects certificate template and compliance reporting."
        ),
    )
    training_record_ids = fields.One2many(
        "camp.staff.training.record",
        "channel_id",
        string=_("Training records"),
    )
    training_record_count = fields.Integer(
        compute="_compute_training_record_count",
        string=_("# Records"),
    )

    @api.depends("training_record_ids")
    def _compute_training_record_count(self):
        for ch in self:
            ch.training_record_count = len(ch.training_record_ids)

    def action_view_training_records(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Training records"),
            "res_model": "camp.staff.training.record",
            "view_mode": "tree,form",
            "domain": [("channel_id", "=", self.id)],
            "context": {"default_channel_id": self.id},
        }


class CampStaffTrainingRecord(models.Model):
    """Per-staff-member training completion record with certificate issuance.

    One record per (partner, channel) pair. Created when a staff member
    is enrolled; updated as they progress through slides; a certificate is
    issued when they reach or exceed required_hours.
    """

    _name = "camp.staff.training.record"
    _description = "Staff training completion record"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "issue_date desc, id"
    _rec_name = "display_name"

    # ── Identity ──────────────────────────────────────────────────────────────

    partner_id = fields.Many2one(
        "res.partner",
        required=True,
        index=True,
        ondelete="restrict",
        string=_("Staff member"),
        tracking=True,
        help=_("The person undergoing training. Must be a res.partner contact."),
    )
    channel_id = fields.Many2one(
        "slide.channel",
        required=True,
        index=True,
        ondelete="restrict",
        string=_("Course"),
        tracking=True,
        help=_("The eLearning channel this record is linked to."),
    )
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
        string=_("Name"),
    )

    # ── Progress ──────────────────────────────────────────────────────────────

    hours_completed = fields.Float(
        string=_("Hours completed"),
        default=0.0,
        tracking=True,
        help=_(
            "Contact hours accumulated by this staff member for this course.\n"
            "Update manually after each session or via automated cron."
        ),
    )
    slides_completed = fields.Integer(
        string=_("Slides completed"),
        default=0,
        help=_("Number of slides/modules marked as done."),
    )
    completion_pct = fields.Float(
        string=_("Completion %"),
        compute="_compute_completion_pct",
        store=True,
        help=_("Percentage of required hours completed."),
    )

    # ── State ──────────────────────────────────────────────────────────────────

    state = fields.Selection(
        [
            ("enrolled", "Enrolled"),
            ("in_progress", "In progress"),
            ("completed", "Completed"),
            ("certified", "Certified"),
            ("expired", "Expired"),
        ],
        default="enrolled",
        required=True,
        index=True,
        tracking=True,
        string=_("Status"),
        help=_(
            "enrolled → in_progress → completed → certified.\n"
            "expired: certificate validity has lapsed (MEN: 5-year renewal)."
        ),
    )

    # ── Certificate ────────────────────────────────────────────────────────────

    certificate_number = fields.Char(
        string=_("Certificate number"),
        index=True,
        copy=False,
        tracking=True,
        help=_(
            "Unique identifier assigned on certification. Format: CAMP-WYC-XXXXXXXX.\n"
            "Required for KRK / RPS presentation in Kuratorium notifications."
        ),
    )
    issue_date = fields.Date(
        string=_("Issue date"),
        tracking=True,
        help=_("Date when the certificate was issued."),
    )
    expiry_date = fields.Date(
        string=_("Valid until"),
        compute="_compute_expiry_date",
        store=True,
        help=_("MEN certificates are valid for 5 years from issue date."),
    )

    # ── Course metadata (denormalised for speed) ───────────────────────────────

    course_type = fields.Selection(
        related="channel_id.camp_course_type",
        store=True,
        string=_("Course type"),
        help=_("Mirrors the course type from the eLearning channel."),
    )
    required_hours = fields.Float(
        related="channel_id.required_hours",
        store=True,
        string=_("Required hours"),
        help=_("Total hours required to complete this course (from channel settings)."),
    )

    # ── SQL constraints ────────────────────────────────────────────────────────

    _sql_constraints = [
        (
            "unique_partner_channel",
            "UNIQUE(partner_id, channel_id)",
            "A staff member can have only one training record per course.",
        )
    ]

    # ── Computes ──────────────────────────────────────────────────────────────

    @api.depends("partner_id", "channel_id")
    def _compute_display_name(self):
        for rec in self:
            partner = rec.partner_id.name or "?"
            channel = rec.channel_id.name or "?"
            rec.display_name = f"{partner} — {channel}"

    @api.depends("hours_completed", "required_hours")
    def _compute_completion_pct(self):
        for rec in self:
            req = rec.required_hours or 0.0
            done = rec.hours_completed or 0.0
            rec.completion_pct = min(100.0, (done / req * 100.0) if req else 0.0)

    @api.depends("issue_date")
    def _compute_expiry_date(self):
        from dateutil.relativedelta import relativedelta

        for rec in self:
            if rec.issue_date:
                rec.expiry_date = rec.issue_date + relativedelta(years=5)
            else:
                rec.expiry_date = False

    # ── Constraints ───────────────────────────────────────────────────────────

    @api.constrains("hours_completed")
    def _check_hours(self):
        for rec in self:
            if rec.hours_completed < 0:
                raise ValidationError(_("Hours completed cannot be negative."))

    # ── State machine ─────────────────────────────────────────────────────────

    def action_start(self):
        for rec in self:
            if rec.state != "enrolled":
                raise UserError(_("Only enrolled records can be started."))
            rec.state = "in_progress"

    def action_complete(self):
        """Mark as completed. Does NOT issue certificate automatically — use action_certify."""
        for rec in self:
            if rec.state not in ("enrolled", "in_progress"):
                raise UserError(_("Only enrolled or in-progress records can be marked complete."))
            rec.state = "completed"

    def action_certify(self):
        """Issue certificate: generate number, set issue date, move to 'certified'."""
        for rec in self:
            if rec.state != "completed":
                raise UserError(_("Only completed records can be certified."))
            req = rec.required_hours or 0.0
            if req and rec.hours_completed < req:
                raise UserError(
                    _(
                        "Staff member has only %(done)s of %(req)s required hours. "
                        "Cannot issue certificate."
                    )
                    % {"done": rec.hours_completed, "req": req}
                )
            type_code = {
                "wychowawca": "WYC",
                "kierownik_improvement": "KIR",
                "first_aid": "FA",
                "specialty": "SP",
            }.get(rec.course_type or "", "CAMP")
            cert_num = f"CAMP-{type_code}-{uuid.uuid4().hex[:8].upper()}"
            rec.write(
                {
                    "state": "certified",
                    "certificate_number": cert_num,
                    "issue_date": fields.Date.today(),
                }
            )

    def action_expire(self):
        """Mark certificate as expired (5-year MEN renewal deadline passed)."""
        for rec in self:
            if rec.state != "certified":
                raise UserError(_("Only certified records can be expired."))
            rec.state = "expired"

    # ── Smart button action ────────────────────────────────────────────────────

    def action_view_channel(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Course"),
            "res_model": "slide.channel",
            "res_id": self.channel_id.id,
            "view_mode": "form",
        }
