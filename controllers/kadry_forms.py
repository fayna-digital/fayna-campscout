# Copyright Fayna Digital — Volodymyr Shevchenko
# License OPL-1 (Odoo Proprietary License v1.0) — see LICENSE for full terms.
"""Публічні статичні форми кадри/батьків (перенесено з окремого репо
kadry-forms/GitHub Pages на staging.campscout.eu — той самий домен, що й
POST /camp/submit-document, тому CORS більше не потрібен).

Файли — самодостатній HTML+JS (pdfMake генерує PDF у браузері), лежать у
static/src/kadry/. Контролер лише віддає їх під чистим URL, без QWeb.
"""

from odoo import http
from odoo.http import request
from odoo.modules.module import get_module_resource


class KadryFormsController(http.Controller):
    def _serve_html(self, filename):
        path = get_module_resource("fayna_camp_portal", "static", "src", "kadry", filename)
        with open(path, "rb") as f:
            content = f.read()
        return request.make_response(
            content, headers=[("Content-Type", "text/html; charset=utf-8")]
        )

    @http.route(
        ["/camp/kadry/campscout"], type="http", auth="public", website=False, methods=["GET"]
    )
    def kadry_campscout(self, **kw):
        """Анкета кадри (instruktor PL / wolontariusz UA) — без підпису, лише PDF+фіксація подання."""
        return self._serve_html("campscout.html")

    @http.route(["/camp/kadry/rodzice"], type="http", auth="public", website=False, methods=["GET"])
    def kadry_rodzice(self, **kw):
        """Згоди батьків (Dodatek 4a wizerunek + 4b marketing) — canvas-підпис."""
        return self._serve_html("rodzice.html")
