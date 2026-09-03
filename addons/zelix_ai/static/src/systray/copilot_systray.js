/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { CopilotSidebar } from "../components/copilot_sidebar/copilot_sidebar";

export class CopilotSystrayItem extends Component {
    static template = "zelix_ai.CopilotSystrayItem";
    static components = { CopilotSidebar };
    static props = {};

    setup() {
        this.copilot = useService("zelix_copilot");
        this.copilotState = useState(this.copilot.state);
    }

    onClick() {
        this.copilot.toggleSidebar();
    }
}

export const systrayItem = {
    Component: CopilotSystrayItem,
    isDisplayed: () => true,
};

registry.category("systray").add("zelix_copilot_systray", systrayItem, { sequence: 10 });
