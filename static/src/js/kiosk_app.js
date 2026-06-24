/** @odoo-module **/

/**
 * CampKiosk — OWL root component for the kiosk shell (TZ §4).
 *
 * Odoo 17 fullscreen client action registered under tag "camp_kiosk".
 * On mount, calls /camp/kiosk/layout (JSON-RPC) to get the per-role
 * button grid. Each tile fires this.action.doAction() with the xmlid
 * or tag returned from the server — no role logic in JS.
 *
 * Toggle "↔ Odoo" is rendered by a separate systray component
 * (kiosk_odoo_toggle_systray.js) visible only to group_system /
 * group_camp_organizator; this component does NOT include it.
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class CampKiosk extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        this.state = useState({
            tiles: [],
            isLoading: true,
            error: null,
        });

        onWillStart(async () => {
            await this._loadLayout();
        });
    }

    /**
     * Fetch the per-role tile grid from the server.
     * Response: [{label, icon, action, description?}, ...]
     * action is either an xmlid string ("fayna_camp_portal.action_camp_staff")
     * or an action tag ("camp.staff.tree") — doAction handles both.
     */
    async _loadLayout() {
        try {
            const result = await this.rpc("/camp/kiosk/layout", {});
            if (result && result.tiles) {
                this.state.tiles = result.tiles;
            } else {
                this.state.error = "Немає дозволених дій для вашої ролі.";
            }
        } catch (err) {
            console.error("[CampKiosk] layout load error:", err);
            this.state.error = "Помилка завантаження кіоска. Зверніться до організатора.";
        } finally {
            this.state.isLoading = false;
        }
    }

    /**
     * Fire an Odoo action by xmlid or tag.
     * doAction accepts both string xmlids and action descriptor objects.
     */
    async onTileClick(tile) {
        if (!tile.action) {
            return;
        }
        try {
            await this.action.doAction(tile.action);
        } catch (err) {
            console.error("[CampKiosk] action error:", tile.action, err);
        }
    }
}

CampKiosk.template = "fayna_camp_portal.CampKiosk";

// Register under the tag declared in ir.actions.client.tag
registry.category("actions").add("camp_kiosk", CampKiosk);
