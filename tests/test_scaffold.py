# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
from odoo.tests.common import TransactionCase


class TestScaffold(TransactionCase):
    """Prove the module installs cleanly.

    The feature-flag test was removed: fayna_camp_portal is the portal module
    and is always active once installed — there is no inert mode. Real
    behaviour tests live in test_campscout.py.
    """

    def test_module_installed(self):
        mod = self.env["ir.module.module"].search([("name", "=", "fayna_camp_portal")], limit=1)
        self.assertTrue(mod.exists())
        self.assertIn(mod.state, ("installed", "to upgrade"))
