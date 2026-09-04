"""
Practice Operations & Clinical Data Query Workflow (W00)
Handles administrative, operational, census, and general database inquiries:
- Live Physical Pharmacy Inventory & Stock on Hand (product.product)
- Low Stock / Reorder Threshold Alerts
- Exact patient counts and patient lists (vet.patient)
- Appointment schedules, statuses, and provider assignments (vet.appointment)
- Active clinical encounters (vet.encounter)
- Clinical Prescription Formulary (vet.medication)
- Staff and user listings (res.users)
- Operational executive briefings grounded strictly in live Odoo data
"""

import logging
from typing import Any, Dict, List, Optional

from providers.alamia_provider import AlamiaAIProvider
from context.context_engine import ActiveContext
from workflows.base_workflow import ActionCard, BaseWorkflow, WorkflowResult

logger = logging.getLogger("zelix.workflow.practice_query")


class PracticeQueryWorkflow(BaseWorkflow):
    def __init__(self):
        super().__init__(
            workflow_id="w00_practice_query",
            name="Practice Operations & Clinical Query",
            description="Queries live clinic statistics, census, appointments, staff, and pharmacy stock.",
        )

    async def execute(
        self,
        user_input: str,
        active_context: ActiveContext,
        context_prompt: str,
        provider: AlamiaAIProvider,
        odoo_client: Optional[Any] = None,
    ) -> WorkflowResult:
        """Executes operational inquiry against live Odoo database with deterministic grounding."""
        client = odoo_client
        prompt_lower = user_input.lower()

        # 1. Fetch live authoritative records (prefer native in-Odoo ORM session data if provided)
        vet_patients = []
        hms_patients = []
        vet_appts = []
        hms_appts = []
        vet_encs = []
        hms_consults = []
        inventory_data = []
        formulary_data = []
        users_data = []

        if active_context and getattr(active_context, "census", None):
            census = active_context.census
            vet_patients = census.get("vet_patients", [])
            hms_patients = census.get("hms_patients", [])
            vet_appts = census.get("vet_appointments", [])
            hms_appts = census.get("hms_visits", [])
            vet_encs = census.get("vet_encounters", [])
            hms_consults = census.get("hms_consults", [])
            inventory_data = census.get("stock_items", [])
            users_data = census.get("staff", [])
        elif client:
            # Fallback to XML-RPC client (for standalone / external MCP callers)
            # A. Patients (Vet & HMS)
            try:
                vet_patients = client.search_read(
                    "vet.patient",
                    [],
                    ["id", "name", "identifier", "species_id", "breed_id", "status"],
                    limit=50,
                )
            except Exception as e:
                logger.debug(f"vet.patient query skipped: {e}")

            try:
                hms_patients = client.search_read(
                    "hms.patient",
                    [],
                    ["id", "name", "mrn", "sex", "age", "phone", "blood_group"],
                    limit=50,
                )
            except Exception as e:
                logger.debug(f"hms.patient query skipped: {e}")

            # B. Appointments / Visits (Vet & HMS)
            try:
                vet_appts = client.search_read(
                    "vet.appointment",
                    [],
                    ["id", "name", "patient_id", "provider_id", "state", "start_datetime"],
                    limit=50,
                    order="start_datetime desc",
                )
            except Exception as e:
                logger.debug(f"vet.appointment query skipped: {e}")

            try:
                hms_appts = client.search_read(
                    "hms.visit",
                    [],
                    ["id", "name", "patient_id", "doctor_id", "stage", "state", "complaint", "arrival_time"],
                    limit=50,
                    order="arrival_time desc",
                )
            except Exception as e:
                logger.debug(f"hms.visit query skipped: {e}")

            # C. Encounters / Consultations (Vet & HMS)
            try:
                vet_encs = client.search_read(
                    "vet.encounter",
                    [],
                    ["id", "name", "patient_id", "provider_id", "state", "chief_complaint"],
                    limit=50,
                )
            except Exception as e:
                logger.debug(f"vet.encounter query skipped: {e}")

            try:
                hms_consults = client.search_read(
                    "hms.consult",
                    [],
                    ["id", "name", "patient_id", "doctor_id", "state"],
                    limit=50,
                )
            except Exception as e:
                logger.debug(f"hms.consult query skipped: {e}")

            # D. Physical Inventory Stock (product.product)
            try:
                inventory_data = client.search_read(
                    "product.product",
                    [],
                    [
                        "id",
                        "name",
                        "qty_available",
                        "virtual_available",
                        "vet_item_type",
                        "vet_storage_location",
                        "vet_reorder_min",
                        "vet_reorder_max",
                        "vet_controlled",
                        "list_price",
                    ],
                    limit=50,
                )
            except Exception as e:
                logger.debug(f"product.product query skipped: {e}")

            # E. Prescription Formulary Master (vet.medication & hms.medicine)
            try:
                v_meds = client.search_read(
                    "vet.medication",
                    [],
                    ["id", "name", "dosage_form", "controlled", "strength"],
                    limit=50,
                )
                formulary_data.extend(v_meds)
            except Exception as e:
                pass

            try:
                h_meds = client.search_read(
                    "hms.drug",
                    [],
                    ["id", "name", "form", "strength", "brand", "generic_name"],
                    limit=50,
                )
                formulary_data.extend(h_meds)
            except Exception as e:
                pass

            # F. Staff & Users
            try:
                users_data = client.search_read(
                    "res.users",
                    [("share", "=", False)],
                    ["id", "name", "login"],
                    limit=20,
                )
            except Exception as e:
                logger.debug(f"res.users query skipped: {e}")

        total_vet_patients = len(vet_patients)
        total_hms_patients = len(hms_patients)
        total_patients = total_vet_patients + total_hms_patients

        total_vet_appts = len(vet_appts)
        total_hms_appts = len(hms_appts)
        total_appts = total_vet_appts + total_hms_appts

        total_vet_encs = len(vet_encs)
        total_hms_consults = len(hms_consults)
        total_encs = total_vet_encs + total_hms_consults

        total_stock_items = len(inventory_data)
        total_formulary = len(formulary_data)
        total_staff = len(users_data)

        # 2. Build deterministic factual responses tailored to the specific query
        response_lines = []

        # A. Patient count / census queries
        if any(w in prompt_lower for w in ["how many patient", "patient count", "number of patient", "patients in", "census", "list patient"]):
            if total_patients == 0:
                response_lines.append("There are currently **no patients registered** in the system database.")
            else:
                summary_breakdown = []
                if total_hms_patients > 0:
                    summary_breakdown.append(f"{total_hms_patients} Hospital")
                if total_vet_patients > 0:
                    summary_breakdown.append(f"{total_vet_patients} Veterinary")
                breakdown_str = f" ({', '.join(summary_breakdown)})" if summary_breakdown else ""

                response_lines.append(f"There are currently **{total_patients} registered patients** in the database{breakdown_str}:")
                if hms_patients:
                    response_lines.append("\n**🏥 Stratos Hospital Patients:**")
                    for p in hms_patients[:5]:
                        age_str = f", {p.get('age')}y" if p.get('age') else ""
                        gen_str = f" ({p.get('gender', 'N/A').capitalize()}{age_str})" if p.get('gender') else ""
                        response_lines.append(f"- **{p.get('name')}** (Code: `{p.get('code', 'N/A')}`{gen_str})")
                if vet_patients:
                    response_lines.append("\n**🐾 VetCairn Veterinary Patients:**")
                    for p in vet_patients[:5]:
                        sp = p.get("species_id", [0, "Pet"])[1] if p.get("species_id") else "Pet"
                        response_lines.append(f"- **{p.get('name')}** (ID #{p.get('id')}, Species: {sp})")

        # B. Medication / Physical Inventory Stock Queries
        elif any(w in prompt_lower for w in ["medicine", "medication", "drug", "stock", "pharmacy", "inventory", "supplies"]):
            if total_stock_items > 0:
                response_lines.append(f"### Pharmacy & Clinical Inventory Stock ({total_stock_items} Products Tracked)")
                low_stock_items = []
                for item in inventory_data[:15]:
                    qty = item.get("qty_available", 0.0)
                    min_stock = item.get("vet_reorder_min", 0.0) or 0.0
                    loc = item.get("vet_storage_location") or "Main Clinic Storage"
                    ctrl_str = " *(Controlled)*" if item.get("vet_controlled") else ""

                    status_badge = "In Stock"
                    if qty == 0:
                        status_badge = "OUT OF STOCK"
                        low_stock_items.append(f"{item.get('name')} (0 units)")
                    elif min_stock > 0 and qty <= min_stock:
                        status_badge = f"LOW STOCK (Below {min_stock:.0f} min)"
                        low_stock_items.append(f"{item.get('name')} ({qty:.0f} on hand, min: {min_stock:.0f})")

                    response_lines.append(
                        f"- **{item.get('name')}**{ctrl_str}: **{qty:.0f} units on hand** [{status_badge}]\n"
                        f"  *(Location: {loc} | Min Reorder: {min_stock:.0f})*"
                    )

                if low_stock_items:
                    response_lines.append(f"\n⚠️ **Reorder Action Needed**: {len(low_stock_items)} item(s) below minimum safety threshold:")
                    for lsi in low_stock_items:
                        response_lines.append(f"  - {lsi}")

            elif total_formulary > 0:
                response_lines.append(f"### Healthcare Prescription Formulary ({total_formulary} Registered Medications)")
                for m in formulary_data[:10]:
                    form_str = f" ({m.get('dosage_form') or m.get('form', 'Tablet')})"
                    strength_str = f" - {m.get('strength') or m.get('dosage', '')}"
                    response_lines.append(f"- **{m.get('name')}**{strength_str}{form_str}")
            else:
                response_lines.append("No medication inventory or formulary catalog items found in the database.")

        # C. Staff / doctor queries
        elif any(w in prompt_lower for w in ["staff", "doctor", "veterinarian", "physician", "who is", "team", "who are"]):
            response_lines.append(f"### Healthcare Staff & Users ({total_staff} Active Members)")
            for u in users_data:
                response_lines.append(f"- **{u.get('name')}** (Login: `{u.get('login')}`)")

        # D. Operational summary / appointments / general activity
        else:
            response_lines.append("### Clinic & Hospital Operations Daily Summary")
            
            # Patients Breakdown
            patient_breakdown = []
            if total_hms_patients > 0:
                patient_breakdown.append(f"{total_hms_patients} Hospital")
            if total_vet_patients > 0:
                patient_breakdown.append(f"{total_vet_patients} Vet")
            pt_detail = f" ({', '.join(patient_breakdown)})" if patient_breakdown else ""
            response_lines.append(f"- **Registered Patients**: {total_patients}{pt_detail}")
            
            # Active patient names preview
            all_pt_names = [p.get("name") for p in (hms_patients + vet_patients)[:6] if p.get("name")]
            if all_pt_names:
                response_lines.append(f"  *(Active: {', '.join(all_pt_names)})*")

            # Appointments Breakdown
            appt_breakdown = []
            if total_hms_appts > 0:
                appt_breakdown.append(f"{total_hms_appts} Hospital")
            if total_vet_appts > 0:
                appt_breakdown.append(f"{total_vet_appts} Vet")
            appt_detail = f" ({', '.join(appt_breakdown)})" if appt_breakdown else ""
            response_lines.append(f"- **Scheduled Appointments**: {total_appts}{appt_detail}")
            
            # Clinical Encounters / Consultations
            enc_breakdown = []
            if total_hms_consults > 0:
                enc_breakdown.append(f"{total_hms_consults} Consultations")
            if total_vet_encs > 0:
                enc_breakdown.append(f"{total_vet_encs} Vet SOAP Encounters")
            enc_detail = f" ({', '.join(enc_breakdown)})" if enc_breakdown else ""
            response_lines.append(f"- **Clinical Encounters**: {total_encs} recorded{enc_detail}")

            # Pharmacy Inventory Stock
            response_lines.append(f"- **Physical Inventory Items**: {total_stock_items} tracked in warehouse")
            
            # Staff
            response_lines.append(f"- **Personnel on Duty**: {total_staff} active users")

        final_response = "\n".join(response_lines)

        return WorkflowResult(
            workflow_id=self.workflow_id,
            response_text=final_response,
            action_cards=[],
            metadata={
                "total_patients": total_patients,
                "total_appointments": total_appts,
                "total_encounters": total_encs,
                "total_stock_items": total_stock_items,
            },
        )
