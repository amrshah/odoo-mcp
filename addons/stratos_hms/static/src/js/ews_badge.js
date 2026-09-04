/** @odoo-module **/
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

/** Early Warning Score pill: 0-2 green, 3-4 amber, 5-6 orange, 7+ red. */
export class EwsBadge extends Component {
    static template = "stratos_hms.EwsBadge";
    static props = { ...standardFieldProps };

    get score() {
        const v = this.props.record.data[this.props.name];
        return typeof v === "number" ? v : 0;
    }
    get level() {
        const s = this.score;
        return s >= 7 ? "high" : s >= 5 ? "medium" : s >= 3 ? "lowmed" : "low";
    }
    get title() {
        return { high: _t("EWS high — urgent review"), medium: _t("EWS medium — see soon"), lowmed: _t("EWS low-medium"), low: _t("EWS low") }[this.level];
    }
}

registry.category("fields").add("hms_ews_badge", {
    component: EwsBadge,
    displayName: _t("EWS badge"),
    supportedTypes: ["integer"],
});
