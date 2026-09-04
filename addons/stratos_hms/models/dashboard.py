from collections import Counter
from datetime import timedelta

from odoo import api, fields, models


class HmsDashboard(models.AbstractModel):
    """Data for the Command Centre. Everything here is the same live data the front line writes —
    not a report anyone compiles at month end."""
    _name = "hms.dashboard"
    _description = "HMS Command Centre data"

    @api.model
    def get_command_center(self):
        Visit = self.env["hms.visit"]
        Order = self.env["hms.order"]
        Move = self.env["account.move"].sudo()
        Bed = self.env["hms.bed"]
        now = fields.Datetime.now()
        today_start = fields.Datetime.to_datetime(fields.Date.today())
        open_visits = Visit.search([("state", "=", "open")])
        today_visits = Visit.search([("arrival_time", ">=", today_start)])
        stage_labels = dict(Visit._fields["stage"].selection)
        by_stage = Counter(open_visits.mapped("stage"))
        # revenue last 14 days
        days = []
        for i in range(13, -1, -1):
            d = fields.Date.today() - timedelta(days=i)
            moves = Move.search([("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("invoice_date", "=", d), ("hms_visit_id", "!=", False)])
            days.append({"day": d.strftime("%d %b"), "billed": sum(moves.mapped("amount_total")), "collected": sum(moves.mapped("amount_total")) - sum(moves.mapped("amount_residual"))})
        month_start = fields.Date.today().replace(day=1)
        month_moves = Move.search([("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("invoice_date", ">=", month_start), ("hms_visit_id", "!=", False)])
        mix = Counter()
        for m in month_moves:
            for l in m.invoice_line_ids:
                charge = self.env["hms.charge"].search([("invoice_line_id", "=", l.id)], limit=1)
                mix[dict(self.env["hms.charge"]._fields["source"].selection).get(charge.source, "Other") if charge else "Other"] += l.price_subtotal
        beds = Bed.search([])
        occupied = beds.filtered(lambda b: b.state == "occupied")
        lab_open = Order.search([("state", "in", ("ordered", "collected", "resulted")), ("category", "=", "lab")])
        lab_done_today = Order.search([("verified_at", ">=", today_start)])
        avg_tat = int(sum(lab_done_today.mapped("tat_minutes")) / len(lab_done_today)) if lab_done_today else 0
        critical_pending = Order.search_count([("critical_pending", "=", True)])
        unacked = Order.search_count([("state", "=", "verified")])
        approvals = self.env["hms.discount.request"].search_count([("state", "=", "submitted")])
        held = len(open_visits.filtered("held"))
        # clinician load
        load = Counter()
        for v in open_visits.filtered(lambda v: v.doctor_id):
            load[v.doctor_id.display_name] += 1
        # top diagnoses this month
        dx = Counter()
        for c in self.env["hms.consult"].search([("state", "=", "signed"), ("signed_at", ">=", fields.Datetime.to_datetime(month_start))]):
            for d in c.diagnosis_ids.filtered("confirmed"):
                dx[d.name] += 1
        ews_high = open_visits.filtered(lambda v: v.ews_score >= 5)
        theatre = self.env["hms.surgery"].search([("scheduled_at", ">=", today_start)])
        pharmacy_queue = self.env["hms.dispense"].search_count([("state", "in", ("to_verify", "verified"))])
        handoffs_open = self.env["hms.handoff"].search_count([("state", "=", "sent")])
        return {
            "generated_at": now.strftime("%d %b %Y %H:%M"),
            "kpis": {
                "patients_today": len(today_visits),
                "in_building": len(open_visits.filtered(lambda v: v.stage != "discharged")),
                "held": held,
                "approvals": approvals,
                "ews_high": len(ews_high),
                "bed_occupancy": round(len(occupied) / len(beds) * 100) if beds else 0,
                "beds_free": len(beds.filtered(lambda b: b.state == "free")),
                "lab_open": len(lab_open),
                "lab_tat": avg_tat,
                "critical_pending": critical_pending,
                "unacked_results": unacked,
                "billed_month": sum(month_moves.mapped("amount_total")),
                "collected_month": sum(month_moves.mapped("amount_total")) - sum(month_moves.mapped("amount_residual")),
                "outstanding": sum(month_moves.mapped("amount_residual")),
                "pharmacy_queue": pharmacy_queue,
                "theatre_today": len(theatre),
                "handoffs_open": handoffs_open,
                "no_show_rate": 0,
            },
            "flow": [{"stage": stage_labels[k], "count": by_stage.get(k, 0)} for k, _ in Visit._fields["stage"].selection],
            "revenue_days": days,
            "revenue_mix": [{"label": k, "amount": v} for k, v in mix.most_common()],
            "clinician_load": [{"doctor": d, "count": n} for d, n in load.most_common(8)],
            "top_dx": [{"name": d, "count": n} for d, n in dx.most_common(6)],
            "sickest": [{"id": v.id, "name": v.patient_id.name, "ews": v.ews_score, "complaint": v.complaint, "doctor": v.doctor_id.display_name or "", "stage": stage_labels[v.stage]} for v in ews_high.sorted(lambda v: -v.ews_score)[:6]],
            "beds": [{"ward": w.name, "total": w.bed_count, "occupied": w.occupied_count} for w in self.env["hms.ward"].search([])],
            "currency": self.env.company.currency_id.symbol or "PKR",
        }

    @api.model
    def get_my_workspace(self):
        """Role-aware landing data: what the logged-in person needs first."""
        me = self.env["hms.practitioner"].get_current()
        role = me.role if me else "receptionist"
        Visit = self.env["hms.visit"]
        data = {"role": role, "name": me.display_name if me else self.env.user.name}
        if role in ("doctor", "hod"):
            q = Visit.search([("state", "=", "open"), ("doctor_id", "=", me.id), ("stage", "in", ("triaged", "consult", "registered"))])
            data["queue"] = [{"id": v.id, "patient": v.patient_id.name, "ews": v.ews_score, "complaint": v.complaint, "wait": v.waiting_minutes, "held": v.held} for v in q]
            data["results"] = self.env["hms.order"].search_count([("state", "=", "verified"), ("doctor_id", "=", me.id)])
            data["inpatients"] = self.env["hms.admission"].search_count([("state", "=", "admitted"), ("doctor_id", "=", me.id)])
        return data
