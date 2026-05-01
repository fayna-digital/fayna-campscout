"""Vozhatyi (wychowawca / kierownik) training tracker — Rozp. MEN 2016.

Migrated from `fayna_camp_vozhatyi_school` (uninstalled, scheduled for deletion)
into `fayna_camp_portal` per consolidation plan.

Models (4):
- fayna.vozhatyi.training         — full training program with module breakdown
- fayna.vozhatyi.training.module  — individual unit within a program
- fayna.vozhatyi.certificate      — issued certificate, 5y validity, daily expiry cron
- vozhatyi.training.record        — flat per-person completion record

Coexists with the existing `slide.channel`-based `camp.staff.training.record`
(see training.py): the slide.channel system is for native eLearning courses
delivered through Odoo Website Slides; this module tracks PL-law-defined
36h/10h external training that does not use video lessons.

Note re. website_slides: source module did NOT depend on website_slides
(only base, mail, portal), so this is NOT a port to eLearning — it preserves
the standalone tracker by design. If a future iteration moves these courses
into Odoo eLearning, prefer the existing `camp.staff.training.record` path.

Legal:
- Rozp. MEN 2016 (Dz.U. 2016 poz. 2148) §3 wychowawca 36h, §4 kierownik 10h
- Certificate validity: 5 years from issue date (industry convention).
"""

import uuid

from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FaynaVozhatyiTraining(models.Model):
    _name = "fayna.vozhatyi.training"
    _description = "Wychowawca / Kierownik Training Program (Rozp. MEN 2016)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_date desc, name"

    name = fields.Char(
        string="Training Name",
        required=True,
        index=True,
        tracking=True,
    )
    participant_id = fields.Many2one(
        "res.partner",
        string="Participant",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    training_type = fields.Selection(
        [
            ("wychowawca_36h", "Wychowawca (36h)"),
            ("kierownik_10h", "Kierownik (10h)"),
        ],
        string="Training Type",
        required=True,
        index=True,
        default="wychowawca_36h",
        tracking=True,
    )
    start_date = fields.Date(string="Start Date", index=True, tracking=True)
    end_date = fields.Date(string="End Date", tracking=True)
    location = fields.Char(string="Location")
    instructor_id = fields.Many2one(
        "res.partner",
        string="Instructor",
        index=True,
        ondelete="set null",
    )

    module_ids = fields.One2many(
        "fayna.vozhatyi.training.module",
        "training_id",
        string="Training Modules",
    )
    certificate_ids = fields.One2many(
        "fayna.vozhatyi.certificate",
        "training_id",
        string="Certificates",
        readonly=True,
    )
    completion_pct = fields.Float(
        string="Completion %",
        compute="_compute_completion_pct",
        store=True,
        help="Percentage of modules marked as completed",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("certified", "Certified"),
        ],
        string="Status",
        default="draft",
        required=True,
        index=True,
        tracking=True,
    )

    total_hours = fields.Float(
        string="Total Hours",
        compute="_compute_total_hours",
        store=True,
        help="Sum of completed module hours",
    )
    required_hours = fields.Float(
        string="Required Hours",
        compute="_compute_required_hours",
        store=True,
    )

    certificate_date = fields.Date(string="Certificate Date", tracking=True)
    certificate_number = fields.Char(
        string="Certificate Number",
        index=True,
        tracking=True,
        copy=False,
    )

    certificate_id = fields.Many2one(
        "fayna.vozhatyi.certificate",
        string="Certificate",
        readonly=True,
        copy=False,
    )

    @api.depends("module_ids.hours", "module_ids.completed")
    def _compute_total_hours(self):
        for rec in self:
            rec.total_hours = sum(m.hours for m in rec.module_ids if m.completed)

    @api.depends("module_ids", "module_ids.completed")
    def _compute_completion_pct(self):
        for rec in self:
            total = len(rec.module_ids)
            if total == 0:
                rec.completion_pct = 0.0
            else:
                done = sum(1 for m in rec.module_ids if m.completed)
                rec.completion_pct = (done / total) * 100.0

    @api.depends("training_type")
    def _compute_required_hours(self):
        for rec in self:
            rec.required_hours = 36.0 if rec.training_type == "wychowawca_36h" else 10.0

    def action_start(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Training must be in Draft state to start."))
            rec.state = "in_progress"

    def action_complete(self):
        """Mark training as completed and generate a certificate number."""
        for rec in self:
            if rec.state not in ("draft", "in_progress"):
                raise UserError(_("Training must be Draft or In Progress to complete."))

            cert_number = f"FAYNA-{rec.training_type.upper()[:3]}-{uuid.uuid4().hex[:8].upper()}"
            rec.write(
                {
                    "state": "completed",
                    "certificate_date": fields.Date.today(),
                    "certificate_number": cert_number,
                }
            )

            # Map training_type → cert_type
            cert_type = "wychowawca" if rec.training_type == "wychowawca_36h" else "kierownik"

            # Create certificate record
            cert = self.env["fayna.vozhatyi.certificate"].create(
                {
                    "training_id": rec.id,
                    "partner_id": rec.participant_id.id,
                    "issue_date": fields.Date.today(),
                    "certificate_number": cert_number,
                    "cert_type": cert_type,
                }
            )
            rec.certificate_id = cert.id
            rec.state = "certified"

    def action_reset_draft(self):
        for rec in self:
            if rec.state == "certified":
                raise UserError(_("Certified training cannot be reset to draft."))
            rec.state = "draft"

    @api.constrains("start_date", "end_date")
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date < rec.start_date:
                raise UserError(_("End date cannot be before start date."))


class FaynaVozhatyiTrainingModule(models.Model):
    _name = "fayna.vozhatyi.training.module"
    _description = "Training Module (individual unit within a training program)"
    _order = "training_id, sequence"

    STANDARD_MODULES = [
        ("group_dynamics", "Group Dynamics (Tuckman Phases)"),
        ("first_aid", "First Aid (BLS/AED)"),
        ("cultural", "Cultural Activities"),
        ("tourism", "Outdoor & Tourism"),
        ("safety", "Camp Safety & Emergency Protocol"),
        ("law_basics", "Legal Basics (PL Camp Law)"),
        ("child_protection", "Child Protection (Art. 160 KK / Kamilka Act)"),
    ]

    training_id = fields.Many2one(
        "fayna.vozhatyi.training",
        string="Training",
        required=True,
        index=True,
        ondelete="cascade",
    )
    name = fields.Char(
        string="Module Name",
        required=True,
    )
    module_type = fields.Selection(
        STANDARD_MODULES,
        string="Standard Module",
        index=True,
        help="Select a standard PL-law-defined module, or leave blank for a custom one.",
    )
    sequence = fields.Integer(string="Sequence", default=10)
    hours = fields.Float(
        string="Hours",
        required=True,
        default=1.0,
        help="Duration of this module in hours",
    )
    completed = fields.Boolean(
        string="Completed",
        default=False,
    )
    completion_date = fields.Date(string="Completion Date")
    notes = fields.Text(string="Notes")

    @api.constrains("hours")
    def _check_hours(self):
        for rec in self:
            if rec.hours <= 0:
                raise UserError(_("Module hours must be positive."))

    @api.onchange("module_type")
    def _onchange_module_type(self):
        if self.module_type and not self.name:
            for key, label in self.STANDARD_MODULES:
                if key == self.module_type:
                    self.name = label
                    break

    def action_mark_completed(self):
        for rec in self:
            rec.write(
                {
                    "completed": True,
                    "completion_date": rec.completion_date or fields.Date.today(),
                }
            )


class FaynaVozhatyiCertificate(models.Model):
    _name = "fayna.vozhatyi.certificate"
    _description = "Wychowawca / Kierownik Training Certificate"
    _inherit = ["mail.thread"]
    _order = "issue_date desc"

    _sql_constraints = [
        (
            "certificate_number_unique",
            "UNIQUE(certificate_number)",
            "Certificate number must be unique.",
        )
    ]

    training_id = fields.Many2one(
        "fayna.vozhatyi.training",
        string="Training",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Holder",
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    issue_date = fields.Date(
        string="Issue Date",
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    valid_until = fields.Date(
        string="Valid Until",
        compute="_compute_valid_until",
        store=True,
        tracking=True,
    )
    certificate_number = fields.Char(
        string="Certificate Number",
        required=True,
        index=True,
        copy=False,
        tracking=True,
    )
    cert_type = fields.Selection(
        [
            ("wychowawca", "Wychowawca"),
            ("kierownik", "Kierownik"),
        ],
        string="Certificate Type",
        index=True,
        tracking=True,
    )
    is_expired = fields.Boolean(
        string="Is Expired",
        compute="_compute_is_expired",
        store=True,
        help="True when valid_until has passed",
    )
    state = fields.Selection(
        [
            ("active", "Active"),
            ("expired", "Expired"),
        ],
        string="Status",
        compute="_compute_state",
        store=True,
        index=True,
        tracking=True,
    )

    @api.depends("issue_date")
    def _compute_valid_until(self):
        for rec in self:
            if rec.issue_date:
                rec.valid_until = rec.issue_date + relativedelta(years=5)
            else:
                rec.valid_until = False

    @api.depends("valid_until")
    def _compute_is_expired(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_expired = bool(rec.valid_until and rec.valid_until < today)

    @api.depends("valid_until")
    def _compute_state(self):
        today = fields.Date.today()
        for rec in self:
            if rec.valid_until and rec.valid_until < today:
                rec.state = "expired"
            else:
                rec.state = "active"

    def action_mark_expired(self):
        """Manually expire a certificate (e.g. revocation)."""
        for rec in self:
            if rec.state == "expired":
                raise UserError(_("Certificate is already expired."))
            rec.valid_until = fields.Date.today()
            rec._compute_state()

    @api.model
    def _cron_expire_certificates(self):
        """Daily cron: recompute state for all certificates so expired ones flip."""
        certs = self.search([("state", "=", "active")])
        certs._compute_state()
        expired = certs.filtered(lambda c: c.state == "expired")
        for cert in expired:
            cert.message_post(
                body=_("Certificate automatically marked as Expired (validity date passed).")
            )

    def action_print_certificate(self):
        self.ensure_one()
        return self.env.ref(
            "fayna_camp_portal.fayna_vozhatyi_certificate_report_action"
        ).report_action(self)


class VozhatyiTrainingRecord(models.Model):
    """Per-person training completion record for Szkoła Wychowawców.

    Tracks who completed which training, certificate number, validity window,
    and current lifecycle state. Designed to be simple and flat — one row per
    person per training type (as opposed to the detailed module-level tracking
    in fayna.vozhatyi.training).
    """

    _name = "vozhatyi.training.record"
    _description = "Vozhatyi Training Record"
    _inherit = ["mail.thread"]
    _order = "completion_date desc, id desc"
    _rec_name = "display_name"

    # ── Core fields ──────────────────────────────────────────────────────────
    partner_id = fields.Many2one(
        "res.partner",
        string=_("Trainee"),
        required=True,
        index=True,
        ondelete="restrict",
        tracking=True,
    )
    training_type = fields.Selection(
        [
            ("wychowawca_36h", "Kurs wychowawcy (36h)"),
            ("kierownik_10h", "Kurs kierownika (10h)"),
            ("first_aid", "First aid / BLS"),
            ("online_platform", "Platform training (§2.15)"),
            ("other", "Other"),
        ],
        string=_("Training Type"),
        index=True,
        tracking=True,
    )
    completion_date = fields.Date(
        string=_("Completion Date"),
        index=True,
        tracking=True,
    )
    certificate_number = fields.Char(
        string=_("Certificate Number"),
        index=True,
        copy=False,
        tracking=True,
    )
    valid_until = fields.Date(
        string=_("Valid Until"),
        index=True,
        tracking=True,
        help="Typically 5 years from completion date (Rozp. MEN 2016).",
    )
    notes = fields.Text(
        string=_("Notes"),
    )
    state = fields.Selection(
        [
            ("enrolled", "Enrolled"),
            ("completed", "Completed"),
            ("expired", "Expired"),
        ],
        string=_("Status"),
        default="enrolled",
        required=True,
        index=True,
        tracking=True,
    )

    # ── Display ──────────────────────────────────────────────────────────────
    display_name = fields.Char(
        string=_("Label"),
        compute="_compute_display_name",
        store=True,
    )

    @api.depends("partner_id", "training_type", "state")
    def _compute_display_name(self):
        type_labels = dict(self._fields["training_type"].selection)
        for rec in self:
            partner_name = rec.partner_id.name if rec.partner_id else "?"
            type_label = type_labels.get(rec.training_type or "", "?")
            rec.display_name = f"{partner_name} — {type_label}"

    # ── State buttons ────────────────────────────────────────────────────────
    def action_complete(self):
        """Mark record as completed."""
        for rec in self:
            if rec.state != "enrolled":
                raise UserError(_("Only enrolled records can be marked as completed."))
            rec.state = "completed"

    def action_expire(self):
        """Manually mark record as expired."""
        for rec in self:
            if rec.state == "expired":
                raise UserError(_("Record is already expired."))
            rec.state = "expired"

    def action_reset_enrolled(self):
        """Reset to enrolled (e.g. for re-enrolment after expiry)."""
        for rec in self:
            rec.state = "enrolled"

    # ── Cron ─────────────────────────────────────────────────────────────────
    @api.model
    def _cron_mark_expired(self):
        """Daily cron: flip completed records to expired when valid_until has passed."""
        import logging

        _logger = logging.getLogger(__name__)
        today = fields.Date.today()
        expired = self.search(
            [
                ("state", "=", "completed"),
                ("valid_until", "!=", False),
                ("valid_until", "<", today),
            ]
        )
        _logger.info("vozhatyi_training_record: marking %d records as expired", len(expired))
        expired.write({"state": "expired"})
        for rec in expired:
            rec.message_post(
                body=_("Training record automatically marked as Expired (valid_until passed).")
            )
