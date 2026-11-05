/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const RFP_CONTEXT = { default_is_international_rfp: true, default_type: "opportunity" };

export class RfpDashboard extends Component {
    static template = "stratos_crm_rfp.RfpDashboard";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, loading: true });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("crm.lead", "get_rfp_dashboard_data", []);
        this.state.loading = false;
    }

    listViews() {
        return [
            [this.state.data.list_view_id, "list"],
            [false, "kanban"],
            [false, "form"],
        ];
    }

    openList(name, domain) {
        return this.action.doAction(
            {
                type: "ir.actions.act_window",
                name,
                res_model: "crm.lead",
                views: this.listViews(),
                domain,
                context: RFP_CONTEXT,
            },
            { onClose: () => this.load() }
        );
    }

    openKpi(kpi) {
        return this.openList(kpi.label, kpi.domain);
    }

    openLead(id) {
        return this.action.doAction(
            {
                type: "ir.actions.act_window",
                res_model: "crm.lead",
                res_id: id,
                views: [[false, "form"]],
            },
            { onClose: () => this.load() }
        );
    }

    openWorkload(row) {
        const domain = [
            ["is_international_rfp", "=", true],
            ["rfp_status", "=", "not_submitted"],
            "|",
            ["rfp_proposal_user_id", "=", row.user_id],
            ["rfp_questionnaire_user_id", "=", row.user_id],
        ];
        return this.openList(_t("Open RFPs: %s", row.name), domain);
    }

    newRfp() {
        return this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: _t("New International RFP"),
                res_model: "crm.lead",
                views: [[false, "form"]],
                context: RFP_CONTEXT,
            },
            { onClose: () => this.load() }
        );
    }

    daysClass(days) {
        if (days === null || days === undefined) {
            return "text-bg-secondary";
        }
        if (days < 0) {
            return "text-bg-danger";
        }
        if (days <= 7) {
            return "text-bg-warning";
        }
        return "text-bg-success";
    }

    daysLabel(days) {
        if (days === null || days === undefined) {
            return "-";
        }
        if (days < 0) {
            return _t("%s day(s) overdue", -days);
        }
        if (days === 0) {
            return _t("Today");
        }
        return _t("in %s day(s)", days);
    }
}

registry.category("actions").add("stratos_crm_rfp.dashboard", RfpDashboard);
