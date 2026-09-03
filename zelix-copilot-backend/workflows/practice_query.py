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

        # 1. Fetch live authoritative records from Odoo
        patients_data = []
        appts_data = []
        encs_data = []
        inventory_data = []
        formulary_data = []
        users_data = []

        if client:
            # A. Patients
            try:
                patients_data = client.search_read(
                    "vet.patient",
                    [],
                    ["id", "name", "identifier", "species_id", "breed_id", "status"],
                    limit=50,
                )
            except Exception as e:
                logger.warning(f"Error querying vet.patient: {e}")

            # B. Appointments
            try:
                appts_data = client.search_read(
                    "vet.appointment",
                    [],
                    ["id", "name", "patient_id", "provider_id", "state", "start_datetime"],
                    limit=50,
                    order="start_datetime desc",
                )
            except Exception as e:
                logger.warning(f"Error querying vet.appointment: {e}")

            # C. Encounters
            try:
                encs_data = client.search_read(
                    "vet.encounter",
                    [],
                    ["id", "name", "patient_id", "provider_id", "state", "chief_complaint"],
                    limit=50,
                )
            except Exception as e:
                logger.warning(f"Error querying vet.encounter: {e}")

            # D. Physical Inventory Stock (product.product)
            try:
                inventory_data = client.search_read(
                    "product.product",
                    [("is_vet_item", "=", True)],
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
                logger.warning(f"Error querying product.product inventory: {e}")

            # E. Prescription Formulary Master (vet.medication)
            try:
                formulary_data = client.search_read(
                    "vet.medication",
                    [],
                    ["id", "name", "dosage_form", "controlled", "strength"],
                    limit=50,
                )
            except Exception as e:
                logger.warning(f"Error querying vet.medication: {e}")

            # F. Staff & Users
            try:
                users_data = client.search_read(
                    "res.users",
                    [("share", "=", False)],
                    ["id", "name", "login"],
                    limit=20,
                )
            except Exception as e:
                logger.warning(f"Error querying res.users: {e}")

        total_patients = len(patients_data)
        total_appts = len(appts_data)
        total_encs = len(encs_data)
        total_stock_items = len(inventory_data)
        total_formulary = len(formulary_data)
        total_staff = len(users_data)

        # 2. Build deterministic factual responses tailored to the specific query
        response_lines = []

        # A. Patient count / census queries
        if any(w in prompt_lower for w in ["how many patient", "patient count", "number of patient", "patients in", "census", "list patient"]):
            if total_patients == 0:
                response_lines.append("There are currently **no patients registered** in the clinic database.")
            elif total_patients == 1:
                p = patients_data[0]
                species_name = p.get("species_id", [0, "Unknown"])[1] if p.get("species_id") else "Unknown"
                status_str = p.get("status", "active").capitalize()
                response_lines.append(f"There is currently **1 registered patient** in the clinic database:")
                response_lines.append(f"- **{p.get('name')}** (ID #{p.get('id')}, Species: {species_name}, Status: {status_str})")
            else:
                response_lines.append(f"There are currently **{total_patients} registered patients** in the clinic database:")
                for p in patients_data[:10]:
                    species_name = p.get("species_id", [0, "Unknown"])[1] if p.get("species_id") else "Unknown"
                    response_lines.append(f"- **{p.get('name')}** (ID #{p.get('id')}, {species_name})")

        # B. Medication / Physical Inventory Stock Queries
        elif any(w in prompt_lower for w in ["medicine", "medication", "drug", "stock", "pharmacy", "inventory", "supplies"]):
            if total_stock_items > 0:
                response_lines.append(f"### Pharmacy & Clinical Inventory Stock ({total_stock_items} Products Tracked)")
                
                low_stock_items = []
                for item in inventory_data:
                    qty = item.get("qty_available", 0.0)
                    min_stock = item.get("vet_reorder_min", 0.0)
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
                response_lines.append("### Prescription Formulary (No Physical Stock Logged)")
                response_lines.append("No active inventory stock levels (`product.product`) were found in the warehouse, but the following medications are registered in the Rx Formulary:")
                for m in formulary_data:
                    form_str = f" ({m.get('dosage_form', 'Tablet')})" if m.get("dosage_form") else ""
                    strength_str = f" - {m.get('strength')}" if m.get("strength") else ""
                    response_lines.append(f"- **{m.get('name')}**{strength_str}{form_str} *(0 physical units in inventory)*")
            else:
                response_lines.append("No medication inventory or formulary catalog items found in the database.")

        # C. Staff / doctor queries
        elif any(w in prompt_lower for w in ["staff", "doctor", "veterinarian", "who is", "team", "who are"]):
            response_lines.append(f"### Clinic Staff & Users ({total_staff} Active Members)")
            for u in users_data:
                response_lines.append(f"- **{u.get('name')}** (Login: `{u.get('login')}`)")

        # D. Operational summary / appointments / general activity
        else:
            response_lines.append("### Clinic Operations & Daily Summary")
            response_lines.append(f"- **Registered Patients**: {total_patients}")
            if total_patients > 0:
                p_names = ", ".join(p.get("name") for p in patients_data[:5])
                response_lines.append(f"  *(Active: {p_names})*")

            # Appointments Breakdown
            response_lines.append(f"- **Scheduled Appointments**: {total_appts}")
            if total_appts > 0:
                status_counts = {}
                for a in appts_data:
                    st = a.get("state", "draft").capitalize()
                    status_counts[st] = status_counts.get(st, 0) + 1
                breakdown = ", ".join(f"{k}: {v}" for k, v in status_counts.items())
                response_lines.append(f"  *(Status: {breakdown})*")
                for a in appts_data[:3]:
                    pt_name = a.get("patient_id", [0, "Patient"])[1] if a.get("patient_id") else "Patient"
                    dr_name = a.get("provider_id", [0, "Doctor"])[1] if a.get("provider_id") else "Assigned Vet"
                    response_lines.append(f"  - `{a.get('name')}`: {pt_name} with {dr_name} ({a.get('state')})")

            # Clinical Encounters
            response_lines.append(f"- **Clinical Encounters**: {total_encs} recorded")
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
