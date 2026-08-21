# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
# Fayna CampScout — odoo.tests.Form onchange coverage (OCA review).
#
# OCA review flags the absence of Form-based onchange tests. These tests drive
# the real UI onchange pipeline (odoo.tests.Form) for the three most
# business-critical onchange methods in the module:
#   - camp.medication.registry._onchange_participant_id
#   - camp.program.activity.line._onchange_activity_template
#   - camp.kuratorium.notification._onchange_event_vacation_form
from odoo.tests.common import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestOnchangeForm(TransactionCase):
    """Form-driven onchange tests for the key UI auto-fill behaviours."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(cls.env.context, tracking_disable=True, no_reset_password=True)
        )
        # medication_name / dosage_frequency are gated by _ART9_GROUPS
        # (group_medical_access, base.group_portal), so they are NOT present in
        # the form view for the default admin user. To drive the medication
        # onchange through odoo.tests.Form we must act as a medic who holds
        # group_medical_officer (which implies group_medical_access).
        group_user = cls.env.ref("base.group_user")
        group_medical = cls.env.ref("fayna_camp_portal.group_medical_officer")
        # The medic also needs the native event registration-desk group so the
        # _onchange_participant_id can read the child's event.registration rows.
        group_event_desk = cls.env.ref("event.group_event_registration_desk")
        cls.user_medic = cls.env["res.users"].create(
            {
                "name": "Test Medic Onchange",
                "login": "test_medic_onchange@campscout.test",
                "email": "test_medic_onchange@campscout.test",
                "groups_id": [(6, 0, [group_medical.id, group_user.id, group_event_desk.id])],
            }
        )
        # NOTE: this Odoo build does not expose Environment.with_user() /
        # with_context(), so we switch user via the classic Environment.__call__
        # (user=..., context=...) form.
        cls.medic_env = cls.env(
            user=cls.user_medic.id,
            context=dict(cls.env.context, tracking_disable=True, no_reset_password=True),
        )
        cls.event = cls.env["event.event"].create(
            {
                "name": "Onchange Camp 2026",
                "date_begin": "2026-07-01 08:00:00",
                "date_end": "2026-07-14 18:00:00",
                "vacation_form": "kolonia",
            }
        )
        # The medication registry record rule scopes a medic to camps where they
        # are on the kadra (event_id.staff_ids.user_id == user.id). Link the medic
        # to this event so the rule lets them create the registry row.
        cls.env["camp.staff"].create(
            {
                "event_id": cls.event.id,
                "name": "Test Medic Onchange",
                "role": "ratownik",
                "user_id": cls.user_medic.id,
                "date_from": "2026-07-01",
                "date_to": "2026-07-14",
            }
        )
        cls.participant = cls.env["camp.participant"].create(
            {
                "partner_id": cls.env["res.partner"].create({"name": "Child"}).id,
                "first_name": "Child",
                "last_name": "Test",
            }
        )
        # Link the participant to the event so the medication onchange can
        # propose this shift from the child's latest registration.
        cls.env["event.registration"].create(
            {
                "event_id": cls.event.id,
                "partner_id": cls.env["res.partner"].create({"name": "Parent"}).id,
                "participant_id": cls.participant.id,
            }
        )

    # --- camp.medication.registry._onchange_participant_id -----------------

    def test_medication_onchange_proposes_event_from_participant(self):
        """Picking a participant with a known registration auto-fills the shift."""
        with Form(self.medic_env["camp.medication.registry"]) as form:
            form.medication_name = "Paracetamol"
            form.participant_id = self.participant
            self.assertEqual(
                form.event_id,
                self.event,
                "onchange should propose the child's latest camp shift",
            )

    def test_medication_onchange_keeps_explicit_event(self):
        """If the medic already chose a shift, the onchange must not override it."""
        other = self.env["event.event"].create(
            {
                "name": "Other Shift",
                "date_begin": "2026-08-01 08:00:00",
                "date_end": "2026-08-14 18:00:00",
            }
        )
        # The medic must be on the kadra of the explicitly chosen event too,
        # otherwise the record rule rule_medication_registry_medical_own_camp
        # blocks create on camp.medication.registry for that event.
        self.env["camp.staff"].create(
            {
                "event_id": other.id,
                "name": "Test Medic Onchange",
                "role": "ratownik",
                "user_id": self.user_medic.id,
                "date_from": "2026-08-01",
                "date_to": "2026-08-14",
            }
        )
        with Form(self.medic_env["camp.medication.registry"]) as form:
            form.medication_name = "Paracetamol"
            form.event_id = other
            form.participant_id = self.participant
            self.assertEqual(
                form.event_id,
                other,
                "an explicitly chosen shift must survive the participant onchange",
            )

    # --- camp.program.activity.line._onchange_activity_template ------------

    def test_activity_line_onchange_fills_title_and_time_to(self):
        """Selecting a template auto-fills the title and the end time."""
        template = self.env["camp.activity.template"].create(
            {
                "name": "Morning warm-up",
                "category": "sport",
                "default_duration_minutes": 45,
            }
        )
        program = self.env["camp.program.structured"].create({"event_id": self.event.id})
        day = self.env["camp.program.day"].create({"program_id": program.id, "date": "2026-07-02"})
        with Form(self.env["camp.program.activity.line"]) as form:
            form.day_id = day
            form.time_from = 9.0
            form.activity_template_id = template
            self.assertEqual(
                form.title,
                "Morning warm-up",
                "onchange should prefill the title from the template",
            )
            # 09:00 + 45 min = 09:45 → 9.75 in hour.minute float.
            self.assertAlmostEqual(
                form.time_to,
                9.75,
                places=2,
                msg="onchange should compute time_to from time_from + duration",
            )

    # --- camp.kuratorium.notification._onchange_event_vacation_form ---------

    def test_kuratorium_onchange_prefills_vacation_form_from_event(self):
        """Selecting an event with a declared MEN form pre-fills the notification."""
        organizer = self.env["res.partner"].create({"name": "QA Organizer"})
        with Form(self.env["camp.kuratorium.notification"]) as form:
            form.organizer_id = organizer
            form.location = "ul. Leśna 12, 00-001 Warszawa"
            form.event_id = self.event
            self.assertEqual(
                form.vacation_form,
                "kolonia",
                "onchange should prefill vacation_form from the event",
            )
