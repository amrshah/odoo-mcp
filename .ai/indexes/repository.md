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
| `hms.dispense` | Pharmacy Dispense Orders | `visit_id`, `consult_id`, `patient_id`, `state`, `line_ids` |
| `mcp.enabled.model` | MCP Model Access Control | `model_id`, `allow_read`, `allow_create`, `allow_write`, `allow_unlink`, `allow_method_calls` |
| `res.partner` | Clients / Owners / Doctors | `name`, `email`, `phone`, `is_company`, `street`, `city` |
| `res.users` | System Users / Providers | `name`, `login`, `groups_id` |
