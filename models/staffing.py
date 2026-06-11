# Fayna CampScout — автоштат §2 + легкі вакансії (TZ_SPRINT_2026-06-10 §6, R12/R13)
#
# Engine:
#   camp.staff.vacancy   — легка внутрішня модель вакансії (R13: БЕЗ hr_recruitment).
#                          open → candidate → hired → (closed вручну).
#   event.event inherit  — required/current wychowawcy + gap + overstaffed,
#                          _sync_staff_vacancies() — серце двигуна.
#   event.registration inherit — тригер: create / write(state) → sync.
#
# Потреба (ПРОСТА модель, НЕ через camp.group — групи живуть окремо):
#   required = ceil(діти<10 / 15) + ceil(решта / 20)
#   (ліміти art. 92c — імпортуються з camp_group, не дублюються).
#
# R13 (рішення user-а): скасування реєстрацій НЕ авто-закриває найняту кадру —
#   лише overstaffed=True + message_post; рішення за людиною.
# R12: ставка за турнус з ir.config_parameter
#   fayna_camp_portal.salary_wychowawca_default / salary_kierownik_default.
#
# Мапінг ролей [ПЕРЕВІРЕНО grep 2026-06-10]: camp.staff.role НЕ має ключа
# 'wychowawca' — селекшен оперує 'counselor' / 'leader' / 'activity_lead'.
# Вакансія говорить юридичною мовою (wychowawca/kierownik/instructor),
# найм транслює в технічні ключі camp.staff через _VACANCY_TO_STAFF_ROLE.
import logging
import math

from dateutil.relativedelta import relativedelta
from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .camp_group import GROUP_LIMIT_DEFAULT, GROUP_LIMIT_UNDER_10, UNDER_10_AGE

_logger = logging.getLogger(__name__)

# ir.config_parameter keys (R12) — wizard «Новий табір» uses the same keys.
SALARY_PARAM_BY_ROLE = {
    "wychowawca": "fayna_camp_portal.salary_wychowawca_default",
    "kierownik": "fayna_camp_portal.salary_kierownik_default",
}

# vacancy.role (legal language) → camp.staff.role (technical selection key).
_VACANCY_TO_STAFF_ROLE = {
    "wychowawca": "counselor",
    "kierownik": "leader",
    "instructor": "activity_lead",
}

# Budget line name pattern — dedup key for auto-added salary lines.
_VACANCY_LINE_NAME = "Wakat wychowawca #%d"


# ---------------------------------------------------------------------------
# camp.staff.vacancy — легка вакансія (R13)
# ---------------------------------------------------------------------------


class CampStaffVacancy(models.Model):
    _name = "camp.staff.vacancy"
    _description = "Wakat kadry (autoштат §2 — легка модель, R13)"
    _inherit = ["mail.thread"]
    _order = "event_id, id"

    name = fields.Char(
        required=True,
        default=lambda self: _("Wakat"),
        tracking=True,
        string=_("Name"),
        help=_("Auto: 'Wakat wychowawca #N' — same string keys the budget line (dedup)."),
    )
    event_id = fields.Many2one(
        "event.event",
        required=True,
        index=True,
        ondelete="cascade",
        tracking=True,
        string=_("Camp shift (event)"),
        help=_("The shift this vacancy belongs to."),
    )
    role = fields.Selection(
        [
            ("wychowawca", "Wychowawca"),
            ("kierownik", "Kierownik wypoczynku"),
            ("instructor", "Instructor"),
        ],
        required=True,
        default="wychowawca",
        index=True,
        tracking=True,
        string=_("Role"),
        help=_(
            "Legal role of the vacancy. Hiring maps it onto camp.staff.role "
            "technical keys (wychowawca→counselor, kierownik→leader, "
            "instructor→activity_lead)."
        ),
    )
    state = fields.Selection(
        [
            ("open", "Open"),
            ("candidate", "Candidate"),
            ("hired", "Hired"),
            ("closed", "Closed"),
        ],
        required=True,
        default="open",
        index=True,
        tracking=True,
        string=_("Status"),
        help=_(
            "open → candidate → hired. Closing is MANUAL ONLY — registration "
            "cancellations never auto-close a vacancy with hired staff (R13)."
        ),
    )
    candidate_name = fields.Char(
        tracking=True,
        string=_("Candidate"),
        help=_("Full name of the candidate being considered / hired."),
    )
    notes = fields.Text(
        string=_("Notes"),
        help=_("Recruitment notes (source, interview remarks, availability)."),
    )
    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        string=_("Currency"),
    )
    salary_amount = fields.Monetary(
        currency_field="currency_id",
        default=lambda self: self._default_salary("wychowawca"),
        tracking=True,
        string=_("Stawka za turnus"),
        help=_(
            "Salary per shift (R12) — default from ir.config_parameter "
            "fayna_camp_portal.salary_wychowawca_default / salary_kierownik_default."
        ),
    )
    created_reason = fields.Char(
        string=_("Created because"),
        help=_(
            "Why the engine opened this vacancy (e.g. 'registrations crossed art. 92c threshold')."
        ),
    )
    staff_id = fields.Many2one(
        "camp.staff",
        readonly=True,
        copy=False,
        index=True,
        ondelete="set null",
        string=_("Hired staff"),
        help=_(
            "camp.staff record created by Hire (draft — RSPTS gate applies before confirmation)."
        ),
    )

    @api.model
    def _default_salary(self, role):
        param = SALARY_PARAM_BY_ROLE.get(role)
        if not param:
            return 0.0
        raw = self.env["ir.config_parameter"].sudo().get_param(param, "0")
        try:
            return float(raw or 0)
        except ValueError:
            _logger.warning("[camp_staffing] Bad value %r for config param %s", raw, param)
            return 0.0

    @api.onchange("role")
    def _onchange_role_salary(self):
        for vacancy in self:
            if vacancy.role and not vacancy.salary_amount:
                vacancy.salary_amount = self._default_salary(vacancy.role)

    # ------------------------------------------------------------------
    # Hire
    # ------------------------------------------------------------------

    def action_hire(self):
        """Hire the candidate: create a DRAFT camp.staff record and link it.

        Deliberately draft, NOT confirmed: the §13 RSPTS hard block
        (camp.staff._check_rspts_before_admission) forbids confirmed/active
        staff without verified KRK+RSPTS — the new hire must first upload
        documents and get admin acceptance.
        """
        self.ensure_one()
        if self.state == "hired":
            raise UserError(_("This vacancy is already hired."))
        if self.state == "closed":
            raise UserError(_("This vacancy is closed — reopen it before hiring."))
        if not self.candidate_name:
            raise UserError(_("Enter the candidate name before hiring."))
        event = self.event_id
        date_from = event.date_begin.date() if event.date_begin else fields.Date.context_today(self)
        date_to = event.date_end.date() if event.date_end else date_from
        staff = self.env["camp.staff"].create(
            {
                "name": self.candidate_name,
                "event_id": event.id,
                "role": _VACANCY_TO_STAFF_ROLE.get(self.role, "counselor"),
                "date_from": date_from,
                "date_to": date_to,
                "state": "draft",  # RSPTS gate: confirmation only after verification
                "notes": _("Hired via vacancy '%(vacancy)s'.", vacancy=self.name),
            }
        )
        self.write({"state": "hired", "staff_id": staff.id})
        self.message_post(
            body=_(
                "Zatrudniono: %(name)s (camp.staff draft — czeka na weryfikację KRK/RSPTS).",
                name=self.candidate_name,
            )
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Staff member"),
            "res_model": "camp.staff",
            "res_id": staff.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_set_candidate(self):
        for vacancy in self:
            if vacancy.state != "open":
                raise UserError(_("Only open vacancies can move to Candidate."))
        self.write({"state": "candidate"})
        return True

    def action_close(self):
        """Manual close — the ONLY way a vacancy closes (R13)."""
        self.write({"state": "closed"})
        return True

    def action_reopen(self):
        for vacancy in self:
            if vacancy.state != "closed":
                raise UserError(_("Only closed vacancies can be reopened."))
        self.write({"state": "open"})
        return True


# ---------------------------------------------------------------------------
# event.event — staffing computes + sync engine
# ---------------------------------------------------------------------------


class EventEventStaffing(models.Model):
    _inherit = "event.event"

    staff_vacancy_ids = fields.One2many(
        "camp.staff.vacancy",
        "event_id",
        string=_("Staff vacancies"),
        help=_("Vacancies of this shift (auto-opened by the staffing engine + manual)."),
    )
    staff_vacancy_count = fields.Integer(
        compute="_compute_staffing",
        string=_("# vacancies (pipeline)"),
        help=_("Vacancies in open/candidate/hired — the wychowawca hiring pipeline."),
    )
    required_wychowawcy = fields.Integer(
        compute="_compute_staffing",
        string=_("Required wychowawcy"),
        help=_(
            "ceil(children under 10 / 15) + ceil(others / 20) over open/done "
            "registrations (art. 92c limits; age on shift start date). "
            "Children without birth_date count with the 20-limit."
        ),
    )
    current_wychowawcy = fields.Integer(
        compute="_compute_staffing",
        string=_("Current wychowawcy"),
        help=_("camp.staff in confirmed/active with role 'counselor' (= wychowawca)."),
    )
    staffing_gap = fields.Integer(
        compute="_compute_staffing",
        string=_("Staffing gap"),
        help=_("required − current. Positive = wychowawcy missing."),
    )
    overstaffed = fields.Boolean(
        compute="_compute_staffing",
        string=_("Overstaffed"),
        help=_(
            "True when required < current + hired vacancies (e.g. after "
            "registration cancellations). Nothing is auto-closed — decision "
            "stays with a human (R13)."
        ),
    )
    overstaffed_notified = fields.Boolean(
        default=False,
        copy=False,
        string=_("Overstaffing already notified"),
        help=_("Spam guard: the engine posts the overstaffing message once per episode."),
    )

    @api.depends(
        "registration_ids.state",
        "registration_ids.participant_id.birth_date",
        "date_begin",
        "staff_ids.state",
        "staff_ids.role",
        "staff_vacancy_ids.state",
        "staff_vacancy_ids.role",
    )
    def _compute_staffing(self):
        for event in self:
            start = (
                event.date_begin.date() if event.date_begin else fields.Date.context_today(event)
            )
            young = others = 0
            for reg in event.registration_ids:
                if reg.state not in ("open", "done"):
                    continue
                child = reg.participant_id
                if (
                    child
                    and child.birth_date
                    and relativedelta(start, child.birth_date).years < UNDER_10_AGE
                ):
                    young += 1
                else:
                    # No participant / no birth_date → safe side of the
                    # simple model: counted with the default 20-limit.
                    others += 1
            required = math.ceil(young / GROUP_LIMIT_UNDER_10) + math.ceil(
                others / GROUP_LIMIT_DEFAULT
            )
            current = len(
                event.staff_ids.filtered(
                    lambda s: s.state in ("confirmed", "active") and s.role == "counselor"
                )
            )
            pipeline = event.staff_vacancy_ids.filtered(
                lambda v: v.role == "wychowawca" and v.state in ("open", "candidate", "hired")
            )
            hired = len(pipeline.filtered(lambda v: v.state == "hired"))
            event.required_wychowawcy = required
            event.current_wychowawcy = current
            event.staffing_gap = required - current
            event.staff_vacancy_count = len(pipeline)
            event.overstaffed = required < (current + hired)

    # ------------------------------------------------------------------
    # Sync engine (§6 / R13)
    # ------------------------------------------------------------------

    def _sync_staff_vacancies(self):
        """Align the wychowawca vacancy pipeline with registration counts.

        gap > pipeline → open the missing vacancies, post «Потрібен +N»,
        add one salary budget line per vacancy (dedup by the vacancy name)
        IF the budget already exists.

        gap < 0 with hired staff/vacancies → NOTHING is closed (R13):
        only overstaffed=True (compute) + a single message_post.
        """
        vacancy_model = self.env["camp.staff.vacancy"]
        for event in self:
            required = event.required_wychowawcy
            covered = event.current_wychowawcy
            pipeline = event.staff_vacancy_ids.filtered(
                lambda v: v.role == "wychowawca" and v.state in ("open", "candidate", "hired")
            )
            missing = required - covered - len(pipeline)

            if missing > 0:
                salary = vacancy_model._default_salary("wychowawca")
                # Numbering continues over ALL wychowawca vacancies ever
                # created for this shift (incl. closed) — names stay unique.
                next_no = (
                    len(event.staff_vacancy_ids.filtered(lambda v: v.role == "wychowawca")) + 1
                )
                for offset in range(missing):
                    name = _VACANCY_LINE_NAME % (next_no + offset)
                    vacancy_model.create(
                        {
                            "name": name,
                            "event_id": event.id,
                            "role": "wychowawca",
                            "state": "open",
                            "salary_amount": salary,
                            "created_reason": _(
                                "Auto: registrations crossed the art. 92c "
                                "threshold (required %(req)d, covered %(cov)d).",
                                req=required,
                                cov=covered + len(pipeline) + offset,
                            ),
                        }
                    )
                    event._add_vacancy_budget_line(name, salary)
                event.message_post(
                    body=_(
                        "Потрібен +%(n)d wychowawca: реєстрації перетнули поріг "
                        "art. 92c (потреба %(req)d, покрито %(cov)d). "
                        "Відкрито вакансії автоматично.",
                        n=missing,
                        req=required,
                        cov=covered + len(pipeline),
                    )
                )
                if event.overstaffed_notified:
                    event.overstaffed_notified = False
            elif event.overstaffed:
                # R13: NO auto-closing of hired staff — flag + one message.
                if not event.overstaffed_notified:
                    event.message_post(
                        body=_(
                            "Overstaffing: після скасувань потреба впала до "
                            "%(req)d wychowawców, а найнято більше. Вакансії "
                            "та кадра НЕ закриті автоматично (R13) — рішення "
                            "за організатором.",
                            req=required,
                        )
                    )
                    event.overstaffed_notified = True
            elif event.overstaffed_notified:
                # Back to normal — re-arm the spam guard.
                event.overstaffed_notified = False
        return True

    def _add_vacancy_budget_line(self, line_name, salary):
        """Add a per_camp salary line for one auto-vacancy. Idempotent by name.

        Only when the budget already exists (the wizard creates it; for
        legacy events without a budget the engine silently skips — BEP
        recalc happens the moment the budget appears and lines are added).
        """
        self.ensure_one()
        budget = self.camp_budget_ids[:1]
        if not budget:
            return False
        existing = budget.line_ids.filtered(lambda line: line.name == line_name)
        if existing:
            return False
        category = self._get_kadra_budget_category()
        if not category:
            _logger.warning(
                "[camp_staffing] No 'kadra' budget category found — salary line "
                "'%s' for event %s skipped.",
                line_name,
                self.display_name,
            )
            return False
        return self.env["camp.budget.line"].create(
            {
                "budget_id": budget.id,
                "category_id": category.id,
                "name": line_name,
                "per": "per_camp",
                "amount": salary,
            }
        )

    @api.model
    def _get_kadra_budget_category(self):
        """kadra/is_salary category: env.ref first, fallback search by flag/name."""
        category = self.env.ref("fayna_camp_portal.budget_categ_kadra", raise_if_not_found=False)
        if category:
            return category
        category_model = self.env["camp.budget.category"]
        return category_model.search([("is_salary", "=", True)], limit=1) or category_model.search(
            [("name", "ilike", "kadra")], limit=1
        )

    def action_open_staff_vacancies(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Wakaty — %(event)s", event=self.display_name),
            "res_model": "camp.staff.vacancy",
            "view_mode": "tree,kanban,form",
            "domain": [("event_id", "=", self.id)],
            "context": {"default_event_id": self.id},
        }


# ---------------------------------------------------------------------------
# event.registration — the trigger
# ---------------------------------------------------------------------------


class EventRegistrationStaffing(models.Model):
    _inherit = "event.registration"

    @api.model_create_multi
    def create(self, vals_list):
        registrations = super().create(vals_list)
        try:
            registrations.event_id._sync_staff_vacancies()
        except Exception:  # noqa: BLE001 — never block a sale/registration on staffing
            _logger.exception(
                "[camp_staffing] Vacancy sync failed after registration create %s",
                registrations.ids,
            )
        return registrations

    def write(self, vals):
        res = super().write(vals)
        if {"state", "event_id", "participant_id"} & set(vals.keys()):
            try:
                self.event_id._sync_staff_vacancies()
            except Exception:  # noqa: BLE001 — never block a registration write on staffing
                _logger.exception(
                    "[camp_staffing] Vacancy sync failed after registration write %s",
                    self.ids,
                )
        return res
