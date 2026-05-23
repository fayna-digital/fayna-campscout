/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ChatWindowService } from "@mail/core/common/chat_window_service";

// Upstream Odoo 17 bug: close() assumes a hidden chat window exists whenever
// maxVisible < total chat windows. That invariant can break (window resize after
// chats already open, restored session, race), making this.hidden[0] undefined
// and crashing on swaped.hidden = false. Fixed by guarding the swap.
// Architecture changed in 18.0 (chatHub model), so no upstream backport.
patch(ChatWindowService.prototype, {
    async close(chatWindow, options = {}) {
        const { escape = false } = options;
        if (!chatWindow.hidden && this.maxVisible < this.store.discuss.chatWindows.length) {
            const swaped = this.hidden[0];
            if (swaped) {
                swaped.hidden = false;
                swaped.folded = false;
            }
        }
        const index = this.store.discuss.chatWindows.findIndex((c) => c.eq(chatWindow));
        if (index > -1) {
            this.store.discuss.chatWindows.splice(index, 1);
        }
        const thread = chatWindow.thread;
        if (thread) {
            thread.state = "closed";
        }
        if (escape && this.store.discuss.chatWindows.length > 0) {
            this.focus(this.store.discuss.chatWindows[index - 1]);
        }
        await this._onClose(chatWindow, options);
        chatWindow.delete();
    },
});
