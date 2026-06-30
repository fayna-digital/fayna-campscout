/** @odoo-module **/

/**
 * KioskOdooToggle — systray button "↔ Odoo" (TZ §4 toggle).
 *
 * Visible only to users with base.group_system OR group_camp_organizator
 * (kierownik in kiosk mode does NOT see it — they stay in the kiosk).
 *
 * Visibility is controlled server-side: the component checks /camp/kiosk/toggle_visible.
 * This avoids hardcoding group membership in JS and keeps logic consistent
 * with the server groups.xml.
 *
 * Click: exits fullscreen client action and navigates to the standard
 * Odoo home action (web#action=home) — the user lands on the normal app grid.
 * The kiosk is still accessible via the "Kiosk" menu entry.
 *
 * Pattern: reuses ImpersonationSystray structure (sequence, rpc, onWillStart).
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class KioskOdooToggle extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.state = useState({
            visible: false,
        });

        onWillStart(async () => {
            try {
                const res = await this.rpc("/camp/kiosk/toggle_visible", {});
                this.state.visible = !!(res && res.visible);
            } catch {
                // Best-effort: on any error stay hidden so the navbar is never broken.
                this.state.visible = false;
            }
        });
    }

    async onToggle() {
        // Navigate to the standard Odoo home — leaves kiosk fullscreen.
        await this.action.doAction("action_menu_default_home");
    }
}

KioskOdooToggle.template = "fayna_camp_portal.KioskOdooToggle";

// Sequence 5 → appears to the left of ImpersonationSystray (sequence 1).
registry.category("systray").add(
    "camp_kiosk_odoo_toggle",
    { Component: KioskOdooToggle },
    { sequence: 5 }
);
