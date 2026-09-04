# Repository Map & Index

This document maps high-level concepts and system domains to physical source code directories, configuration files, and scripts.

---

## 1. Concept to File Mapping

| Domain / Concept | Files / Locations | Description |
|---|---|---|
| **Container Orchestration** | [`docker-compose.yml`](file:///e:/myapps/odoo-mcp/docker-compose.yml) | Multi-container definitions for `db`, `web`, and `mcp` services |
| **Environment Configuration** | [`.env`](file:///e:/myapps/odoo-mcp/.env), [`.env.example`](file:///e:/myapps/odoo-mcp/.env.example) | Active configuration and environment variable templates |
| **Odoo 19 Server Config** | [`config/odoo.conf`](file:///e:/myapps/odoo-mcp/config/odoo.conf) | Database host, addons paths (`/mnt/extra-addons`, `/mnt/extra-addons/VetCairn`), memory/cpu limits |
| **In-Odoo MCP Addon** | [`addons/mcp_server/`](file:///e:/myapps/odoo-mcp/addons/mcp_server) | Odoo module providing `/mcp` HTTP endpoint, OAuth 2.1 authorization server, and security groups |
| **FastMCP Python Server** | [`mcp-server/server.py`](file:///e:/myapps/odoo-mcp/mcp-server/server.py) | FastMCP 4.x server defining 10 core AI tools for Odoo |
| **Odoo XML-RPC Client** | [`mcp-server/odoo_client.py`](file:///e:/myapps/odoo-mcp/mcp-server/odoo_client.py) | Reusable client wrapper for Odoo XML-RPC / JSON-RPC endpoints |
| **MCP Docker Definition** | [`mcp-server/Dockerfile`](file:///e:/myapps/odoo-mcp/mcp-server/Dockerfile), [`mcp-server/requirements.txt`](file:///e:/myapps/odoo-mcp/mcp-server/requirements.txt) | Python 3.12 slim container for FastMCP SSE server |
| **VetCairn Clinical Suite** | [`addons/VetCairn/`](file:///e:/myapps/odoo-mcp/addons/VetCairn) | 22 veterinary clinic modules (patients, appointments, clinical encounters, Rx) |
| **VetCairn Suite Installer** | [`addons/VetCairn/vet_installer/`](file:///e:/myapps/odoo-mcp/addons/VetCairn/vet_installer) | Master installer module declaring dependencies for all 22 vet modules |
| **Stratos HMS Suite** | [`addons/stratos_hms/`](file:///e:/myapps/odoo-mcp/addons/stratos_hms) | Human hospital EMR suite with AI scribe, hospital memory, learned rules, lab, pharmacy, OT, wards |
| **Automation & Verification** | [`scripts/test_mcp.py`](file:///e:/myapps/odoo-mcp/scripts/test_mcp.py), [`scripts/setup_odoo_mcp.py`](file:///e:/myapps/odoo-mcp/scripts/setup_odoo_mcp.py) | Verification tests and MCP model registration automation |

---

## 2. Key Odoo Models & Database Entities

| Model Technical Name | Business Domain | Key Fields |
|---|---|---|
| `vet.patient` | Pet / Patient Records | `name`, `identifier`, `species_id`, `breed_id`, `sex`, `primary_owner_id`, `clinic_id`, `microchip_number` |
| `vet.appointment` | Clinic Scheduling | `name`, `patient_id`, `client_id`, `provider_id`, `clinic_id`, `appointment_type_id`, `reason`, `start_datetime`, `end_datetime`, `state` |
| `vet.encounter` | Clinical Consultations | `patient_id`, `provider_id`, `encounter_date`, `chief_complaint`, `assessment`, `plan`, `state` |
| `vet.prescription` | Drug Prescriptions | `patient_id`, `provider_id`, `medication_id`, `dosage`, `frequency`, `duration`, `state` |
| `vet.vaccination` | Immunizations | `patient_id`, `vaccine_id`, `administered_date`, `next_due_date`, `lot_number`, `provider_id` |
| `vet.treatment.plan` | Treatment Plans | `patient_id`, `name`, `start_date`, `diagnosis_id`, `state` |
| `vet.diagnostic.order` | Diagnostic & Lab Orders | `patient_id`, `diagnostic_type_id`, `order_date`, `state`, `result_summary` |
| `hms.patient` | Human Hospital Patients | `name`, `mrn`, `dob`, `gender`, `cnic`, `phone`, `blood_group`, `emergency_contact_phone` |
| `hms.visit` | Hospital Visits / Encounters | `name`, `patient_id`, `department_id`, `doctor_id`, `complaint`, `stage`, `ews_score`, `state` |
| `hms.consult` | Doctor Consultation & Scribe | `visit_id`, `doctor_id`, `complaint`, `transcript`, `hpi`, `state`, `ai_summary` |
| `hms.case.memory` | Hospital Case Memory | `consult_id`, `doctor_id`, `department_id`, `diagnosis`, `icd10_code`, `prescription_json` |
| `hms.ai.rule` | Learned Prescribing Rules | `doctor_id`, `department_id`, `trigger_keywords`, `drug_id`, `dose`, `route`, `frequency` |
| `hms.order` | Lab & Diagnostic Orders | `visit_id`, `consult_id`, `test_id`, `urgency`, `state`, `result_value`, `flag` |
| `hms.critical.call` | Critical Lab Escalation Logs | `order_id`, `doctor_id`, `caller_id`, `result_value`, `read_back_confirmed`, `state` |
| `hms.dispense` | Pharmacy Dispense Orders | `visit_id`, `consult_id`, `patient_id`, `state`, `line_ids` |
| `hms.drug` | Formulary & Dose Guards | `name`, `generic_name`, `drug_class`, `allergen_class`, `default_dose`, `max_daily_dose_text` |
| `hms.admission` | IPD Inpatient Admissions | `patient_id`, `ward_id`, `bed_id`, `admit_date`, `discharge_date`, `state` |
| `hms.ward` / `hms.bed` | Wards & Bed Board | `name`, `department_id`, `gender_restriction`, `daily_rate`, `state` (`available`, `occupied`, `cleaning`) |
| `hms.mar` | Medication Administration Record | `admission_id`, `order_id`, `drug_id`, `dose`, `scheduled_time`, `given_time`, `scanned_barcode` |
| `hms.handoff` | SBAR Nursing Shift Handoffs | `admission_id`, `from_nurse_id`, `to_nurse_id`, `situation`, `background`, `assessment`, `recommendation` |
| `hms.surgery` | Operating Theatre Surgeries | `patient_id`, `theatre_id`, `surgeon_id`, `anesthetist_id`, `who_sign_in`, `who_time_out`, `who_sign_out` |
| `hms.blood.unit` / `request` | Blood Bank Inventory & Crossmatch | `donor_id`, `blood_group`, `rh_factor`, `product_type`, `verifier1_id`, `verifier2_id`, `state` |
| `hms.charge` | Clinical Charge Ledger | `visit_id`, `patient_id`, `product_id`, `amount`, `source_model`, `source_id`, `state` |
| `hms.dashboard` | Command Centre KPIs | `patients_today`, `in_building`, `ews_gt_5`, `bed_occupancy_pct`, `critical_calls_pending` |
| `mcp.enabled.model` | MCP Model Access Control | `model_id`, `allow_read`, `allow_create`, `allow_write`, `allow_unlink`, `allow_method_calls` |
| `res.partner` | Clients / Owners / Doctors | `name`, `email`, `phone`, `is_company`, `street`, `city` |
| `res.users` | System Users / Providers | `name`, `login`, `groups_id` |

---

## 3. Architecture & Domain Specifications
* [System Architecture & Multi-Model Tiered SLM Topology](file:///e:/myapps/odoo-mcp/.ai/permanent/architecture/01-system-architecture.md)
* [Stratos HMS Deep Analysis & Clinical Safety Specification](file:///e:/myapps/odoo-mcp/.ai/permanent/architecture/02-stratos-hms-deep-analysis.md)

