/** @odoo-module **/
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

/**
 * Patient Journey Bar — the first thing on every chart: where the patient actually is.
 * Renders every stage of the selection as a chevron; done stages filled, current highlighted.
 */
export class JourneyBar extends Component {
    static template = "stratos_hms.JourneyBar";
    static props = { ...standardFieldProps };

    get steps() {
        const field = this.props.record.fields[this.props.name];
        const options = field.selection || [];
        const current = this.props.record.data[this.props.name];
        const idx = options.findIndex(([k]) => k === current);
        return options.map(([key, label], i) => ({
            key,
            label,
            cls: i < idx ? "done" : i === idx ? "current" : "todo",
        }));
    }
}

registry.category("fields").add("hms_journey_bar", {
    component: JourneyBar,
    displayName: _t("Journey bar"),
    supportedTypes: ["selection"],
});
