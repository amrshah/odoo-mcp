/** @odoo-module **/

import {Component, onWillStart, useState} from "@odoo/owl";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";

export class VetCairnDashboard extends Component {
    static template = "vet_dashboard.VetCairnDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({loading: true, data: {metrics: [], charts: [], quick_actions: []}});
        onWillStart(() => this.loadDashboard());
    }

    async loadDashboard() {
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call("vet.dashboard", "get_dashboard_data", []);
        } finally {
            this.state.loading = false;
        }
    }

    openAction(action) {
        return this.action.doAction(action);
    }
}

registry.category("actions").add("vetcairn.dashboard", VetCairnDashboard);
