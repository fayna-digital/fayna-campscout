/** @odoo-module **/

/**
 * KioskBackButton — systray button "← Powrót" (back to fullscreen kiosk).
 *
 * Mirror image of KioskOdooToggle: shown to the kiosk roles
 * (kierownik / wychowawca / instructor) who land in the standard Odoo
 * backend after tapping a tile (a plain window-action is NOT fullscreen,
 * so the navbar reappears). This button returns them to the fullscreen
 * camp_kiosk_action, which hides the navbar / app menu again — a
 * "container return" without route hacks.
 *
 * Visibility is controlled server-side via /camp/kiosk/back_visible
 * (no group membership hardcoded in JS).
 *
 * Pattern: copy of KioskOdooToggle structure.
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class KioskBackButton extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.state = useState({
            visible: false,
        });

        onWillStart(async () => {
            try {
                const res = await this.rpc("/camp/kiosk/back_visible", {});
                this.state.visible = !!(res && res.visible);
            } catch {
                // Best-effort: on any error stay hidden so the navbar is never broken.
                this.state.visible = false;
            }
        });
    }

    async onBack() {
        // Return to the fullscreen kiosk client action → hides navbar/app menu.
        await this.action.doAction("fayna_camp_portal.camp_kiosk_action");
    }
}

KioskBackButton.template = "fayna_camp_portal.KioskBackButton";

// Sequence 6 → appears to the left of KioskOdooToggle (sequence 5).
registry.category("systray").add(
    "camp_kiosk_back",
    { Component: KioskBackButton },
    { sequence: 6 }
);
