/** @odoo-module **/

/**
 * CampKioskTour — @odoo/tour smoke test for the kiosk shell (TZ §4).
 *
 * OCA review flags the absence of JS UI tours. This tour drives the real
 * kiosk client action (OWL root "camp_kiosk") through the browser:
 *   1. opens the kiosk action,
 *   2. waits for the header ("Portal CampScout") to render,
 *   3. waits for the tile grid to load from /camp/kiosk/layout,
 *   4. asserts the PL/UA language switcher is present.
 *
 * The tour is registered under the module tag so it only runs when the
 * module's own test suite is executed (see tests/test_ui.py).
 */

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

registry.category("web_tours").add("fayna_camp_portal.kiosk_tour", {
    url: "/web#action=fayna_camp_portal.camp_kiosk_action",
    steps: () => [
        {
            trigger: ".o_camp_kiosk_header h1",
            content: _t("The kiosk shell header must render its title."),
            run: () => {},
        },
        {
            trigger: ".o_camp_kiosk_grid .o_camp_kiosk_tile",
            content: _t("The kiosk tile grid must load at least one action tile."),
            run: () => {},
        },
        {
            trigger: ".o_camp_kiosk_langbar button",
            content: _t("The PL/UA language switcher must be present in the header."),
            run: () => {},
        },
    ],
});
