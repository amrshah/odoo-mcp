from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError


class VetDashboard(models.Model):
    _name = "vet.dashboard"
    _description = "VetCairn Operational Dashboard"

    name = fields.Char(default="VetCairn Dashboard")

    @api.model
    def get_dashboard_data(self):
        today = fields.Date.context_today(self)
        now = fields.Datetime.now()
        tomorrow = today + timedelta(days=1)
        next_month = today + timedelta(days=30)

        def count(model_name, domain):
            model = self.env[model_name]
            try:
                model.check_access("read")
                return model.search_count(domain)
            except AccessError:
                return None

        metrics = [
            self._metric("Appointments Today", count("vet.appointment", [("start_datetime", ">=", fields.Datetime.to_datetime(today)), ("start_datetime", "<", fields.Datetime.to_datetime(tomorrow)), ("state", "not in", ("cancelled", "no_show"))]), "fa-calendar", "primary", "vet_appointment.action_vet_appointment_today"),
            self._metric("Waiting / In Consultation", count("vet.encounter", [("state", "in", ("draft", "in_progress"))]), "fa-stethoscope", "info", "vet_clinical.action_vet_encounter_census"),
            self._metric("Overdue Treatments", count("vet.treatment.line", [("state", "in", ("planned", "in_progress")), ("due_datetime", "<", now)]), "fa-heartbeat", "danger", "vet_treatment.action_vet_treatment_board"),
            self._metric("Vaccinations Due", count("vet.vaccination", [("state", "=", "planned"), ("planned_date", "<=", next_month)]), "fa-medkit", "warning", "vet_vaccination.action_vet_vaccination"),
            self._metric("Open Diagnostics", count("vet.diagnostic.order", [("state", "in", ("draft", "ordered", "collected", "in_progress"))]), "fa-flask", "info", "vet_diagnostic.action_vet_diagnostic_order"),
            self._metric("Pending Prescriptions", count("vet.prescription", [("state", "in", ("draft", "pending", "approved"))]), "fa-file-text-o", "warning", "vet_prescription.action_vet_prescription"),
            self._metric("Ready Billing Charges", count("vet.charge", [("state", "=", "ready")]), "fa-money", "success", "vet_billing.action_vet_charge"),
            self._metric("Overdue Reminders", count("vet.reminder", [("state", "=", "pending"), ("due_date", "<", today)]), "fa-bell", "danger", "vet_reminder.action_vet_reminder"),
            self._metric("Expiring Documents", count("vet.patient.document", [("state", "in", ("current", "signed")), ("expiry_date", ">=", today), ("expiry_date", "<=", next_month)]), "fa-folder-open", "warning", "vet_documents.action_vet_patient_document"),
            self._metric("Pending Estimates", count("sale.order", [("is_vet_estimate", "=", True), ("vet_approval_state", "=", "pending"), ("state", "in", ("draft", "sent"))]), "fa-calculator", "primary", "vet_commercial.action_vet_estimate"),
            self._metric("Controlled Purchases", count("purchase.order", [("is_vet_purchase", "=", True), ("vet_review_state", "=", "pending")]), "fa-shopping-cart", "danger", "vet_procurement.action_vet_purchase_order"),
            self._metric("Active Patients", count("vet.patient", [("status", "=", "active")]), "fa-paw", "success", "vet_base.action_vet_patient"),
        ]

        appointment_chart = self._selection_chart("vet.appointment", "state", [])
        patient_chart = self._many2one_chart("vet.patient", "species_id", [("status", "=", "active")])
        clinical_chart = self._selection_chart("vet.encounter", "triage_priority", [("state", "in", ("draft", "in_progress"))])

        return {
            "metrics": [metric for metric in metrics if metric["value"] is not None],
            "charts": [
                {"title": "Appointments by Status", "items": appointment_chart, "action": "vet_reporting.action_vet_report_appointments"},
                {"title": "Active Patients by Species", "items": patient_chart, "action": "vet_base.action_vet_patient"},
                {"title": "Open Clinical Priority", "items": clinical_chart, "action": "vet_reporting.action_vet_report_clinical"},
            ],
            "generated_at": fields.Datetime.to_string(now),
            "company": self.env.company.display_name,
            "user": self.env.user.display_name,
            "quick_actions": [
                {"label": "Schedule", "icon": "fa-calendar", "action": "vet_appointment.action_vet_appointment_today"},
                {"label": "Patients", "icon": "fa-paw", "action": "vet_base.action_vet_patient"},
                {"label": "Clinical Census", "icon": "fa-stethoscope", "action": "vet_clinical.action_vet_encounter_census"},
                {"label": "Treatment Board", "icon": "fa-heartbeat", "action": "vet_treatment.action_vet_treatment_board"},
                {"label": "Vaccinations", "icon": "fa-medkit", "action": "vet_vaccination.action_vet_vaccination"},
                {"label": "Diagnostics", "icon": "fa-flask", "action": "vet_diagnostic.action_vet_diagnostic_order"},
                {"label": "Prescriptions", "icon": "fa-file-text-o", "action": "vet_prescription.action_vet_prescription"},
                {"label": "Billing", "icon": "fa-money", "action": "vet_billing.action_vet_charge"},
                {"label": "Reminders", "icon": "fa-bell", "action": "vet_reminder.action_vet_reminder"},
                {"label": "Documents", "icon": "fa-folder-open", "action": "vet_documents.action_vet_patient_document"},
                {"label": "Reports", "icon": "fa-bar-chart", "action": "vet_reporting.action_vet_report_appointments"},
                {"label": "Purchasing", "icon": "fa-shopping-cart", "action": "vet_procurement.action_vet_purchase_order"},
            ],
        }

    @api.model
    def _metric(self, label, value, icon, color, action):
        return {"label": label, "value": value, "icon": icon, "color": color, "action": action}

    @api.model
    def _selection_chart(self, model_name, field_name, domain):
        model = self.env[model_name]
        try:
            model.check_access("read")
            rows = model._read_group(domain, [field_name], ["__count"])
        except AccessError:
            return []
        labels = dict(model._fields[field_name].selection)
        return self._chart_items([(labels.get(value, value or "Unspecified"), count) for value, count in rows])

    @api.model
    def _many2one_chart(self, model_name, field_name, domain):
        model = self.env[model_name]
        try:
            model.check_access("read")
            rows = model._read_group(domain, [field_name], ["__count"])
        except AccessError:
            return []
        return self._chart_items([((record.display_name if record else "Unspecified"), count) for record, count in rows])

    @api.model
    def _chart_items(self, rows):
        maximum = max((count for _label, count in rows), default=0)
        return [{"label": label, "value": count, "percent": round(count * 100 / maximum) if maximum else 0} for label, count in rows]
