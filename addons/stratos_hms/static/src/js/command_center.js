/** @odoo-module **/
/*
 * Command Centre — the whole hospital, live, for the director.
 * Same data the front line writes, not a report compiled at month end.
 */
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";
import { Component, onWillStart, onMounted, onWillUnmount, useState, useRef } from "@odoo/owl";

const PALETTE = ["#4f46e5", "#0f9d7a", "#f59e0b", "#dc2626", "#0ea5e9", "#a855f7", "#64748b", "#14b8a6"];

export class CommandCenter extends Component {
    static template = "stratos_hms.CommandCenter";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ data: null, loading: true, error: null });
        this.revenueRef = useRef("revenueChart");
        this.mixRef = useRef("mixChart");
        this.flowRef = useRef("flowChart");
        this.bedsRef = useRef("bedsChart");
        this.charts = [];
        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.load();
        });
        onMounted(() => this.renderCharts());
        onWillUnmount(() => this.destroyCharts());
        this.timer = setInterval(() => this.refresh(), 60000);
        onWillUnmount(() => clearInterval(this.timer));
    }

    async load() {
        try {
            this.state.data = await this.orm.call("hms.dashboard", "get_command_center", []);
            this.state.error = null;
        } catch (e) {
            this.state.error = e.message || String(e);
        }
        this.state.loading = false;
    }

    async refresh() {
        await this.load();
        this.destroyCharts();
        this.renderCharts();
    }

    destroyCharts() {
        for (const c of this.charts) {
            try {
                c.destroy();
            } catch (e) {
                /* ignore */
            }
        }
        this.charts = [];
    }

    money(v) {
        const cur = (this.state.data && this.state.data.currency) || "PKR";
        return `${cur} ${Math.round(v || 0).toLocaleString()}`;
    }

    renderCharts() {
        const d = this.state.data;
        if (!d || !window.Chart) return;
        const Chart = window.Chart;
        const base = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } };
        if (this.revenueRef.el) {
            this.charts.push(new Chart(this.revenueRef.el, {
                type: "bar",
                data: {
                    labels: d.revenue_days.map((x) => x.day),
                    datasets: [
                        { label: "Billed", data: d.revenue_days.map((x) => x.billed), backgroundColor: "#c7d2fe", borderRadius: 4 },
                        { label: "Collected", data: d.revenue_days.map((x) => x.collected), backgroundColor: "#4f46e5", borderRadius: 4 },
                    ],
                },
                options: { ...base, plugins: { legend: { display: true, position: "bottom" } }, scales: { x: { grid: { display: false } }, y: { grid: { color: "#eef0f6" } } } },
            }));
        }
        if (this.mixRef.el) {
            this.charts.push(new Chart(this.mixRef.el, {
                type: "doughnut",
                data: { labels: d.revenue_mix.map((x) => x.label), datasets: [{ data: d.revenue_mix.map((x) => x.amount), backgroundColor: PALETTE, borderWidth: 0 }] },
                options: { ...base, cutout: "68%", plugins: { legend: { display: true, position: "right" } } },
            }));
        }
        if (this.flowRef.el) {
            this.charts.push(new Chart(this.flowRef.el, {
                type: "bar",
                data: { labels: d.flow.map((x) => x.stage), datasets: [{ data: d.flow.map((x) => x.count), backgroundColor: PALETTE, borderRadius: 4 }] },
                options: { ...base, indexAxis: "y", scales: { x: { grid: { color: "#eef0f6" }, ticks: { precision: 0 } }, y: { grid: { display: false } } } },
            }));
        }
        if (this.bedsRef.el) {
            this.charts.push(new Chart(this.bedsRef.el, {
                type: "bar",
                data: {
                    labels: d.beds.map((x) => x.ward),
                    datasets: [
                        { label: "Occupied", data: d.beds.map((x) => x.occupied), backgroundColor: "#dc2626", borderRadius: 4 },
                        { label: "Free", data: d.beds.map((x) => x.total - x.occupied), backgroundColor: "#0f9d7a", borderRadius: 4 },
                    ],
                },
                options: { ...base, plugins: { legend: { display: true, position: "bottom" } }, scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, ticks: { precision: 0 }, grid: { color: "#eef0f6" } } } },
            }));
        }
    }

    open(action, extra = {}) {
        this.action.doAction({ type: "ir.actions.act_window", res_model: action.model, name: action.name, view_mode: "list,form", views: [[false, "list"], [false, "form"]], domain: action.domain || [], context: action.context || {}, ...extra });
    }

    openVisit(id) {
        this.action.doAction({ type: "ir.actions.act_window", res_model: "hms.visit", res_id: id, views: [[false, "form"]], target: "current" });
    }

    get tiles() {
        const k = this.state.data.kpis;
        return [
            { label: "Patients today", value: k.patients_today, icon: "fa-users", tone: "indigo", click: { model: "hms.visit", name: "Today", domain: [["arrival_time", ">=", new Date().toISOString().slice(0, 10)]] } },
            { label: "In the building", value: k.in_building, icon: "fa-hospital-o", tone: "indigo", click: { model: "hms.visit", name: "Open visits", domain: [["state", "=", "open"]] } },
            { label: "EWS ≥ 5", value: k.ews_high, icon: "fa-heartbeat", tone: k.ews_high ? "red" : "teal", click: { model: "hms.visit", name: "Sickest", domain: [["state", "=", "open"], ["ews_score", ">=", 5]] } },
            { label: "Bed occupancy", value: k.bed_occupancy + "%", sub: k.beds_free + " free", icon: "fa-bed", tone: k.bed_occupancy > 85 ? "amber" : "teal", click: { model: "hms.bed", name: "Beds" } },
            { label: "Held files", value: k.held, icon: "fa-lock", tone: k.held ? "amber" : "teal", click: { model: "hms.visit", name: "Held", domain: [["held", "=", true]] } },
            { label: "Approvals pending", value: k.approvals, icon: "fa-percent", tone: k.approvals ? "amber" : "teal", click: { model: "hms.discount.request", name: "Approvals", domain: [["state", "=", "submitted"]] } },
            { label: "Lab worklist", value: k.lab_open, sub: "avg TAT " + k.lab_tat + " min", icon: "fa-flask", tone: "indigo", click: { model: "hms.order", name: "Worklist", domain: [["state", "in", ["ordered", "collected", "resulted"]]] } },
            { label: "Critical calls due", value: k.critical_pending, icon: "fa-phone", tone: k.critical_pending ? "red" : "teal", click: { model: "hms.critical.call", name: "Critical calls", domain: [["state", "=", "pending"]] } },
            { label: "Results unacknowledged", value: k.unacked_results, icon: "fa-inbox", tone: k.unacked_results ? "amber" : "teal", click: { model: "hms.order", name: "To acknowledge", domain: [["state", "=", "verified"]] } },
            { label: "Pharmacy queue", value: k.pharmacy_queue, icon: "fa-medkit", tone: "indigo", click: { model: "hms.dispense", name: "Pharmacy", domain: [["state", "in", ["to_verify", "verified"]]] } },
            { label: "Theatre today", value: k.theatre_today, icon: "fa-user-md", tone: "indigo", click: { model: "hms.surgery", name: "Theatre" } },
            { label: "Handoffs open", value: k.handoffs_open, icon: "fa-exchange", tone: k.handoffs_open ? "amber" : "teal", click: { model: "hms.handoff", name: "Handoffs", domain: [["state", "=", "sent"]] } },
        ];
    }
}

registry.category("actions").add("hms_command_center", CommandCenter);
