# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""R10 — compute_sudo consistency guard (module-wide).

Odoo's registry warns when fields sharing one compute method disagree on
``compute_sudo`` (the whole group runs once, so the flag of the triggering
field silently wins for the others). The warning also broke ``odoo shell``
startup ergonomics on the stand. This guard re-implements the registry's
check as a hard assertion for every model this module defines, so a new
field can never re-introduce the drift.
"""

from collections import defaultdict

from odoo.tests.common import TransactionCase, tagged

MODULE = "fayna_camp_portal"


@tagged("post_install", "-at_install", "fayna_camp_portal")
class TestComputeSudoConsistency(TransactionCase):
    def test_compute_groups_consistent(self):
        offenders = []
        for model_name in self.env.registry.models:
            model = self.env[model_name]
            if getattr(type(model), "_module", None) != MODULE:
                continue
            groups = defaultdict(list)
            for field in model._fields.values():
                if field.compute and isinstance(field.compute, str):
                    groups[field.compute].append(field)
            for compute, fields_ in groups.items():
                sudo_values = {f.compute_sudo for f in fields_}
                if len(sudo_values) > 1:
                    offenders.append(
                        f"{model_name}.{compute}: "
                        + ", ".join(f"{f.name}={f.compute_sudo}" for f in fields_)
                    )
        self.assertFalse(
            offenders,
            "Inconsistent compute_sudo inside a compute group "
            "(align the flag or split the method): " + "; ".join(offenders),
        )
