# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — Staff Recruitment (Фаза B)
# ADR: DevJournal/projects/campscout/it-project/09-ADR-FAZA-B-build.md
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

_CANDIDATE_GROUP = "fayna_camp_portal.group_camp_candidate"
_PORTAL_GROUP = "base.group_portal"


class CampStaffApplication(models.Model):
    """Заявка кандидата на вакансію виховника.

    Цикл: new → reviewing → accepted/rejected.
    При accepted → action_hire() (staffing.py:176) → camp.staff (draft) + portal-user.
    §13 RSPTS-гейт не обходиться: staff народжується draft, підтвердження — лише після
    верифікації KRK/RSPTS (operations.py:217).
    """

    _name = "camp.staff.application"
    _description = "Camp staff application"
    _inherit = ["mail.thread"]
    _order = "create_date desc, id desc"

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------

    name = fields.Char(
        string=_("Application ref"),
        compute="_compute_name",
        store=True,
        readonly=True,
    )

    vacancy_id = fields.Many2one(
        "camp.staff.vacancy",
        string=_("Vacancy"),
        required=True,
        ondelete="cascade",
        index=True,
    )
    event_id = fields.Many2one(
        "event.event",
        string=_("Camp event"),
        related="vacancy_id.event_id",
        store=True,
        readonly=True,
    )
    role = fields.Selection(
        string=_("Role"),
        related="vacancy_id.role",
        store=True,
        readonly=True,
    )

    candidate_name = fields.Char(
        string=_("Candidate name"),
        required=True,
        tracking=True,
    )
    candidate_email = fields.Char(
        string=_("E-mail"),
        required=True,
        tracking=True,
    )
    candidate_phone = fields.Char(
        string=_("Phone"),
    )
    message = fields.Text(
        string=_("Cover message"),
    )

    partner_id = fields.Many2one(
        "res.partner",
        string=_("Portal partner"),
        readonly=True,
        copy=False,
        index=True,
    )
    staff_id = fields.Many2one(
        "camp.staff",
        string=_("Staff record"),
        readonly=True,
        copy=False,
        ondelete="set null",
        index=True,
    )

    state = fields.Selection(
        [
            ("new", "New"),
            ("reviewing", "Reviewing"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
        ],
        default="new",
        required=True,
        tracking=True,
        string=_("State"),
    )
    rejection_reason = fields.Char(
        string=_("Rejection reason"),
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends("vacancy_id", "candidate_name")
    def _compute_name(self):
        for rec in self:
            vacancy = rec.vacancy_id.name if rec.vacancy_id else "?"
            candidate = rec.candidate_name or "?"
            rec.name = f"{vacancy} — {candidate}"

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def action_start_review(self):
        for rec in self:
            if rec.state != "new":
                raise UserError(_("Only new applications can be set to Reviewing."))
        self.write({"state": "reviewing"})
        return True

    def action_accept(self):
        """Прийняти заявку: найняти через вакансію, прив'язати portal-user.

        Послідовність:
        1. Перевірка стану (reviewing).
        2. Пишемо candidate_name у вакансію (щоб action_hire знав ім'я).
        3. vacancy.action_hire() → camp.staff (draft).
        4. _ensure_portal_user(email, name) → res.users (portal + candidate group).
        5. Прив'язуємо user до staff.user_id та application.partner_id.
        6. Повідомлення + invite partner.
        """
        self.ensure_one()
        if self.state not in ("new", "reviewing"):
            raise UserError(_("Application must be in New or Reviewing state to accept."))
        if not self.vacancy_id:
            raise UserError(_("No vacancy linked to this application."))

        # 2. Set candidate_name on vacancy so action_hire() can use it.
        self.vacancy_id.write({"candidate_name": self.candidate_name})

        # 3. Hire via vacancy (creates camp.staff in draft — §13 safe).
        self.vacancy_id.action_hire()
        # action_hire returns act_window dict; vacancy now has staff_id
        staff_record = self.vacancy_id.staff_id
        if not staff_record:
            raise ValidationError(_("action_hire did not produce a staff record."))

        # 4. Ensure portal user exists.
        user = self._ensure_portal_user(self.candidate_email, self.candidate_name)

        # 5. Link user to staff + application.
        staff_record.sudo().write({"user_id": user.id})
        self.write(
            {
                "state": "accepted",
                "staff_id": staff_record.id,
                "partner_id": user.partner_id.id,
            }
        )

        # 6. Notify.
        self.message_post(
            body=_(
                "Application accepted. Staff record created (draft): %(staff)s. "
                "Portal user: %(email)s",
                staff=staff_record.name,
                email=user.login,
            )
        )
        # Invite portal partner to follow the application.
        self.message_subscribe(partner_ids=[user.partner_id.id])
        return True

    def action_reject(self):
        self.ensure_one()
        if self.state == "accepted":
            raise UserError(_("Cannot reject an already accepted application."))
        self.write({"state": "rejected"})
        self.message_post(
            body=_(
                "Application rejected. Reason: %(reason)s",
                reason=self.rejection_reason or "—",
            )
        )
        # Vacancy stays open — ready for next candidate.
        return True

    # ------------------------------------------------------------------
    # B5 — portal user helper
    # ------------------------------------------------------------------

    def _ensure_portal_user(self, email, name):
        """Знайти або створити portal-user за email.

        - Якщо вже існує → додати group_camp_candidate (якщо нема).
        - Якщо нема → create з group_portal + group_camp_candidate + signup-token.
        - Захист від дублів: пошук по login (email, lower-cased).
        """
        email_lower = (email or "").strip().lower()
        if not email_lower:
            raise ValidationError(_("Candidate email is required to create portal access."))

        User = self.env["res.users"].sudo()
        user = User.search([("login", "=", email_lower)], limit=1)

        portal_group = self.env.ref("base.group_portal")
        candidate_group = self.env.ref(_CANDIDATE_GROUP)

        if user:
            # Merge candidate group if missing.
            if candidate_group not in user.groups_id:
                user.write({"groups_id": [(4, candidate_group.id)]})
            return user

        # Create new portal+candidate user.
        user = User.create(
            {
                "name": name or email_lower,
                "login": email_lower,
                "email": email_lower,
                "lang": "pl_PL",  # продукт = польський ринок (TZ §18.3 default pl_PL)
                "groups_id": [
                    (4, portal_group.id),
                    (4, candidate_group.id),
                ],
            }
        )
        # Send portal invite / signup link.
        try:
            user.action_reset_password()
        except Exception:
            _logger.warning(
                "[recruitment] Could not send portal invite to %s — check mail server.",
                email_lower,
            )
        return user
