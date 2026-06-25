/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Systray indicator shown only when the current backend session is in
 * impersonation mode (Organizator logged in as another user via
 * /admin/login-as). Loud red banner with a one-click "повернутися" that
 * routes to /admin/stop-impersonation (server restores the original uid
 * and RODO-logs the stop).
 *
 * Odoo 17: the rpc service is obtained via useService("rpc"); the standalone
 * "@web/core/network/rpc" export only exists from Odoo 18 onward.
 */
export class ImpersonationSystray extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            impersonating: false,
            adminName: "",
            currentName: "",
        });

        onWillStart(async () => {
            try {
                const res = await this.rpc("/admin/impersonation-status", {});
                if (res && res.impersonating) {
                    this.state.impersonating = true;
                    this.state.adminName = res.admin_name || "";
                    this.state.currentName = res.current_name || "";
                }
            } catch {
                // Status route is best-effort; on any error stay hidden so we
                // never break the navbar for normal users.
                this.state.impersonating = false;
            }
        });
    }

    onStop() {
        window.location = "/admin/stop-impersonation";
    }
}

ImpersonationSystray.template = "fayna_camp_portal.ImpersonationSystray";

// Sequence 1 → appears far to the right (low number = right side), making the
// alert hard to miss.
registry.category("systray").add(
    "fayna_impersonation",
    { Component: ImpersonationSystray },
    { sequence: 1 }
);
