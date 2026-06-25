# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
from . import controllers, models, wizards
from .hooks import post_init_hook

__all__ = ["post_init_hook"]
