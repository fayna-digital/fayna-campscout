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
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { session } from "@web/session";

export class CampKiosk extends Component {
    setup() {
        this.rpc = useService("rpc");
        this.action = useService("action");
        // Current UI language (e.g. "pl_PL" / "uk_UA") — drives the active
        // state of the PL/UA switcher in the header. Does not change without a
        // reload, so a plain property (not reactive state) is enough.
        this.lang = session.user_context.lang;
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
     * Header/spinner labels (R2 — bilingual PL/UA).
     *
     * Static text placed directly in an OWL .xml template is NOT picked up by
     * Odoo's translation export (the JS term extractor scans .js for `_t(...)`
     * calls, not template text nodes), so it can never be translated. Routing
     * these strings through `_t()` in JS getters is the Odoo-native fix: the
     * literals land in the .pot, and because a getter is evaluated on every
     * render, `_t()` resolves against the translation bundle of the language
     * currently loaded in the page. setLang() does a full reload on switch, so
     * the new bundle is loaded and the getter returns the translated term.
     * The template binds these via `t-esc` (see kiosk_template.xml).
     */
    get headerTitle() {
        return _t("Portal CampScout");
    }

    get headerSubtitle() {
        return _t("Wybierz działanie");
    }

    get loadingText() {
        return _t("Завантаження...");
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
                this.state.error = _t("Немає дозволених дій для вашої ролі.");
            }
        } catch (err) {
            console.error("[CampKiosk] layout load error:", err);
            this.state.error = _t("Помилка завантаження кіоска. Зверніться до організатора.");
        } finally {
            this.state.isLoading = false;
        }
    }

    /**
     * Switch the UI language (PL/UA header switcher, R2).
     * Persists res.users.lang via /camp/kiosk/set_lang, then does a full
     * page reload so the whole client-action (and all lazy-translated tiles)
     * re-render in the chosen language. No-op if the language is unchanged.
     */
    async setLang(lang) {
        if (!lang || lang === this.lang) {
            return;
        }
        try {
            const result = await this.rpc("/camp/kiosk/set_lang", { lang });
            if (result && result.ok) {
                browser.location.reload();
            } else {
                this.state.error =
                    (result && result.error) ||
                    _t("Nie udało się zmienić języka.");
            }
        } catch (err) {
            console.error("[CampKiosk] set_lang error:", lang, err);
            this.state.error = _t("Nie udało się zmienić języka.");
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
