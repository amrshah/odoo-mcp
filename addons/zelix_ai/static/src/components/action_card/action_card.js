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
        this.action = useService("action");
    }

    async onApprove() {
        await this.copilot.approveAction(this.props.card.action_id);
    }

    async onReject() {
        await this.copilot.rejectAction(this.props.card.action_id);
    }

    onRequestChanges() {
        this.copilot.sendMessage(`Please adjust the proposal for ${this.props.card.title}: specify alternate dosage or duration.`);
    }

    onViewInOdoo() {
        const model = this.props.card.target_model;
        const resId = this.props.card.record_id || this.props.card.result?.record_id;
        if (model && resId) {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: model,
                res_id: resId,
                views: [[false, "form"]],
                target: "current",
            });
        }
    }
}
