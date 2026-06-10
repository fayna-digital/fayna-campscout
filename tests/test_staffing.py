# Fayna CampScout — тести автоштату §6 (camp.staff.vacancy + event staffing)
# Registration ↔ participant pattern: той самий, що в tests/test_camp_group.py
# (event.registration з partner_id + participant_id; вік = camp.participant.birth_date).
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged

YOUNG_BIRTH = "2018-09-01"  # age 7 on 2026-07-01 → under-10 bucket (limit 15)
OLDER_BIRTH = "2012-01-01"  # age 14 on 2026-07-01 → default bucket (limit 20)

SALARY_PARAM = "fayna_camp_portal.salary_wychowawca_default"
TEST_SALARY = "2500"


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestStaffing(TransactionCase):
    """§6 R13: required wychowawcy, auto-vacancies, budget lines, overstaffing."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param(SALARY_PARAM, TEST_SALARY)
        cls.parent = cls.env["res.partner"].create(
            {"name": "Staffing Test Parent", "email": "staffing-test@campscout.test"}
        )
        cls.event = cls.env["event.event"].create(
            {
                "name": "Staffing Test Camp 2026",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-14 18:00:00",
            }
        )
        # Budget exists up-front (the wizard normally creates it) so the
        # engine can add 'Wakat wychowawca #N' salary lines.
        cls.event.action_open_budget()
        cls.budget = cls.event.camp_budget_ids[:1]
        cls.Vacancy = cls.env["camp.staff.vacancy"]

    # ------------------------------------------------------------------
    # Helpers (test_camp_group pattern)
    # ------------------------------------------------------------------

    @classmethod
    def _make_registration(cls, idx, birth_date):
        child = cls.env["camp.participant"].create(
            {
                "first_name": f"Child{idx}",
                "last_name": "StaffingTest",
                "birth_date": birth_date,
            }
        )
        return cls.env["event.registration"].create(
            {
                "event_id": cls.event.id,
                "partner_id": cls.parent.id,
                "participant_id": child.id,
                "state": "open",
            }
        )

    @classmethod
    def _make_registrations(cls, count, birth_date, offset=0):
        regs = cls.env["event.registration"]
        for i in range(count):
            regs |= cls._make_registration(offset + i, birth_date)
        return regs

    def _wychowawca_vacancies(self):
        return self.event.staff_vacancy_ids.filtered(lambda v: v.role == "wychowawca")

    def _vacancy_budget_lines(self):
        return self.budget.line_ids.filtered(lambda line: (line.name or "").startswith("Wakat"))

    # ------------------------------------------------------------------
    # Required wychowawcy (проста модель: ceil(<10/15) + ceil(решта/20))
    # ------------------------------------------------------------------

    def test_required_one_for_15_young(self):
        """15 under-10 children → exactly 1 wychowawca required."""
        self._make_registrations(15, YOUNG_BIRTH)
        self.assertEqual(self.event.required_wychowawcy, 1)
        # The engine keeps the pipeline aligned with the need: 1 open vacancy.
        self.assertEqual(len(self._wychowawca_vacancies()), 1)

    def test_required_two_for_17_young(self):
        """17 under-10 children → ceil(17/15) = 2 wychowawcy required."""
        self._make_registrations(17, YOUNG_BIRTH)
        self.assertEqual(self.event.required_wychowawcy, 2)

    def test_mixed_ages_buckets(self):
        """Buckets are independent: 5 young + 20 older → 1 + 1 = 2."""
        self._make_registrations(5, YOUNG_BIRTH)
        self._make_registrations(20, OLDER_BIRTH, offset=100)
        self.assertEqual(self.event.required_wychowawcy, 2)

    # ------------------------------------------------------------------
    # Threshold crossing: 16th registration → new vacancy + budget line
    # ------------------------------------------------------------------

    def test_16th_registration_creates_vacancy_and_budget_line(self):
        self._make_registrations(15, YOUNG_BIRTH)
        self.assertEqual(len(self._wychowawca_vacancies()), 1)
        lines_before = self._vacancy_budget_lines()
        self.assertEqual(len(lines_before), 1)

        self._make_registration(15, YOUNG_BIRTH)  # the 16th child

        self.assertEqual(self.event.required_wychowawcy, 2)
        vacancies = self._wychowawca_vacancies()
        self.assertEqual(len(vacancies), 2)
        self.assertEqual(
            sorted(vacancies.mapped("name")),
            ["Wakat wychowawca #1", "Wakat wychowawca #2"],
        )
        lines = self._vacancy_budget_lines()
        self.assertEqual(len(lines), 2)
        self.assertIn("Wakat wychowawca #2", lines.mapped("name"))
        # R12: the salary comes from the config parameter, per_camp.
        new_line = lines.filtered(lambda line: line.name == "Wakat wychowawca #2")
        self.assertEqual(new_line.per, "per_camp")
        self.assertAlmostEqual(new_line.amount, float(TEST_SALARY))
        self.assertTrue(new_line.category_id.is_salary)

    def test_no_duplicate_vacancies_on_repeated_registrations(self):
        """Registrations within the same required count never duplicate vacancies."""
        regs = self._make_registrations(16, YOUNG_BIRTH)
        self.assertEqual(len(self._wychowawca_vacancies()), 2)

        # 17..20 young: ceil(20/15) is still 2 — no new vacancies.
        self._make_registrations(4, YOUNG_BIRTH, offset=50)
        self.assertEqual(self.event.required_wychowawcy, 2)
        self.assertEqual(len(self._wychowawca_vacancies()), 2)
        self.assertEqual(len(self._vacancy_budget_lines()), 2)

        # Re-writing state (no real change) must not duplicate either.
        regs[0].write({"state": "open"})
        self.assertEqual(len(self._wychowawca_vacancies()), 2)
        self.assertEqual(len(self._vacancy_budget_lines()), 2)

    # ------------------------------------------------------------------
    # Hire: draft camp.staff (RSPTS gate — NOT confirmed)
    # ------------------------------------------------------------------

    def test_hire_creates_draft_staff(self):
        self._make_registrations(15, YOUNG_BIRTH)
        vacancy = self._wychowawca_vacancies()
        self.assertEqual(vacancy.state, "open")

        with self.assertRaises(UserError):
            vacancy.action_hire()  # no candidate_name yet

        vacancy.candidate_name = "Anna Testowa"
        vacancy.action_hire()

        self.assertEqual(vacancy.state, "hired")
        staff = vacancy.staff_id
        self.assertTrue(staff)
        self.assertEqual(staff.name, "Anna Testowa")
        self.assertEqual(staff.state, "draft")  # RSPTS §13: not confirmed
        self.assertEqual(staff.role, "counselor")  # wychowawca → counselor mapping
        self.assertEqual(staff.event_id, self.event)
        # Draft staff does NOT count as current (no KRK/RSPTS verification yet).
        self.assertEqual(self.event.current_wychowawcy, 0)

        with self.assertRaises(UserError):
            vacancy.action_hire()  # already hired

    # ------------------------------------------------------------------
    # R13: cancellations never auto-close hired vacancies — only overstaffed
    # ------------------------------------------------------------------

    def test_cancellation_sets_overstaffed_keeps_hired_vacancies(self):
        regs = self._make_registrations(17, YOUNG_BIRTH)
        vacancies = self._wychowawca_vacancies()
        self.assertEqual(len(vacancies), 2)
        for i, vacancy in enumerate(vacancies):
            vacancy.candidate_name = f"Wychowawca {i}"
            vacancy.action_hire()
        self.assertEqual(set(vacancies.mapped("state")), {"hired"})
        self.assertFalse(self.event.overstaffed)

        # Cancel down to 10 young children → required drops to 1.
        regs[10:].write({"state": "cancel"})

        self.assertEqual(self.event.required_wychowawcy, 1)
        self.assertTrue(self.event.overstaffed)
        # R13: nothing auto-closed — both vacancies still hired, staff intact.
        self.assertEqual(set(vacancies.mapped("state")), {"hired"})
        self.assertEqual(len(vacancies.mapped("staff_id")), 2)
        # And the engine did NOT open new vacancies despite gap math.
        self.assertEqual(len(self._wychowawca_vacancies()), 2)

    def test_overstaffed_false_while_balanced(self):
        self._make_registrations(15, YOUNG_BIRTH)
        self.assertFalse(self.event.overstaffed)
