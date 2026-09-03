/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ActionCard extends Component {
    static template = "zelix_ai.ActionCard";
    static props = {
        card: Object,
    };

    setup() {
        this.copilot = useService("zelix_copilot");
    }

    async onApprove() {
        await this.copilot.approveAction(this.props.card.action_id);
    }

    async onReject() {
        await this.copilot.rejectAction(this.props.card.action_id);
    }
}
